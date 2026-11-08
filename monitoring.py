from collections import deque

from simulation import Simulation


ZONES = {
    'Zone_1': {'name': 'Zone 1', 'area': 'Central', 'latitude': 24.7136, 'longitude': 46.6753},
    'Zone_2': {'name': 'Zone 2', 'area': 'North', 'latitude': 24.7736, 'longitude': 46.6753},
    'Zone_3': {'name': 'Zone 3', 'area': 'South', 'latitude': 24.6536, 'longitude': 46.6753},
    'Zone_4': {'name': 'Zone 4', 'area': 'West', 'latitude': 24.7136, 'longitude': 46.6093},
    'Zone_5': {'name': 'Zone 5', 'area': 'East', 'latitude': 24.7136, 'longitude': 46.7413},
}


def display_reading(reading):
    zone = ZONES[reading['Zone']]
    block = int(reading['Block'].split('_')[-1])
    pipe = int(reading['Pipe'].split('_')[-1])
    return dict(reading, Latitude=zone['latitude'] + (block - 3) * 0.012,
                Longitude=zone['longitude'] + (pipe - 3) * 0.012)


class ContinuousMonitor:
    def __init__(self, readings, start_index=0, interval=2.0, pressure_limit=54,
                 flow_limit=90, major_limit=40, repair_ticks=8, fail_first=False,
                 unavailable=False, team_a_available=True, team_b_available=True):
        if not readings or interval < 0.5:
            raise ValueError('Invalid monitoring settings')
        self.readings = readings
        self.start_index = start_index % len(readings)
        self.total_readings = len(readings) - self.start_index
        self.interval_ticks = max(1, round(interval / 0.5))
        self.settings = dict(pressure_limit=pressure_limit, flow_limit=flow_limit,
                             major_limit=major_limit, repair_ticks=repair_ticks)
        self.fail_first = fail_first
        self.tick = self.observed = self.processed = 0
        self.confirmed = self.completed = self.failure_count = self.error_count = self.dropped = 0
        self.finished = self.running = False
        self.observation = self.latest_sim = None
        self.activity = []
        self.role_states = {}
        self.deliveries = deque(maxlen=8)
        self.focus_zone = readings[self.start_index]['Zone']
        self.history = deque(maxlen=600)
        self.performance = deque(maxlen=600)
        self.messages = deque(maxlen=1500)
        self.traces = deque(maxlen=1500)
        self.incidents = deque(maxlen=500)
        self.total_messages = self.total_calls = 0
        self.total_duration_ms = 0.0
        self.open_incidents = {}
        self.fleet = {
            'Team A': {'position': (24.7136, 46.6653), 'failed': False, 'enabled': not unavailable and team_a_available, 'owner': None},
            'Team B': {'position': (24.7336, 46.7053), 'failed': False, 'enabled': not unavailable and team_b_available, 'owner': None},
        }
        self.regions = {zone: {'latest': None, 'classification': 'No readings', 'active': None,
                               'pending': deque(), 'last_sim': None, 'last_monitor': None,
                               'last_task': None} for zone in ZONES}

    @property
    def seconds(self):
        return self.tick * 0.5

    def refresh_teams(self, sim):
        for team in sim.teams:
            saved = self.fleet[team.name]
            if saved['owner'] == sim.conversation_id and team.remaining:
                continue
            team.position = saved['position']
            team.failed = saved['failed']
            team.available = saved['enabled'] and not saved['failed'] and saved['owner'] is None
            team.status = ('Failed' if team.failed else 'Busy' if saved['owner'] else
                           'Available' if team.available else 'Unavailable')
            team.fail_on_accept = self.fail_first and team.name == 'Team A' and not team.failed

    def reserve_team(self, sim, name):
        saved = self.fleet[name]
        if not saved['enabled'] or saved['failed'] or saved['owner'] not in (None, sim.conversation_id):
            return False
        saved['owner'] = sim.conversation_id
        return True

    def update_fleet(self, sim):
        for team in sim.teams:
            saved = self.fleet[team.name]
            if saved['owner'] != sim.conversation_id:
                continue
            saved['position'] = team.position
            if team.failed:
                saved['failed'] = True
                saved['owner'] = None
            elif not team.remaining and team.available:
                saved['owner'] = None

    def healthy_busy_team(self):
        return any(t['enabled'] and not t['failed'] and t['owner'] for t in self.fleet.values())

    def free_team(self):
        return any(t['enabled'] and not t['failed'] and t['owner'] is None for t in self.fleet.values())

    def advance(self):
        if self.finished:
            self.running = False
            return
        if not self.running:
            return
        self.activity = []
        self.tick += 1
        if self.observation is None and self.observed < self.total_readings and (self.tick - 1) % self.interval_ticks == 0:
            self.observe()
        if self.observation:
            sim, zone = self.observation
            sim.step()
            self.sync(sim, zone)
            if sim.step_number == 3:
                self.finish_observation(sim, zone)
                self.observation = None
                self.processed += 1
        for zone, region in self.regions.items():
            if region['active'] is None and region['pending']:
                region['active'] = region['pending'].popleft()
                region['active']['status'] = 'Processing'
            incident = region['active']
            if incident is None:
                continue
            sim = incident['sim']
            self.refresh_teams(sim)
            if incident['status'] == 'Waiting for team' and self.free_team():
                sim.result = 'Monitoring'
                sim.agents['Dispatch'].collect_offers()
            if sim.active:
                try:
                    sim.step()
                except Exception as error:
                    sim.queue.clear()
                    for team in sim.teams:
                        if self.fleet[team.name]['owner'] == sim.conversation_id:
                            self.fleet[team.name]['owner'] = None
                        team.remaining = 0
                    sim.result = f'Execution error: {type(error).__name__}'
                self.update_fleet(sim)
                self.sync(sim, zone)
            incident['status'] = sim.result if sim.result != 'Monitoring' else 'Processing'
            if sim.waiting_approval:
                incident['status'] = 'Waiting for approval'
            elif any(t.remaining for t in sim.teams):
                incident['status'] = 'Repairing'
            elif not sim.active and sim.result.startswith('No available team') and (self.healthy_busy_team() or self.free_team()):
                incident['status'] = 'Waiting for team'
            elif not sim.active:
                incident['finished_seconds'] = self.seconds
                region['last_sim'] = region['last_task'] = sim
                if sim.repaired:
                    self.completed += 1
                    self.open_incidents.pop(incident['key'], None)
                    incident['status'] = 'Completed'
                region['active'] = None
        self.performance.append({'seconds': self.seconds, 'confirmed': self.confirmed,
                                 'completed': self.completed})
        runnable = any((r['active'] and (r['active']['sim'].active or
                                        r['active']['status'] == 'Waiting for team')) or
                       (r['active'] is None and r['pending']) for r in self.regions.values())
        if self.processed == self.total_readings and not runnable:
            self.running = False
            self.finished = True

    def observe(self):
        index = self.start_index + self.observed
        reading = display_reading(self.readings[index])
        self.observed += 1
        zone = reading['Zone']
        region = self.regions[zone]
        sim = Simulation(reading, **self.settings)
        sim.conversation_id = f'reading-{self.observed}'
        sim.monitor_row = index + 1
        sim.synced_messages = sim.synced_traces = 0
        sim.reserve_team = lambda name: self.reserve_team(sim, name)
        self.refresh_teams(sim)
        sim.start()
        self.observation = (sim, zone)
        self.focus_zone = zone
        region['latest'] = reading
        region['classification'] = 'Checking'
        self.history.append({'seconds': self.seconds, 'row': index + 1, 'zone': zone,
                             'Block': reading['Block'], 'Pipe': reading['Pipe'],
                             'Pressure': reading['Pressure'], 'Flow_Rate': reading['Flow_Rate']})

    def finish_observation(self, sim, zone):
        region = self.regions[zone]
        reading = sim.reading
        self.latest_sim = sim
        region['last_sim'] = region['last_monitor'] = sim
        low = reading['Pressure'] < self.settings['pressure_limit']
        high = reading['Flow_Rate'] > self.settings['flow_limit']
        region['classification'] = 'Confirmed leak' if sim.detected else 'Suspected' if low or high else 'Normal'
        if sim.detected:
            key = (zone, reading['Block'], reading['Pipe'])
            if key not in self.open_incidents and len(region['pending']) < 100:
                incident = {'id': sim.conversation_id, 'key': key, 'zone': zone, 'sim': sim,
                            'status': 'Queued', 'created_seconds': self.seconds, 'finished_seconds': None}
                self.open_incidents[key] = incident
                self.incidents.append(incident)
                region['pending'].append(incident)
                self.confirmed += 1
            else:
                if key not in self.open_incidents:
                    self.dropped += 1
                for message in sim.queue:
                    message['cancelled'] = True
                sim.queue.clear()
        self.sync(sim, zone)

    def sync(self, sim, zone):
        for message in sim.messages[sim.synced_messages:]:
            message.update(zone=zone, seconds=self.seconds, row=sim.monitor_row)
            self.messages.append(message)
            self.total_messages += 1
            if message['performative'] == 'INFORM' and message['content'].get('state') == 'failed':
                self.failure_count += 1
        sim.synced_messages = len(sim.messages)
        for message in sim.messages:
            if message['delivered'] and 'delivered_seconds' not in message:
                message['delivered_seconds'] = self.seconds
                self.deliveries.append(message)
        for trace in sim.traces[sim.synced_traces:]:
            item = dict(trace, zone=zone, seconds=self.seconds, conversation_id=sim.conversation_id)
            self.traces.append(item)
            self.activity.append((zone, trace['agent']))
            self.role_states[trace['agent']] = {'status': sim.agents[trace['agent']].status,
                                                 'zone': ZONES[zone]['name']}
            self.total_calls += 1
            self.total_duration_ms += trace['duration_ms']
            self.error_count += bool(trace['error'])
        sim.synced_traces = len(sim.traces)

    def approve(self, zone, accepted):
        incident = self.regions[zone]['active']
        if incident and incident['sim'].waiting_approval:
            incident['sim'].approve(accepted)
            self.sync(incident['sim'], zone)
            if self.finished:
                self.finished = False
                self.running = True

    def zone_status(self, zone):
        incidents = [item for key, item in self.open_incidents.items() if key[0] == zone]
        if incidents:
            active = self.regions[zone]['active']
            return 'Confirmed leak', active['status'] if active else incidents[-1]['status']
        previous = self.regions[zone]['last_sim']
        return self.regions[zone]['classification'], 'Completed' if previous and previous.repaired else 'No open incident'

    def selected_sim(self, zone):
        region = self.regions[zone]
        return region['active']['sim'] if region['active'] else region['last_sim']

    def agent_states(self, zone):
        region = self.regions[zone]
        sensing = self.observation[0] if self.observation and self.observation[1] == zone else region['last_monitor']
        task = region['active']['sim'] if region['active'] else region['last_task']
        states = {}
        for name in ('Pressure Monitor', 'Usage Monitor', 'Leak Locator', 'Dispatch', 'Team A', 'Team B'):
            if name in self.fleet:
                saved = self.fleet[name]
                states[name] = ('Failed' if saved['failed'] else 'Repairing' if saved['owner'] else
                                'Available' if saved['enabled'] else 'Unavailable')
            else:
                sim = sensing if name in ('Pressure Monitor', 'Usage Monitor') else task
                states[name] = sim.agents[name].status if sim else 'Idle'
        return states

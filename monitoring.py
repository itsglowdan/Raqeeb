from collections import deque

from simulation import Simulation


CITIES = {
    "Zone_1": {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753},
    "Zone_2": {"name": "Madinah", "latitude": 24.4672, "longitude": 39.6024},
    "Zone_3": {"name": "Abha", "latitude": 18.2164, "longitude": 42.5053},
    "Zone_4": {"name": "Makkah", "latitude": 21.3891, "longitude": 39.8579},
    "Zone_5": {"name": "Dammam", "latitude": 26.4207, "longitude": 50.0888},
}


def display_reading(reading):
    city = CITIES[reading["Zone"]]
    block = int(reading["Block"].split("_")[-1])
    pipe = int(reading["Pipe"].split("_")[-1])
    return dict(reading, Latitude=city["latitude"] + (block - 3) * 0.012,
                Longitude=city["longitude"] + (pipe - 3) * 0.012)


class ContinuousMonitor:
    def __init__(self, readings, start_index=0, interval=2.0, pressure_limit=54,
                 flow_limit=90, major_limit=40, repair_ticks=8, fail_first=False,
                 unavailable=False):
        if not readings or interval < 0.5:
            raise ValueError("Invalid monitoring settings")
        self.readings = readings
        self.start_index = start_index % len(readings)
        self.interval_ticks = max(1, round(interval / 0.5))
        self.settings = dict(pressure_limit=pressure_limit, flow_limit=flow_limit,
                             major_limit=major_limit, repair_ticks=repair_ticks)
        self.fail_first = fail_first
        self.unavailable = unavailable
        self.tick = 0
        self.total_readings = len(readings) - self.start_index
        self.processed = 0
        self.finished = False
        self.observation = None
        self.activity = []
        self.role_states = {}
        self.deliveries = deque(maxlen=8)
        self.focus_zone = readings[self.start_index]["Zone"]
        self.observed = 0
        self.confirmed = 0
        self.completed = 0
        self.failure_count = 0
        self.error_count = 0
        self.dropped = 0
        self.running = False
        self.history = deque(maxlen=600)
        self.performance = deque(maxlen=600)
        self.messages = deque(maxlen=1500)
        self.traces = deque(maxlen=1500)
        self.incidents = deque(maxlen=500)
        self.total_messages = 0
        self.total_calls = 0
        self.total_duration_ms = 0.0
        self.open_incidents = {}
        self.latest_sim = None
        self.cities = {}
        for zone, city in CITIES.items():
            self.cities[zone] = {
                "latest": None, "classification": "No readings", "active": None,
                "pending": deque(), "last_sim": None, "last_monitor": None, "last_task": None,
                "teams": [{"position": (city["latitude"] + offset, city["longitude"]),
                           "failed": False, "available": not unavailable}
                          for offset in (0.002, 0.04)],
            }

    @property
    def seconds(self):
        return self.tick * 0.5

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
        for zone, city in self.cities.items():
            if city["active"] is None and city["pending"]:
                incident = city["pending"].popleft()
                city["active"] = incident
                self.restore_teams(incident["sim"], city)
                incident["status"] = "Processing"
            incident = city["active"]
            if incident is None:
                continue
            sim = incident["sim"]
            if sim.active:
                try:
                    sim.step()
                except Exception as error:
                    sim.queue.clear()
                    for team in sim.teams:
                        team.remaining = 0
                    sim.result = f"Execution error: {type(error).__name__}"
                    incident["status"] = "Unresolved: execution error"
                self.sync(sim, zone)
            incident["status"] = sim.result if sim.result != "Monitoring" else "Processing"
            if sim.waiting_approval:
                incident["status"] = "Waiting for approval"
            elif any(team.remaining for team in sim.teams):
                incident["status"] = "Repairing"
            elif not sim.active:
                incident["finished_seconds"] = self.seconds
                city["last_sim"] = sim
                city["last_task"] = sim
                city["teams"] = [{"position": team.position, "failed": team.failed,
                                  "available": team.available} for team in sim.teams]
                if sim.repaired:
                    self.completed += 1
                    self.open_incidents.pop(incident["key"], None)
                    incident["status"] = "Completed"
                city["active"] = None
        self.performance.append({"seconds": self.seconds, "confirmed": self.confirmed,
                                 "completed": self.completed,
                                 "messages": self.total_messages, "failures": self.failure_count,
                                 "errors": self.error_count})

        runnable = any((city["active"] and city["active"]["sim"].active) or
                       (city["active"] is None and city["pending"]) for city in self.cities.values())
        if self.processed == self.total_readings and not runnable:
            self.running = False
            self.finished = True

    def observe(self):
        index = self.start_index + self.observed
        reading = display_reading(self.readings[index])
        self.observed += 1
        zone = reading["Zone"]
        city = self.cities[zone]
        sim = Simulation(reading, **self.settings)
        sim.conversation_id = f"reading-{self.observed}"
        sim.monitor_row = index + 1
        sim.synced_messages = sim.synced_traces = 0
        self.restore_teams(sim, city)
        sim.start()
        self.observation = (sim, zone)
        self.focus_zone = zone
        city["latest"] = reading
        city["classification"] = "Checking"
        self.history.append({"seconds": self.seconds, "row": index + 1,
                             "city": CITIES[zone]["name"], "Pressure": reading["Pressure"],
                             "Flow_Rate": reading["Flow_Rate"]})

    def finish_observation(self, sim, zone):
        city = self.cities[zone]
        reading = sim.reading
        self.latest_sim = sim
        city["last_sim"] = sim
        city["last_monitor"] = sim
        low = reading["Pressure"] < self.settings["pressure_limit"]
        high = reading["Flow_Rate"] > self.settings["flow_limit"]
        city["classification"] = "Confirmed leak" if sim.detected else "Suspected" if low or high else "Normal"
        if sim.detected:
            key = (zone, reading["Block"], reading["Pipe"])
            if key not in self.open_incidents and len(city["pending"]) < 100:
                incident = {"id": sim.conversation_id, "key": key, "zone": zone, "sim": sim,
                            "status": "Queued", "created_seconds": self.seconds,
                            "finished_seconds": None}
                self.open_incidents[key] = incident
                self.incidents.append(incident)
                city["pending"].append(incident)
                self.confirmed += 1
            else:
                if key not in self.open_incidents:
                    self.dropped += 1
                for message in sim.queue:
                    message["cancelled"] = True
                sim.queue.clear()
        self.sync(sim, zone)

    def restore_teams(self, sim, city):
        for team, saved in zip(sim.teams, city["teams"]):
            team.position = saved["position"]
            team.failed = saved["failed"]
            team.available = saved["available"] and not self.unavailable and not team.failed
            team.status = "Failed" if team.failed else "Available" if team.available else "Unavailable"
            team.fail_on_accept = self.fail_first and team.name == "Team A" and not team.failed

    def sync(self, sim, zone):
        for message in sim.messages[sim.synced_messages:]:
            message.update(city=CITIES[zone]["name"], seconds=self.seconds,
                           row=sim.monitor_row)
            self.messages.append(message)
            self.total_messages += 1
            if message["performative"] == "INFORM" and message["content"].get("state") == "failed":
                self.failure_count += 1
        sim.synced_messages = len(sim.messages)
        for message in sim.messages:
            if message["delivered"] and "delivered_seconds" not in message:
                message["delivered_seconds"] = self.seconds
                self.deliveries.append(message)
        for trace in sim.traces[sim.synced_traces:]:
            item = dict(trace, city=CITIES[zone]["name"], seconds=self.seconds,
                        conversation_id=sim.conversation_id)
            self.traces.append(item)
            self.activity.append((zone, trace["agent"]))
            self.role_states[trace["agent"]] = {"status": sim.agents[trace["agent"]].status,
                                                 "city": CITIES[zone]["name"]}
            self.total_calls += 1
            self.total_duration_ms += trace["duration_ms"]
            self.error_count += bool(trace["error"])
        sim.synced_traces = len(sim.traces)

    def approve(self, zone, accepted):
        incident = self.cities[zone]["active"]
        if incident and incident["sim"].waiting_approval:
            incident["sim"].approve(accepted)
            self.sync(incident["sim"], zone)
            if self.finished:
                self.finished = False
                self.running = True

    def city_status(self, zone):
        incidents = [item for key, item in self.open_incidents.items() if key[0] == zone]
        if incidents:
            active = self.cities[zone]["active"]
            return "Confirmed leak", active["status"] if active else incidents[-1]["status"]
        previous = self.cities[zone]["last_sim"]
        return self.cities[zone]["classification"], "Completed" if previous and previous.repaired else "No open incident"

    def selected_sim(self, zone):
        city = self.cities[zone]
        return city["active"]["sim"] if city["active"] else city["last_sim"]

    def agent_states(self, zone):
        city = self.cities[zone]
        sensing = self.observation[0] if self.observation and self.observation[1] == zone else city["last_monitor"]
        task = city["active"]["sim"] if city["active"] else city["last_task"]
        states = {}
        for name in ("Pressure Monitor", "Usage Monitor", "Leak Locator", "Dispatch", "Team A", "Team B"):
            sim = sensing if name in ("Pressure Monitor", "Usage Monitor") else task
            if sim:
                status = sim.agents[name].status
            elif name in ("Team A", "Team B"):
                saved = city["teams"][0 if name == "Team A" else 1]
                status = "Failed" if saved["failed"] else "Available" if saved["available"] else "Unavailable"
            else:
                status = "Idle"
            states[name] = status
        return states

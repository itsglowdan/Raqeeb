from math import asin, cos, radians, sin, sqrt
from data_loader import validate_reading
from protocol import utc_now


def distance_km(first, second):
    a, b = map(radians, first)
    c, d = map(radians, second)
    v = sin((c-a)/2)**2 + cos(a)*cos(c)*sin((d-b)/2)**2
    return 6371 * 2 * asin(sqrt(min(1, max(0, v))))


class Agent:
    role = ''

    def __init__(self, name, system):
        self.name, self.system = name, system
        self.state, self.action, self.last_activity, self.failure = 'Idle', 'No activity yet', None, None

    def touch(self, state, action):
        self.state, self.action, self.last_activity = state, action, utc_now()

    def send(self, receiver, performative, content, message=None, task_ref=None):
        return self.system.bus.send(self.name, receiver, performative, content, self.system.step,
                                    message.record_ref if message else self.system.current_ref,
                                    task_ref or (message.task_ref if message else None))


class ReadingAgent(Agent):
    role = 'Validate and deliver selected readings'

    def receive(self, message):
        row = message.content['reading']
        try:
            validate_reading(row, labeled=row.get('source') != 'Custom simulation input')
        except ValueError as error:
            self.touch('Validation failed', str(error))
            self.system.events.append({'step': self.system.step, 'type': 'validation_failure', 'record_ref': message.record_ref, 'reason': str(error)})
            self.system.fail_current(str(error))
            return
        self.touch('Delivered', message.record_ref)
        # Dataset labels never enter the assessment protocol.
        payload = {key: value for key, value in row.items() if key != 'Leakage_Flag'}
        self.send('Pressure Monitor', 'REQUEST', {'reading': payload}, message)


class PressureMonitor(Agent):
    role = 'Check pressure and request independent flow verification'

    def receive(self, message):
        if message.performative == 'REQUEST':
            reading = message.content['reading']
            low = reading['Pressure_PSI'] < self.system.config.pressure_limit
            self.touch('Checking', f"Pressure {reading['Pressure_PSI']:.2f} PSI")
            self.send('Usage Monitor', 'REQUEST', {'reading': reading, 'pressure_low': low}, message)
        else:
            low, high = message.content['pressure_low'], message.content['flow_high']
            reading = message.content['reading']
            result = 'Leak indicated' if low and high else 'Suspected' if low or high else 'Normal'
            reasons = []
            if low:
                reasons.append(f"Pressure {reading['Pressure_PSI']:.2f} < {self.system.config.pressure_limit} PSI")
            if high:
                reasons.append(f"Flow {reading['Flow_Rate_Lmin']:.2f} > {self.system.config.flow_limit} L/min")
            assessment = {'record_ref': message.record_ref, 'assessment': result,
                          'reason': '; '.join(reasons) or 'Neither detection threshold crossed',
                          'pressure_low': low, 'flow_high': high, 'step': self.system.step,
                          'source': reading.get('source', 'Dataset Readings')}
            self.system.assessments.append(assessment)
            self.touch(result, assessment['reason'])
            if low and high:
                self.send('Leak Locator', 'REQUEST', {'reading': reading, 'assessment': assessment}, message)
            else:
                self.send('Dispatch', 'INFORM', {'assessment': assessment, 'reading': reading}, message)


class UsageMonitor(Agent):
    role = 'Independently check flow; return verification'

    def receive(self, message):
        content = dict(message.content)
        content['flow_high'] = content['reading']['Flow_Rate_Lmin'] > self.system.config.flow_limit
        self.touch('High flow' if content['flow_high'] else 'Normal flow', f"Flow {content['reading']['Flow_Rate_Lmin']:.2f} L/min")
        self.send('Pressure Monitor', 'INFORM', content, message)


class LeakLocator(Agent):
    role = 'Preserve exact record coordinates and identify severity'

    def receive(self, message):
        content = dict(message.content)
        row = content['reading']
        content['major'] = row['Pressure_PSI'] <= self.system.config.major_limit
        content['location'] = {key: row[key] for key in ['Zone', 'Block', 'Pipe', 'Location_Code', 'Latitude', 'Longitude']}
        self.touch('Location identified', f"{message.record_ref}: {row['Latitude']}, {row['Longitude']}")
        self.send('Dispatch', 'REQUEST', content, message)


class Dispatch(Agent):
    role = 'Coordinate reports, supervisor approval and simulated team negotiation'

    def receive(self, message):
        system, content = self.system, message.content
        if message.sender == 'Reporting Agent':
            system.report_response(message)
        elif message.sender == 'Supervisor':
            system.waiting_approval = False
            if message.performative == 'ACCEPT':
                self.touch('Approved', 'Supervisor accepted simulated dispatch')
                system.request_teams()
            else:
                self.touch('Refused', 'Supervisor rejected simulated dispatch')
                system.complete_workflow('Dispatch rejected; no intervention performed')
        elif message.sender in ['Team A', 'Team B']:
            if message.performative in ['PROPOSE', 'REFUSE']:
                system.offers[message.sender] = content.get('distance_km') if message.performative == 'PROPOSE' else None
                if len(system.offers) == 2:
                    available = {name: distance for name, distance in system.offers.items() if distance is not None}
                    if available:
                        chosen = min(available, key=lambda name: (available[name], name))
                        system.assigned = chosen
                        self.touch('Assigning', f'{chosen}: nearest configured available simulated team')
                        self.send(chosen, 'ACCEPT', system.location_content, message)
                        for other in available:
                            if other != chosen:
                                self.send(other, 'REFUSE', {'reason': 'Closer available offer accepted'}, message)
                    else:
                        system.complete_workflow('No available simulated team; unresolved')
            elif content.get('state') == 'failed':
                system.events.append({'step': system.step, 'type': 'team_failure', 'agent': message.sender, 'record_ref': message.record_ref})
                self.touch('Reassigning', f'{message.sender} failed; requesting remaining teams')
                system.request_teams()
            elif content.get('state') == 'completed':
                system.complete_workflow(f'Simulated task completed by {message.sender}')
        else:
            system.location_content = content
            if content.get('major'):
                system.waiting_approval = True
                self.touch('Waiting approval', 'Major rule assessment; supervisor decision required')
                system.request_report('Major rule assessment; awaiting supervisor approval')
            elif content['assessment']['assessment'] == 'Leak indicated':
                system.request_report('Dual-rule leak assessment; simulated dispatch requested')
                system.request_teams()
            else:
                system.complete_workflow(content['assessment']['assessment'])


class RepairTeam(Agent):
    role = 'Represent a configured maintenance team in simulation only'

    def __init__(self, name, system, position, available=True):
        super().__init__(name, system)
        self.position, self.available = tuple(position), available
        self.remaining = 0
        self.assignment = None

    def receive(self, message):
        if message.performative == 'CFP':
            if not self.available or self.failure:
                self.send('Dispatch', 'REFUSE', {'reason': self.failure or 'Configured unavailable'}, message)
            else:
                row = message.content['reading']
                distance = distance_km(self.position, (row['Latitude'], row['Longitude']))
                self.touch('Offer sent', f'Straight-line distance {distance:.3f} km')
                self.send('Dispatch', 'PROPOSE', {'distance_km': distance, 'distance_type': 'Straight-line; not a route'}, message)
        elif message.performative == 'ACCEPT':
            if self.name == 'Team A' and self.system.config.fail_team_a and not self.system.team_a_fault_consumed:
                self.system.team_a_fault_consumed = True
                self.failure = 'User-configured assignment failure'
                self.available = False
                self.touch('Failed', self.failure)
                self.send('Dispatch', 'INFORM', {'state': 'failed'}, message)
            else:
                self.available = False
                self.assignment = message
                self.remaining = self.system.config.team_steps
                self.touch('Simulated task', f'{message.record_ref}; no physical intervention')
                self.send('Dispatch', 'INFORM', {'state': 'accepted'}, message)
        elif not self.failure:
            self.touch('Available', 'Offer not selected')

    def tick(self):
        if self.remaining:
            self.remaining -= 1
            if self.remaining == 0:
                self.available = True
                self.touch('Task completed', 'Simulated work only')
                self.send('Dispatch', 'INFORM', {'state': 'completed'}, self.assignment)


class ReportingAgent(Agent):
    role = 'Create idempotent, traceable alert and outcome records'

    def __init__(self, name, system):
        super().__init__(name, system)
        self.available = not system.config.reporting_unavailable
        self.silent = system.config.reporting_silent

    def receive(self, message):
        if not self.available:
            self.failure = 'User-configured unavailability'
            self.touch('Unavailable', self.failure)
            self.send('Dispatch', 'REFUSE', {'reason': self.failure}, message)
        else:
            self.failure = None
            if not any(row['task_ref'] == message.task_ref for row in self.system.reports):
                self.system.reports.append({'task_ref': message.task_ref, 'record_ref': message.record_ref,
                                            'conversation_id': message.conversation_id,
                                            'runtime_timestamp': utc_now(), **message.content})
            if self.silent:
                self.touch('Acknowledgment withheld', 'Report stored; user-configured acknowledgment loss')
            else:
                self.touch('Report created', message.task_ref)
                self.send('Dispatch', 'INFORM', {'state': 'recorded'}, message)

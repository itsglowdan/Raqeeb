from dataclasses import dataclass, asdict
from copy import deepcopy
from uuid import uuid4
import math
from agents import PressureMonitor, UsageMonitor, LeakLocator, Dispatch, RepairTeam
from data_loader import validate_reading
from protocol import MessageBus, utc_now


@dataclass(frozen=True)
class Configuration:
    pressure_limit: float = 54.0
    flow_limit: float = 90.0
    major_limit: float = 40.0
    team_steps: int = 4
    playback_interval: float = 0.5
    team_a_available: bool = True
    team_b_available: bool = True
    fail_team_a: bool = False
    fail_team_b: bool = False

    def __post_init__(self):
        for key in ['pressure_limit', 'flow_limit', 'major_limit', 'playback_interval']:
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f'{key} must be positive and finite')
        if self.major_limit >= self.pressure_limit:
            raise ValueError('Major pressure limit must be below low-pressure limit')
        for key in ['team_steps']:
            if not isinstance(getattr(self, key), int) or getattr(self, key) < 1:
                raise ValueError(f'{key} must be a positive integer')



class Simulation:
    def __init__(self, readings, config=None, metadata=None, team_positions=None):
        if not readings:
            raise ValueError('Add at least one reading before running')
        self.readings = deepcopy(readings)
        refs = [row['record_ref'] for row in self.readings]
        if len(refs) != len(set(refs)):
            raise ValueError('Sequence record references must be unique')
        self.config = config or Configuration()
        self.metadata = deepcopy(metadata or {})
        self.run_id = uuid4().hex[:12]
        self.created_at, self.started_at, self.finished_at = utc_now(), None, None
        self.status, self.step, self.cursor = 'Ready', 0, 0
        self.current = None
        self.waiting_approval, self.workflow_done, self.had_failure = False, False, False
        self.bus = MessageBus(self.run_id)
        self.assessments, self.reports, self.events, self.outcomes = [], [], [], []
        self.offers = {}
        self.location_content, self.assigned = {}, None
        self.team_faults_consumed = set()
        self.team_attempts = []
        self.positions = deepcopy(team_positions or {
            'Team A': {'record_ref': refs[0], 'position': [self.readings[0]['Latitude'], self.readings[0]['Longitude']]},
            'Team B': {'record_ref': refs[-1], 'position': [self.readings[-1]['Latitude'], self.readings[-1]['Longitude']]}})
        self.agents = {}
        for name, kind in [('Pressure Monitor', PressureMonitor), ('Usage Monitor', UsageMonitor),
                           ('Leak Locator', LeakLocator), ('Dispatch', Dispatch)]:
            self.agents[name] = kind(name, self)
        for name, available in [('Team A', self.config.team_a_available), ('Team B', self.config.team_b_available)]:
            self.agents[name] = RepairTeam(name, self, self.positions[name]['position'], available)

    @property
    def current_ref(self):
        return self.current['record_ref'] if self.current else None

    def run(self):
        if self.status in ['Ready', 'Paused']:
            self.status = 'Running'
            self.started_at = self.started_at or utc_now()

    def pause(self):
        if self.status == 'Running':
            self.status = 'Paused'

    def approve(self, accepted):
        if self.status != 'Running' or not self.waiting_approval:
            return False
        self.bus.send('Supervisor', 'Dispatch', 'ACCEPT' if accepted else 'REFUSE',
                      {'decision': 'User approval' if accepted else 'User rejection'}, self.step, self.current_ref)
        self.waiting_approval = False
        return True

    def restore(self, name):
        agent = self.agents[name]
        if not isinstance(agent, RepairTeam):
            raise ValueError('Only maintenance teams can be restored')
        agent.available = True
        agent.failure = None
        agent.touch('Restored', 'Restored by user; pending work continues on Resume')
        self.events.append({'step': self.step, 'type': 'agent_restored', 'agent': name, 'runtime_timestamp': utc_now()})

    def request_teams(self):
        self.offers = {}
        self.agents['Dispatch'].touch('Negotiating', 'Requesting configured team offers')
        for name in ['Team A', 'Team B']:
            self.bus.send('Dispatch', name, 'CFP', self.location_content, self.step, self.current_ref)

    def assign_team(self, team):
        self.assigned = team
        prior = [a for a in self.team_attempts if a['record_ref'] == self.current_ref]
        self.team_attempts.append({'assignment_id': f'{self.run_id}-A{len(self.team_attempts)+1}',
                                   'record_ref': self.current_ref, 'team': team,
                                   'attempt': len(prior)+1, 'reassigned_from': prior[-1]['team'] if prior else None,
                                   'state': 'Assigned', 'assigned_step': self.step, 'finished_step': None,
                                   'reason': None})
        return self.team_attempts[-1]

    def update_team_attempt(self, team, state, reason=None):
        attempt = next((a for a in reversed(self.team_attempts)
                        if a['record_ref'] == self.current_ref and a['team'] == team), None)
        if attempt is None:
            raise ValueError('No matching team assignment')
        attempt['state'] = state
        attempt['reason'] = reason
        if state in ['Failed', 'Completed']:
            attempt['finished_step'] = self.step

    def record_report(self, outcome):
        task_ref = f'{self.run_id}-R{len(self.reports)+1}'
        self.reports.append({'task_ref': task_ref, 'record_ref': self.current_ref,
                             'conversation_id': f'{self.run_id}:{self.current_ref}',
                             'runtime_timestamp': utc_now(), 'outcome': outcome,
                             'assessment': deepcopy(self.location_content.get('assessment')),
                             'location': deepcopy(self.location_content.get('location')),
                             'source': self.current.get('source', 'Dataset Readings')})

    def deliver_reading(self):
        try:
            validate_reading(self.current, labeled=self.current.get('source') != 'Custom simulation input')
        except ValueError as error:
            self.events.append({'step': self.step, 'type': 'validation_failure',
                                'record_ref': self.current_ref, 'reason': str(error)})
            self.fail_current(str(error))
            return
        payload = {key: value for key, value in self.current.items() if key != 'Leakage_Flag'}
        self.bus.send('Environment', 'Pressure Monitor', 'REQUEST', {'reading': payload}, self.step, self.current_ref)

    def complete_workflow(self, outcome):
        self.workflow_done = True
        self.outcomes.append({'record_ref': self.current_ref, 'outcome': outcome, 'step': self.step})
        self.record_report(outcome)

    def fail_current(self, reason):
        self.had_failure = True
        self.workflow_done = True
        self.outcomes.append({'record_ref': self.current_ref, 'outcome': 'Validation failed', 'reason': reason, 'step': self.step})

    def tick(self):
        if self.status != 'Running':
            return
        self.step += 1
        if self.current is None and not self.bus.queue:
            if self.cursor == len(self.readings):
                self.status = 'Failed' if self.had_failure else 'Completed'
                self.finished_at = utc_now()
                return
            self.current = self.readings[self.cursor]
            self.cursor += 1
            self.workflow_done = False
            self.location_content, self.assigned = {}, None
            self.deliver_reading()
        for name in ['Team A', 'Team B']:
            self.agents[name].tick()
        if self.bus.queue:
            message = self.bus.queue.popleft()
            try:
                self.agents[message.receiver].receive(message)
            except Exception as error:
                self.had_failure = True
                self.events.append({'step': self.step, 'type': 'execution_error', 'record_ref': message.record_ref,
                                    'agent': message.receiver, 'reason': f'{type(error).__name__}: {error}'})
                self.status, self.finished_at = 'Failed', utc_now()
                return
        if self.workflow_done and not self.bus.queue and not any(self.agents[name].remaining for name in ['Team A', 'Team B']):
            self.current = None
            if self.cursor == len(self.readings):
                self.status = 'Failed' if self.had_failure else 'Completed'
                self.finished_at = utc_now()

    def export(self):
        return {'run_id': self.run_id, 'metadata': self.metadata, 'configuration': asdict(self.config),
                'team_coordinate_references': self.positions, 'status': self.status, 'step': self.step,
                'created_at_runtime': self.created_at, 'started_at_runtime': self.started_at,
                'finished_at_runtime': self.finished_at, 'inputs': deepcopy(self.readings),
                'assessments': deepcopy(self.assessments), 'reports': deepcopy(self.reports),
                'outcomes': deepcopy(self.outcomes), 'team_attempts': deepcopy(self.team_attempts), 'events': deepcopy(self.events), 'messages': deepcopy(self.bus.log)}


def evaluate(frame, pressure_limit, flow_limit):
    predicted = (frame.Pressure_PSI < pressure_limit) & (frame.Flow_Rate_Lmin > flow_limit)
    labels = frame.Leakage_Flag == 1
    tp, tn = int((predicted & labels).sum()), int((~predicted & ~labels).sum())
    fp, fn = int((predicted & ~labels).sum()), int((~predicted & labels).sum())
    return {'accuracy': (tp+tn)/len(frame) if len(frame) else 0,
            'precision': tp/(tp+fp) if tp+fp else 0, 'recall': tp/(tp+fn) if tp+fn else 0,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
            'true_positive': tp, 'true_negative': tn, 'false_positive': fp, 'false_negative': fn}

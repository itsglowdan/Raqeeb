import unittest
from copy import deepcopy
from data_loader import load_data, validate_reading, custom_reading, filter_data, summarize
from simulation import Simulation, Configuration, evaluate

DATA = load_data()


def row(pressure=65, flow=80, ref='TEST-1'):
    reading = DATA.iloc[0].to_dict()
    reading.update(Pressure_PSI=pressure, Flow_Rate_Lmin=flow, record_ref=ref)
    return reading


def finish(system, approve=True, limit=300):
    system.run()
    for _ in range(limit):
        if system.waiting_approval:
            system.approve(approve)
        system.tick()
        if system.status != 'Running':
            return system
    raise AssertionError('Simulation did not terminate')


class DataTests(unittest.TestCase):
    def test_dataset_shape_precision(self):
        self.assertEqual(len(DATA), 5000)
        self.assertEqual(int(DATA.Leakage_Flag.sum()), 323)
        self.assertEqual(DATA.iloc[0].Pressure_PSI, 64.96714153011233)
        self.assertEqual(DATA.iloc[0].Latitude, 24.692188)
        self.assertEqual(DATA.iloc[0].record_ref, 'CSV-00001')

    def test_coordinate_associations_filters(self):
        subset = filter_data(DATA, 'Zone_1', 'Block_1', 'Pipe_1')
        self.assertGreater(subset.Latitude.nunique(), 1)
        for record in subset.to_dict('records'):
            original = DATA.iloc[record['original_index']-1]
            self.assertEqual(record['Latitude'], original.Latitude)
            self.assertEqual(record['Longitude'], original.Longitude)
        self.assertEqual(subset.original_index.tolist(), sorted(subset.original_index))

    def test_summary_empty(self):
        subset = filter_data(DATA, 'Zone_2', query='Pipe_1')
        self.assertEqual(summarize(subset)['flagged'], len(subset[subset.Leakage_Flag == 1]))
        self.assertEqual(summarize(filter_data(DATA, query='no-such-reference')), dict(readings=0, flagged=0, pressure=None, flow=None))

    def test_custom_unlabeled_exact_reference(self):
        reference = DATA.iloc[7].to_dict()
        custom = custom_reading(reference, 50, 110, 3, 1)
        self.assertNotIn('Leakage_Flag', custom)
        self.assertEqual(custom['coordinate_reference'], reference['record_ref'])
        self.assertEqual(custom['Latitude'], reference['Latitude'])
        self.assertEqual(custom['Longitude'], reference['Longitude'])

    def test_invalid_measurements(self):
        for value in [float('nan'), float('inf'), -1, None, 'bad']:
            invalid = row()
            invalid['Pressure_PSI'] = value
            with self.assertRaises(ValueError):
                validate_reading(invalid)
        invalid = row()
        invalid['Latitude'] = 91
        with self.assertRaises(ValueError):
            validate_reading(invalid)


class AgentTests(unittest.TestCase):
    def test_normal_acl(self):
        system = finish(Simulation([row()]))
        self.assertEqual(system.status, 'Completed')
        self.assertEqual(system.assessments[0]['assessment'], 'Normal')
        self.assertEqual(len(system.reports), 1)
        for message in system.bus.log:
            for field in ['sender', 'receiver', 'performative', 'ontology', 'conversation_id', 'message_id', 'runtime_timestamp', 'record_ref', 'step']:
                self.assertIn(field, message)
        self.assertEqual(len({m['message_id'] for m in system.bus.log}), len(system.bus.log))
        self.assertTrue(any(m['sender'] == 'Usage Monitor' and m['receiver'] == 'Pressure Monitor' for m in system.bus.log))

    def test_labels_never_enter_assessment(self):
        a, b = row(50, 110), row(50, 110)
        a['Leakage_Flag'], b['Leakage_Flag'] = 0, 1
        first, second = finish(Simulation([a])), finish(Simulation([b]))
        self.assertEqual(first.assessments, second.assessments)
        for message in first.bus.log:
            if message['sender'] != 'Environment':
                self.assertNotIn('Leakage_Flag', str(message['content']))

    def test_dual_rule_boundaries(self):
        for pressure, flow, expected in [(54, 90, 'Normal'), (53, 90, 'Suspected'), (54, 91, 'Suspected'), (53, 91, 'Leak indicated')]:
            self.assertEqual(finish(Simulation([row(pressure, flow)])).assessments[0]['assessment'], expected)

    def test_location_nearest_team(self):
        reading = row(50, 110)
        positions = {'Team A': {'record_ref': 'far', 'position': [25, 47]}, 'Team B': {'record_ref': 'same', 'position': [reading['Latitude'], reading['Longitude']]}}
        system = finish(Simulation([reading], team_positions=positions))
        self.assertEqual(system.assigned, 'Team B')
        self.assertEqual(system.reports[0]['location']['Latitude'], reading['Latitude'])
        self.assertEqual(system.reports[0]['location']['Longitude'], reading['Longitude'])
        self.assertTrue(any(m['performative'] == 'CFP' for m in system.bus.log))

    def test_major_approval_rejection(self):
        system = Simulation([row(35, 110)])
        system.run()
        for _ in range(10):
            system.tick()
        self.assertTrue(system.waiting_approval)
        self.assertFalse(any(m['performative'] == 'CFP' for m in system.bus.log))
        finish(system, approve=False)
        self.assertIn('rejected', system.outcomes[0]['outcome'])

    def test_pause_resume_no_duplicate(self):
        system = Simulation([row(50, 110), row(ref='TEST-2')])
        system.run()
        for _ in range(12):
            system.tick()
        system.pause()
        before = system.export()
        for _ in range(30):
            system.tick()
        self.assertEqual(before, system.export())
        finish(system)
        self.assertEqual(system.cursor, 2)
        self.assertEqual(len(system.assessments), 2)
        self.assertEqual(system.status, 'Completed')
        final = system.export()
        system.run()
        system.tick()
        self.assertEqual(final, system.export())

    def test_team_failure_reassignment(self):
        system = finish(Simulation([row(50, 110)], Configuration(fail_team_a=True)))
        self.assertEqual(system.assigned, 'Team B')
        self.assertEqual(system.status, 'Completed')
        self.assertEqual(sum(e['type'] == 'team_failure' for e in system.events), 1)
        self.assertIn('Team B', system.outcomes[0]['outcome'])

    def test_no_team_explicit(self):
        system = finish(Simulation([row(50, 110)], Configuration(team_a_available=False, team_b_available=False)))
        self.assertIn('unresolved', system.outcomes[0]['outcome'])
        self.assertFalse(any(m['performative'] == 'ACCEPT' for m in system.bus.log))

    def test_reporting_refusal_bounded(self):
        system = finish(Simulation([row()], Configuration(reporting_unavailable=True, timeout_steps=6, retries=2)))
        self.assertEqual(len([m for m in system.bus.log if m['receiver'] == 'Reporting Agent']), 3)
        self.assertEqual(system.status, 'Failed')
        self.assertEqual(len(system.reports), 0)
        self.assertTrue(any(e['type'] == 'report_failed' for e in system.events))

    def test_silent_timeout_bounded(self):
        system = finish(Simulation([row()], Configuration(reporting_silent=True, timeout_steps=5, retries=1)))
        self.assertEqual(system.status, 'Failed')
        self.assertEqual(sum(e['type'] == 'report_retry' for e in system.events), 1)

    def test_restore_before_retry(self):
        system = Simulation([row()], Configuration(reporting_unavailable=True, timeout_steps=10))
        system.run()
        for _ in range(8):
            system.tick()
        system.pause()
        system.restore('Reporting Agent')
        finish(system)
        self.assertEqual(system.status, 'Completed')
        self.assertEqual(len(system.reports), 1)

    def test_restore_lost_ack_without_duplicate_report(self):
        system = Simulation([row()], Configuration(reporting_silent=True, timeout_steps=12))
        system.run()
        for _ in range(8):
            system.tick()
        self.assertEqual(len(system.reports), 1)
        system.pause()
        system.restore('Reporting Agent')
        finish(system)
        self.assertEqual(system.status, 'Completed')
        self.assertEqual(len(system.reports), 1)

    def test_duplicate_record_refs_rejected(self):
        with self.assertRaises(ValueError):
            Simulation([row(), row()])

    def test_idempotent_reporting(self):
        system = finish(Simulation([row(50, 110)], Configuration(timeout_steps=1, retries=5)))
        self.assertEqual(len({r['task_ref'] for r in system.reports}), len(system.reports))

    def test_invalid_runtime_explicit(self):
        reading = row()
        reading['Flow_Rate_Lmin'] = float('nan')
        system = finish(Simulation([reading]))
        self.assertEqual(system.status, 'Failed')
        self.assertEqual(len(system.assessments), 0)
        self.assertEqual(system.events[0]['type'], 'validation_failure')

    def test_isolated_runs(self):
        reading = row(50, 110)
        original = deepcopy(reading)
        first, second = finish(Simulation([reading])), Simulation([reading])
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(second.bus.log, [])
        self.assertEqual(reading, original)

    def test_configuration_effect(self):
        for config in [dict(major_limit=60), dict(retries=-1), dict(timeout_steps=0), dict(flow_limit=float('nan'))]:
            with self.assertRaises(ValueError):
                Configuration(**config)
        system = finish(Simulation([row(65, 80)], Configuration(pressure_limit=70, flow_limit=75)))
        self.assertEqual(system.assessments[0]['assessment'], 'Leak indicated')

    def test_evaluation(self):
        scores = evaluate(DATA, 54, 90)
        self.assertEqual([scores[k] for k in ['true_positive', 'false_positive', 'false_negative', 'true_negative']], [323, 34, 0, 4643])


if __name__ == '__main__':
    unittest.main()

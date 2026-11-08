import unittest

from manual_input import make_reading
from monitoring import ContinuousMonitor


def finish(monitor):
    monitor.running = True
    for _ in range(200):
        monitor.advance()
        if monitor.finished:
            return
    raise AssertionError('Manual sequence did not finish')


class ManualInputTests(unittest.TestCase):
    def test_default_normal_reading(self):
        row = make_reading(65, 80, 'Zone_1', 'Block_1', 'Pipe_1')
        self.assertNotIn('Leakage_Flag', row)
        monitor = ContinuousMonitor([row])
        finish(monitor)
        self.assertEqual(monitor.processed, 1)
        self.assertEqual(monitor.confirmed, 0)
        self.assertEqual(monitor.regions['Zone_1']['classification'], 'Normal')

    def test_manual_minor_leak_is_detected_and_repaired(self):
        monitor = ContinuousMonitor([make_reading(50, 110, 'Zone_1', 'Block_1', 'Pipe_1')])
        finish(monitor)
        self.assertEqual(monitor.confirmed, 1)
        self.assertEqual(monitor.completed, 1)

    def test_manual_major_leak_waits_and_recovers_from_failure(self):
        monitor = ContinuousMonitor([make_reading(35, 110, 'Zone_1', 'Block_1', 'Pipe_1')], fail_first=True)
        finish(monitor)
        self.assertTrue(monitor.regions['Zone_1']['active']['sim'].waiting_approval)
        self.assertEqual(monitor.completed, 0)
        monitor.approve('Zone_1', True)
        finish(monitor)
        self.assertEqual(monitor.completed, 1)
        self.assertEqual(monitor.failure_count, 1)
        self.assertEqual(monitor.incidents[0]['sim'].assigned_team, 'Team B')

    def test_sequence_preserves_order_and_stops(self):
        rows = [make_reading(p, f, 'Zone_1', 'Block_1', 'Pipe_1')
                for p, f in [(65, 80), (50, 110), (65, 80)]]
        monitor = ContinuousMonitor(rows, interval=0.5)
        finish(monitor)
        self.assertEqual(monitor.processed, 3)
        self.assertEqual([(r['Pressure'], r['Flow_Rate']) for r in monitor.history],
                         [(65, 80), (50, 110), (65, 80)])
        tick = monitor.tick
        monitor.advance()
        self.assertEqual(monitor.tick, tick)

    def test_invalid_numbers_and_locations_rejected(self):
        for value in [-1, None, float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                make_reading(value, 80, 'Zone_1', 'Block_1', 'Pipe_1')
            with self.assertRaises(ValueError):
                make_reading(65, value, 'Zone_1', 'Block_1', 'Pipe_1')
        for zone, block, pipe in [('Zone_6', 'Block_1', 'Pipe_1'),
                                   ('Zone_1', 'Block_0', 'Pipe_1'),
                                   ('Zone_1', 'Block_1', 'Pipe_6')]:
            with self.assertRaises(ValueError):
                make_reading(65, 80, zone, block, pipe)


    def test_individual_team_availability(self):
        row = make_reading(50, 110, 'Zone_1', 'Block_1', 'Pipe_1')
        monitor = ContinuousMonitor([row], team_a_available=False, team_b_available=True)
        finish(monitor)
        self.assertEqual(monitor.completed, 1)
        self.assertEqual(monitor.incidents[0]['sim'].assigned_team, 'Team B')
        monitor = ContinuousMonitor([row], team_a_available=False, team_b_available=False)
        finish(monitor)
        self.assertEqual(monitor.completed, 0)
        self.assertIn('No available team', monitor.incidents[0]['status'])


if __name__ == '__main__':
    unittest.main()

import unittest
from data_loader import load_data
from monitoring import ContinuousMonitor, display_reading


def reading(zone='Zone_1', pressure=60, flow=80, pipe='Pipe_1'):
    return {'Pressure': pressure, 'Flow_Rate': flow, 'Zone': zone, 'Block': 'Block_1',
            'Pipe': pipe, 'Latitude': 25.1, 'Longitude': 55.2}


def run(monitor, steps):
    monitor.running = True
    for _ in range(steps):
        monitor.advance()


def finish(monitor, approve=False):
    monitor.running = True
    for _ in range(25000):
        monitor.advance()
        if approve:
            for zone, city in monitor.regions.items():
                if city['active'] and city['active']['sim'].waiting_approval:
                    monitor.approve(zone, True)
        if monitor.finished:
            return
    raise AssertionError('Monitoring did not finish')


class MonitoringTests(unittest.TestCase):
    def test_every_reading_once_then_stops(self):
        monitor = ContinuousMonitor([reading(), reading('Zone_2')], interval=0.5)
        finish(monitor)
        self.assertFalse(monitor.running)
        self.assertEqual(monitor.observed, 2)
        self.assertEqual(monitor.processed, 2)
        self.assertEqual([x['row'] for x in monitor.history], [1, 2])
        tick = monitor.tick
        run(monitor, 10)
        self.assertEqual(monitor.tick, tick)
        self.assertEqual(monitor.observed, 2)

    def test_starting_row_does_not_wrap(self):
        monitor = ContinuousMonitor([reading() for _ in range(4)], start_index=2)
        finish(monitor)
        self.assertEqual(monitor.processed, 2)
        self.assertEqual([x['row'] for x in monitor.history], [3, 4])

    def test_pause_and_resume_keep_position(self):
        monitor = ContinuousMonitor([reading() for _ in range(10)], interval=0.5)
        run(monitor, 4)
        monitor.running = False
        before = (monitor.tick, monitor.observed, monitor.processed, monitor.total_messages)
        for _ in range(10):
            monitor.advance()
        self.assertEqual(before, (monitor.tick, monitor.observed, monitor.processed, monitor.total_messages))
        finish(monitor)
        self.assertEqual(monitor.processed, 10)
        self.assertEqual([x['row'] for x in monitor.history], list(range(1, 11)))

    def test_agents_act_in_separate_visible_steps(self):
        monitor = ContinuousMonitor([reading()], interval=0.5)
        run(monitor, 1)
        self.assertEqual(monitor.processed, 0)
        self.assertEqual(monitor.activity, [('Zone_1', 'Pressure Monitor')])
        self.assertEqual(monitor.agent_states('Zone_1')['Pressure Monitor'], 'Checking pressure')
        run(monitor, 1)
        self.assertEqual(monitor.activity, [('Zone_1', 'Usage Monitor')])
        self.assertEqual(monitor.processed, 0)
        run(monitor, 1)
        self.assertEqual(monitor.activity, [('Zone_1', 'Pressure Monitor')])
        self.assertEqual(monitor.processed, 1)
        self.assertEqual(len(monitor.deliveries), 3)
        self.assertTrue(monitor.finished)

    def test_approval_does_not_block_other_zones(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110), reading('Zone_4')], interval=0.5)
        finish(monitor)
        self.assertEqual(monitor.processed, 2)
        self.assertTrue(monitor.regions['Zone_1']['active']['sim'].waiting_approval)
        self.assertEqual(monitor.regions['Zone_4']['classification'], 'Normal')
        monitor.approve('Zone_1', True)
        self.assertTrue(monitor.running)
        finish(monitor)
        self.assertEqual(monitor.completed, 1)
        self.assertEqual(monitor.observed, 2)

    def test_duplicate_open_pipe_is_merged(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110) for _ in range(10)], interval=0.5)
        finish(monitor)
        self.assertEqual(monitor.confirmed, 1)
        self.assertEqual(len(monitor.open_incidents), 1)
        self.assertTrue(any(m.get('cancelled') for m in monitor.messages))

    def test_failure_recovery_keeps_failed_team_unavailable(self):
        rows = [reading(pressure=50, flow=110), reading(pressure=50, flow=110, pipe='Pipe_2')]
        monitor = ContinuousMonitor(rows, interval=5, fail_first=True)
        finish(monitor)
        self.assertEqual(monitor.completed, 2)
        self.assertEqual(monitor.failure_count, 1)
        self.assertTrue(monitor.fleet['Team A']['failed'])
        self.assertTrue(all(item['sim'].assigned_team == 'Team B' for item in monitor.incidents))
        self.assertEqual(len(monitor.fleet), 2)

    def test_rejected_and_unavailable_incidents_remain_open(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110)])
        finish(monitor)
        monitor.approve('Zone_1', False)
        finish(monitor)
        self.assertEqual(monitor.completed, 0)
        self.assertIn('rejected', monitor.zone_status('Zone_1')[1])
        monitor = ContinuousMonitor([reading(pressure=50, flow=110)], unavailable=True)
        finish(monitor)
        self.assertIn('No available team', monitor.zone_status('Zone_1')[1])

    def test_later_normal_reading_does_not_hide_open_leak(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110), reading()], interval=0.5)
        finish(monitor)
        self.assertEqual(monitor.regions['Zone_1']['classification'], 'Normal')
        self.assertEqual(monitor.zone_status('Zone_1')[0], 'Confirmed leak')

    def test_saudi_positions_fixed_and_values_unchanged(self):
        rows, _ = load_data()
        positions = {}
        for row in rows:
            mapped = display_reading(row)
            self.assertEqual(mapped['Pressure'], row['Pressure'])
            self.assertEqual(mapped['Flow_Rate'], row['Flow_Rate'])
            self.assertTrue(24.6 < mapped['Latitude'] < 24.9 and 46.5 < mapped['Longitude'] < 46.9)
            key = tuple(row[k] for k in ['Zone', 'Block', 'Pipe'])
            point = mapped['Latitude'], mapped['Longitude']
            if key in positions:
                self.assertEqual(positions[key], point)
            positions[key] = point
        self.assertEqual(len(set(positions.values())), 125)

    def test_full_dataset_finishes_with_bounded_logs(self):
        rows, _ = load_data()
        monitor = ContinuousMonitor(rows, interval=0.5, fail_first=True)
        finish(monitor, approve=True)
        self.assertEqual(monitor.processed, 5000)
        self.assertEqual(monitor.observed, 5000)
        self.assertEqual(monitor.error_count, 0)
        self.assertEqual(monitor.dropped, 0)
        self.assertEqual(len(monitor.history), 600)
        self.assertEqual(len(monitor.messages), 1500)
        self.assertEqual(len(monitor.traces), 1500)
        self.assertTrue(all(t['duration_ms'] >= 0 for t in monitor.traces))

    def test_execution_error_does_not_block_remaining_readings(self):
        monitor = ContinuousMonitor([reading(pressure=50, flow=110), reading('Zone_4')])
        run(monitor, 3)
        sim = monitor.regions['Zone_1']['active']['sim']
        def broken(message):
            raise RuntimeError('Test failure')
        sim.agents['Dispatch'].receive = broken
        finish(monitor)
        self.assertEqual(monitor.error_count, 1)
        self.assertEqual(monitor.processed, 2)
        self.assertEqual(monitor.completed, 0)


    def test_shared_fleet_never_double_booked_and_queues_busy_tasks(self):
        rows = [reading(f'Zone_{i}', pressure=50, flow=110) for i in range(1, 6)]
        monitor = ContinuousMonitor(rows, interval=0.5, repair_ticks=20)
        monitor.running = True
        max_busy = 0
        saw_wait = False
        for _ in range(1000):
            monitor.advance()
            booked = [name for name, team in monitor.fleet.items() if team['owner']]
            max_busy = max(max_busy, len(booked))
            self.assertLessEqual(len(booked), 2)
            active_names = []
            for region in monitor.regions.values():
                if region['active']:
                    incident = region['active']
                    saw_wait |= incident['status'] == 'Waiting for team'
                    for team in incident['sim'].teams:
                        if team.remaining:
                            active_names.append(team.name)
                            self.assertEqual(monitor.fleet[team.name]['owner'], incident['id'])
            self.assertEqual(len(active_names), len(set(active_names)))
            if monitor.finished:
                break
        self.assertTrue(monitor.finished)
        self.assertEqual(monitor.completed, 5)
        self.assertEqual(max_busy, 2)
        self.assertTrue(saw_wait)
        self.assertTrue(all(team['owner'] is None for team in monitor.fleet.values()))

    def test_stale_offer_cannot_reserve_already_booked_team(self):
        monitor = ContinuousMonitor([reading()])
        from simulation import Simulation
        first = Simulation(display_reading(reading()))
        first.conversation_id = 'first'
        second = Simulation(display_reading(reading('Zone_2')))
        second.conversation_id = 'second'
        self.assertTrue(monitor.reserve_team(first, 'Team A'))
        self.assertFalse(monitor.reserve_team(second, 'Team A'))
        self.assertTrue(monitor.reserve_team(second, 'Team B'))
        self.assertEqual(monitor.fleet['Team A']['owner'], 'first')
        self.assertEqual(monitor.fleet['Team B']['owner'], 'second')


if __name__ == '__main__':
    unittest.main()

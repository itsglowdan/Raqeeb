import unittest

from data_loader import load_data
from monitoring import ContinuousMonitor, display_reading


def reading(zone="Zone_1", pressure=60, flow=80, pipe="Pipe_1"):
    return {"Pressure": pressure, "Flow_Rate": flow, "Zone": zone, "Block": "Block_1",
            "Pipe": pipe, "Latitude": 25.1, "Longitude": 55.2}


def run(monitor, steps):
    monitor.running = True
    for _ in range(steps):
        monitor.advance()


class MonitoringTests(unittest.TestCase):
    def test_continues_and_replays_dataset(self):
        monitor = ContinuousMonitor([reading(), reading("Zone_2")], interval=0.5)
        run(monitor, 10)
        self.assertTrue(monitor.running)
        self.assertEqual(monitor.observed, 10)
        self.assertEqual(monitor.cycle, 5)
        self.assertEqual([x["row"] for x in monitor.history], [1, 2] * 5)
        self.assertEqual(monitor.confirmed, 0)

    def test_pause_freezes_everything_and_manual_is_one_tick(self):
        monitor = ContinuousMonitor([reading(pressure=50, flow=110)], interval=0.5)
        run(monitor, 4)
        monitor.running = False
        before = (monitor.tick, monitor.observed, monitor.total_cost, monitor.total_messages)
        for _ in range(10):
            monitor.advance()
        self.assertEqual(before, (monitor.tick, monitor.observed, monitor.total_cost, monitor.total_messages))
        monitor.advance(manual=True)
        self.assertEqual(monitor.tick, before[0] + 1)
        self.assertFalse(monitor.running)

    def test_approval_does_not_block_other_cities(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110), reading("Zone_4")], interval=0.5)
        run(monitor, 20)
        self.assertTrue(monitor.cities["Zone_1"]["active"]["sim"].waiting_approval)
        self.assertIsNotNone(monitor.cities["Zone_4"]["latest"])
        self.assertEqual(monitor.observed, 20)
        monitor.approve("Zone_1", True)
        run(monitor, 25)
        self.assertGreater(monitor.completed, 0)

    def test_duplicate_open_pipe_is_not_dispatched_twice(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110)], interval=0.5)
        run(monitor, 20)
        self.assertEqual(monitor.confirmed, 1)
        self.assertEqual(len(monitor.open_incidents), 1)
        self.assertEqual(len(monitor.cities["Zone_1"]["pending"]), 0)
        self.assertTrue(any(m.get("cancelled") for m in monitor.messages))

    def test_failure_recovery_and_cost_not_double_counted(self):
        monitor = ContinuousMonitor([reading(pressure=50, flow=110)], interval=5,
                                    fail_first=True, base_cost=100, cost_per_km=0)
        run(monitor, 50)
        self.assertGreater(monitor.completed, 0)
        self.assertEqual(monitor.failure_count, 1)
        starts = sum(m["content"].get("state") == "accepted" for m in monitor.messages)
        self.assertEqual(monitor.total_cost, starts * 100)
        self.assertTrue(monitor.cities["Zone_1"]["teams"][0]["failed"])
        self.assertTrue(all(item["sim"].assigned_team == "Team B" for item in monitor.incidents
                            if item["status"] == "Completed"))

    def test_rejection_and_unavailable_teams_remain_unresolved(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110)], interval=0.5)
        run(monitor, 5)
        monitor.approve("Zone_1", False)
        run(monitor, 20)
        self.assertEqual(monitor.completed, 0)
        self.assertEqual(len(monitor.open_incidents), 1)
        self.assertIn("rejected", monitor.city_status("Zone_1")[1])
        self.assertEqual(monitor.total_cost, 0)
        monitor = ContinuousMonitor([reading(pressure=50, flow=110)], unavailable=True)
        run(monitor, 30)
        self.assertIn("No available team", monitor.city_status("Zone_1")[1])
        self.assertEqual(monitor.completed, 0)

    def test_new_normal_reading_does_not_hide_open_leak(self):
        monitor = ContinuousMonitor([reading(pressure=35, flow=110), reading()], interval=0.5)
        run(monitor, 10)
        self.assertEqual(monitor.cities["Zone_1"]["classification"], "Normal")
        self.assertEqual(monitor.city_status("Zone_1")[0], "Confirmed leak")

    def test_fleet_positions_are_carried_forward(self):
        monitor = ContinuousMonitor([reading(pressure=50, flow=110)], interval=5)
        run(monitor, 19)
        completed = [item for item in monitor.incidents if item["status"] == "Completed"]
        self.assertTrue(completed)
        first = completed[0]["sim"]
        position = first.agents[first.assigned_team].position
        self.assertEqual(position, (first.reading["Latitude"], first.reading["Longitude"]))
        run(monitor, 2)
        active = monitor.cities["Zone_1"]["active"]
        self.assertIsNotNone(active)
        self.assertEqual(active["sim"].agents[first.assigned_team].position, position)

    def test_saudi_locations_fixed_and_values_unchanged(self):
        rows, _ = load_data()
        positions = {}
        original = dict(rows[0])
        for row in rows:
            mapped = display_reading(row)
            self.assertEqual(mapped["Pressure"], row["Pressure"])
            self.assertEqual(mapped["Flow_Rate"], row["Flow_Rate"])
            self.assertTrue(18 < mapped["Latitude"] < 27)
            self.assertTrue(39 < mapped["Longitude"] < 51)
            key = tuple(row[k] for k in ["Zone", "Block", "Pipe"])
            point = mapped["Latitude"], mapped["Longitude"]
            if key in positions:
                self.assertEqual(positions[key], point)
            positions[key] = point
        self.assertEqual(len(set(positions.values())), 125)
        self.assertEqual(rows[0], original)

    def test_execution_traces_and_bounded_history(self):
        monitor = ContinuousMonitor([reading()], interval=0.5)
        run(monitor, 700)
        self.assertEqual(len(monitor.history), 600)
        self.assertEqual(len(monitor.performance), 600)
        self.assertEqual(len(monitor.messages), 1500)
        self.assertEqual(len(monitor.traces), 1500)
        self.assertEqual(monitor.total_messages, 2100)
        self.assertEqual(monitor.total_calls, 2100)
        self.assertEqual(monitor.error_count, 0)
        self.assertTrue(all(x["duration_ms"] >= 0 for x in monitor.traces))
        self.assertEqual(len({m["conversation_id"] for m in monitor.messages}), 500)

    def test_execution_error_does_not_stop_stream(self):
        monitor = ContinuousMonitor([reading(pressure=50, flow=110), reading("Zone_4")])
        run(monitor, 1)
        sim = monitor.cities["Zone_1"]["active"]["sim"]
        def broken(message):
            raise RuntimeError("Test execution failure")
        sim.agents["Dispatch"].receive = broken
        run(monitor, 20)
        self.assertEqual(monitor.error_count, 1)
        self.assertIsNotNone(monitor.cities["Zone_4"]["latest"])
        self.assertEqual(monitor.completed, 0)
        self.assertTrue(monitor.running)


if __name__ == "__main__":
    unittest.main()

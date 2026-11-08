import unittest

from agents import distance_km
from data_loader import load_data
from simulation import Simulation, evaluate, scenario_reading


def finish(sim):
    for _ in range(200):
        if not sim.active:
            return
        sim.step()
    raise AssertionError("Simulation did not stop")


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readings, cls.labels = load_data()

    def example(self, name, **settings):
        _, reading = scenario_reading(self.readings, name)
        sim = Simulation(reading, **settings)
        sim.start()
        return sim

    def test_normal_reading_does_not_dispatch(self):
        sim = self.example("Normal")
        finish(sim)
        self.assertFalse(sim.detected)
        self.assertFalse(any(m["performative"] == "CFP" for m in sim.messages))

    def test_minor_leak_uses_closest_team(self):
        sim = self.example("Minor leak")
        finish(sim)
        self.assertTrue(sim.detected and sim.repaired)
        self.assertEqual(sim.assigned_team, "Team A")
        self.assertFalse(sim.waiting_approval)

    def test_major_leak_cannot_dispatch_without_approval(self):
        sim = self.example("Major leak + team failure")
        finish(sim)
        self.assertTrue(sim.waiting_approval)
        self.assertIsNone(sim.assigned_team)
        self.assertFalse(sim.repaired)
        sim.approve(True)
        finish(sim)
        self.assertTrue(sim.repaired)

    def test_failure_reassigns_to_other_team(self):
        sim = self.example("Major leak + team failure", fail_first=True)
        finish(sim)
        sim.approve(True)
        finish(sim)
        self.assertTrue(sim.teams[0].failed)
        self.assertEqual(sim.assigned_team, "Team B")
        self.assertTrue(sim.repaired)
        self.assertEqual(sum(m["performative"] == "ACCEPT" and m["receiver"] in ("Team A", "Team B")
                             for m in sim.messages), 2)

    def test_supervisor_rejection_leaves_leak_unresolved(self):
        sim = self.example("Major leak + team failure")
        finish(sim)
        sim.approve(False)
        finish(sim)
        self.assertFalse(sim.repaired)
        self.assertIsNone(sim.assigned_team)
        self.assertIn("rejected", sim.result)

    def test_no_available_teams_stops_cleanly(self):
        sim = self.example("Minor leak", unavailable=True)
        finish(sim)
        self.assertIn("No available team", sim.result)
        self.assertFalse(sim.repaired)

    def test_one_abnormal_sensor_is_not_enough(self):
        for pressure, flow in [(35, 70), (65, 110)]:
            reading = dict(self.readings[0], Pressure=pressure, Flow_Rate=flow)
            sim = Simulation(reading)
            sim.start()
            finish(sim)
            self.assertFalse(sim.detected)
            self.assertEqual(sim.result, "Unconfirmed anomaly")

    def test_boundaries_and_changed_limits(self):
        reading = dict(self.readings[0], Pressure=54, Flow_Rate=90)
        sim = Simulation(reading)
        sim.start()
        finish(sim)
        self.assertFalse(sim.detected)
        sim = Simulation(reading, pressure_limit=55, flow_limit=89)
        sim.start()
        finish(sim)
        self.assertTrue(sim.repaired)

    def test_labels_are_separate_and_metrics_include_false_positives(self):
        self.assertTrue(all("Leakage_Flag" not in row for row in self.readings))
        scores = evaluate(self.readings, self.labels)
        self.assertEqual(sum(scores[k] for k in ("TP", "FP", "TN", "FN")), 5000)
        self.assertGreater(scores["FP"], 0)

    def test_distance(self):
        self.assertEqual(distance_km((25, 55), (25, 55)), 0)
        self.assertAlmostEqual(distance_km((0, 0), (1, 0)), 111.195, places=2)


    def test_demo_leaks_match_reference_labels(self):
        for name in ("Minor leak", "Major leak + team failure"):
            index, _ = scenario_reading(self.readings, name)
            self.assertEqual(self.labels[index], 1)


if __name__ == "__main__":
    unittest.main()

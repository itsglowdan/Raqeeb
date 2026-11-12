import unittest
from data_loader import load_data
from controls import automatic_inputs, automatic_team_positions, assessment_status
from simulation import Simulation


class AutomaticControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()

    def test_dataset_automatically_preserves_all_original_records(self):
        readings = automatic_inputs(self.data, 'Dataset Readings')
        self.assertEqual(len(readings), 5000)
        self.assertEqual([r['record_ref'] for r in readings], self.data.record_ref.tolist())
        self.assertEqual(readings[10]['Latitude'], self.data.iloc[10].Latitude)

    def test_custom_automatically_updates_not_appends(self):
        self.assertEqual(automatic_inputs(self.data, 'Custom Readings'), [])
        first = automatic_inputs(self.data, 'Custom Readings', 65, 80)
        second = automatic_inputs(self.data, 'Custom Readings', 50, 110)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]['coordinate_reference'], self.data.iloc[0].record_ref)
        self.assertEqual(second[0]['Latitude'], self.data.iloc[0].Latitude)
        self.assertNotIn('Leakage_Flag', second[0])
        self.assertEqual(second[0]['Vibration_mms'], self.data.iloc[0].Vibration_mms)
        self.assertNotEqual(first[0]['Pressure_PSI'], second[0]['Pressure_PSI'])

    def test_teams_use_exact_automatic_dataset_locations(self):
        positions = automatic_team_positions(self.data)
        self.assertNotEqual(positions['Team A']['record_ref'], positions['Team B']['record_ref'])
        for team in positions.values():
            row = self.data[self.data.record_ref == team['record_ref']].iloc[0]
            self.assertEqual(team['position'], [row.Latitude, row.Longitude])

    def test_status_is_assessment_not_execution_state(self):
        self.assertEqual(assessment_status(None)[1], 'waiting')
        for pressure, flow, expected in [(65,80,'normal'),(50,80,'suspected'),(50,110,'leak')]:
            system = Simulation(automatic_inputs(self.data, 'Custom Readings', pressure, flow))
            system.run()
            system.tick()
            self.assertEqual(assessment_status(system)[1], 'checking')
            while not system.assessments:
                system.tick()
            system.pause()
            self.assertEqual(assessment_status(system)[1], expected)
            self.assertNotIn('Paused', assessment_status(system)[0])


if __name__ == '__main__':
    unittest.main()

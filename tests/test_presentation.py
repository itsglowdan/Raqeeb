import unittest
import pandas as pd
from simulation import Simulation
from controls import automatic_inputs
from data_loader import load_data
from presentation import network_summary, observed_readings, line_chart, outcome_history
from i18n import tr


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_data()

    def test_network_does_not_hide_alert_when_other_zone_is_normal(self):
        rows=self.data.iloc[:2].to_dict('records')
        rows[0].update(Pressure_PSI=50,Flow_Rate_Lmin=110,Zone='Zone_4')
        rows[1].update(Pressure_PSI=65,Flow_Rate_Lmin=80,Zone='Zone_3')
        run=Simulation(rows)
        run.run()
        for _ in range(100):
            run.tick()
            if run.status=='Completed': break
        status,color,issues=network_summary(run)
        self.assertEqual(run.assessments[-1]['assessment'],'Normal')
        self.assertEqual(color,'leak')
        self.assertEqual([a['Zone'] for a in issues],['Zone_4'])
        self.assertEqual(issues[0]['Latitude'],rows[0]['Latitude'])

    def test_all_processed_zones_remain_in_order(self):
        run=Simulation(self.data.iloc[:3].to_dict('records'))
        run.cursor=3
        observed=observed_readings(run)
        self.assertEqual(observed.record_ref.tolist(),self.data.record_ref.iloc[:3].tolist())
        self.assertEqual(observed.Zone.tolist(),self.data.Zone.iloc[:3].tolist())
        self.assertEqual(observed.reading_order.tolist(),[1,2,3])

    def test_waiting_and_suspected_are_separate(self):
        self.assertEqual(network_summary(None)[0],'Awaiting readings')
        run=Simulation(automatic_inputs(self.data,'Custom Readings',50,80))
        run.run()
        for _ in range(10):run.tick()
        self.assertEqual(network_summary(run)[1],'suspected')

    def test_chart_uses_lines_and_integer_axis_without_altering_data(self):
        frame=self.data.head(3).copy()
        frame['reading_order']=[1,2,3]
        original=frame.copy(deep=True)
        spec=line_chart(frame,'Pressure_PSI','Pressure',54,'en').to_dict()
        self.assertEqual(spec['layer'][0]['mark']['type'],'line')
        self.assertNotIn('point',spec['layer'][0]['mark'])
        self.assertEqual(spec['layer'][0]['encoding']['x']['axis']['format'],'d')
        pd.testing.assert_frame_equal(frame,original)

    def test_counter_history_tracks_actual_messages_not_fake_measurements(self):
        run=Simulation(automatic_inputs(self.data,'Custom Readings',65,80))
        run.run()
        for _ in range(15):run.tick()
        history=outcome_history(run)
        self.assertEqual(history.leaks.tolist(),[0]*len(history))
        self.assertEqual(history.completed.tolist(),[0]*len(history))
        self.assertEqual(len(run.readings),1)

    def test_translation_preserves_protocol_identifiers(self):
        self.assertEqual(tr('Zone_4','ar'),'Zone_4')
        self.assertEqual(tr('REQUEST','ar'),'REQUEST')
        self.assertEqual(tr('Run','en'),'Run')
        self.assertEqual(tr('Run','ar'),'تشغيل')
        self.assertIn('الفريق ب',tr('Simulated task completed by Team B','ar'))
        self.assertNotEqual(tr('Leaks indicated by detection rules','ar'),'Leaks indicated by detection rules')
        self.assertIn('أقل من',tr('Pressure 50.00 < 54.0 PSI','ar'))
        self.assertIn('أعلى من',tr('Flow 110.00 > 90.0 L/min','ar'))


if __name__=='__main__':unittest.main()

import unittest
from data_loader import load_data
from simulation import Simulation, Configuration
from presentation import incident_rows, message_rows

DATA=load_data()


def reading(ref='TEST-1',pressure=50,flow=110):
    row=DATA.iloc[0].to_dict()
    row.update(record_ref=ref,Pressure_PSI=pressure,Flow_Rate_Lmin=flow)
    return row


def positions(nearest):
    row=reading()
    near=[row['Latitude'],row['Longitude']]
    far=[DATA.iloc[-1].Latitude,DATA.iloc[-1].Longitude]
    return {name:{'record_ref':DATA.iloc[0 if name==nearest else -1].record_ref,
                  'position':near if name==nearest else far} for name in ['Team A','Team B']}


def finish(run):
    run.run()
    for _ in range(200):
        run.tick()
        if run.status in ['Completed','Failed']:return run
    raise AssertionError('Workflow did not terminate')


class TeamAttemptTests(unittest.TestCase):
    def test_b_failure_reassigns_to_a_and_keeps_both_attempts(self):
        run=finish(Simulation([reading()],Configuration(fail_team_b=True),team_positions=positions('Team B')))
        self.assertEqual(run.status,'Completed')
        self.assertEqual([(a['team'],a['state']) for a in run.team_attempts],[('Team B','Failed'),('Team A','Completed')])
        self.assertEqual(run.team_attempts[1]['reassigned_from'],'Team B')
        assignment_ids={a['assignment_id'] for a in run.team_attempts}
        for message in run.bus.log:
            if message['performative']=='ACCEPT' or message['content'].get('state') in ['failed','completed','accepted']:
                self.assertIn(message['task_ref'],assignment_ids)
        self.assertEqual(run.events[0]['agent'],'Team B')
        rows=incident_rows(run)
        self.assertEqual(rows.assigned_team.tolist(),['Team B','Team A'])
        self.assertEqual(rows.task_status.tolist(),['Failed','Completed'])
        self.assertTrue(all('Team A' in r for r in rows.incident_result))

    def test_both_fail_then_terminate_unresolved(self):
        run=finish(Simulation([reading()],Configuration(fail_team_a=True,fail_team_b=True)))
        self.assertEqual(len(run.team_attempts),2)
        self.assertEqual([a['state'] for a in run.team_attempts],['Failed','Failed'])
        self.assertEqual(sum(e['type']=='team_failure' for e in run.events),2)
        self.assertTrue(all('unresolved' in r for r in incident_rows(run).incident_result))
        self.assertLess(run.step,50)

    def test_b_does_not_fail_unless_assigned(self):
        run=finish(Simulation([reading()],Configuration(fail_team_b=True),team_positions=positions('Team A')))
        self.assertFalse(run.events)
        self.assertNotIn('Team B',run.team_faults_consumed)
        self.assertEqual(run.team_attempts[0]['team'],'Team A')

    def test_restored_b_fails_only_once_per_run(self):
        run=Simulation([reading(),reading('TEST-2')],Configuration(fail_team_b=True),team_positions=positions('Team B'))
        run.run()
        while not run.agents['Team B'].failure:run.tick()
        run.pause()
        run.restore('Team B')
        finish(run)
        self.assertEqual(run.status,'Completed')
        self.assertEqual(sum(e['type']=='team_failure' for e in run.events),1)
        self.assertEqual([a['state'] for a in run.team_attempts],['Failed','Completed','Completed'])

    def test_incident_team_persists_after_later_normal_reading(self):
        run=finish(Simulation([reading(),reading('TEST-2',65,80)]))
        self.assertIsNone(run.assigned)
        rows=incident_rows(run)
        self.assertEqual(rows.record_ref.tolist(),['TEST-1'])
        self.assertEqual(rows.assigned_team.tolist(),['Team A'])
        self.assertEqual(rows.task_status.tolist(),['Completed'])
        self.assertEqual(run.export()['team_attempts'],run.team_attempts)

    def test_pending_assignment_not_reported_completed(self):
        run=Simulation([reading()]);run.run()
        while not run.team_attempts:run.tick()
        run.pause()
        row=incident_rows(run).iloc[0]
        self.assertEqual(row.task_status,'Assigned')
        self.assertIsNone(row.finished_step)
        self.assertEqual(row.incident_result,'Pending')

    def test_unavailable_teams_do_not_create_fake_assignment(self):
        run=finish(Simulation([reading()],Configuration(team_a_available=False,team_b_available=False)))
        self.assertEqual(run.team_attempts,[])
        row=incident_rows(run).iloc[0]
        self.assertEqual(row.assigned_team,'Not assigned')
        self.assertEqual(row.task_status,'Unresolved')

    def test_log_contains_every_actual_message_in_order(self):
        run=finish(Simulation([reading()],Configuration(fail_team_b=True),team_positions=positions('Team B')))
        rows=message_rows(run)
        self.assertGreater(len(rows),3)
        self.assertEqual(rows.message_id.tolist(),[m['message_id'] for m in run.bus.log])
        self.assertEqual(rows.content.tolist(),[m['content'] for m in run.bus.log])
        self.assertTrue({'Pressure Monitor','Usage Monitor','Leak Locator','Dispatch','Team A','Team B'}.issubset(set(rows.sender)|set(rows.receiver)))


if __name__=='__main__':unittest.main()

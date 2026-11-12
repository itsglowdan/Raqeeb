"""Execute technical verification runs and save their actual protocol traces."""
import sys
from pathlib import Path
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_loader import load_data
from simulation import Simulation, Configuration


def main():
    frame = load_data()
    normal = frame[(frame.Pressure_PSI >= 54)&(frame.Flow_Rate_Lmin <= 90)].iloc[0].to_dict()
    anomaly = frame[(frame.Pressure_PSI > 40)&(frame.Pressure_PSI < 54)&(frame.Flow_Rate_Lmin > 90)].iloc[0].to_dict()
    cases = [('normal', normal, Configuration(), 'Normal; one locally recorded outcome'),
             ('dual_anomaly', anomaly, Configuration(), 'Dual-rule assessment; closest configured team completes simulated task'),
             ('team_failure', anomaly, Configuration(fail_team_a=True), 'Team A fails on assignment; Dispatch reassigns to Team B'),
             ('team_b_failure', anomaly, Configuration(fail_team_b=True), 'Team B fails on assignment; Dispatch reassigns to Team A')]
    destination = Path(__file__).resolve().parents[1]/'docs'/'verification'
    destination.mkdir(exist_ok=True)
    results = []
    for name, reading, config, expected in cases:
        positions = None
        if name == 'team_b_failure':
            far = frame.loc[frame.Longitude.idxmin()]
            positions = {'Team A': {'record_ref': far.record_ref, 'position': [float(far.Latitude),float(far.Longitude)]},
                         'Team B': {'record_ref': reading['record_ref'], 'position': [reading['Latitude'],reading['Longitude']]}}
        system = Simulation([reading], config, {'name': name, 'purpose': 'Technical development verification, not a user-submitted experiment', 'expected_outcome': expected}, team_positions=positions)
        system.run()
        for _ in range(500):
            if system.waiting_approval:
                raise AssertionError('Verification selection unexpectedly needs approval')
            system.tick()
            if system.status in ['Completed', 'Failed']:
                break
        assert system.status == 'Completed'
        if name == 'team_failure':
            assert system.assigned == 'Team B' and any(e['type']=='team_failure' for e in system.events)
        if name == 'team_b_failure':
            assert system.assigned == 'Team A' and any(e.get('agent')=='Team B' and e['type']=='team_failure' for e in system.events)
        (destination/f'{name}.json').write_text(json.dumps(system.export(), indent=2))
        results.append({'name': name, 'record_ref': reading['record_ref'], 'status': system.status,
                        'assessment': system.assessments[0]['assessment'], 'messages': len(system.bus.log),
                        'reports': len(system.reports), 'events': len(system.events), 'steps': system.step})
    (destination/'summary.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

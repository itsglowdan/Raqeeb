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
    cases = [('normal', normal, Configuration(), 'Normal; one acknowledged outcome report'),
             ('dual_anomaly', anomaly, Configuration(), 'Dual-rule assessment; closest configured team completes simulated task'),
             ('reporting_failure', anomaly, Configuration(reporting_unavailable=True), 'Refusal, one retry per report task, explicit reporting failure')]
    destination = Path(__file__).resolve().parents[1]/'docs'/'verification'
    destination.mkdir(exist_ok=True)
    results = []
    for name, reading, config, expected in cases:
        system = Simulation([reading], config, {'name': name, 'purpose': 'Technical development verification, not a user-submitted experiment', 'expected_outcome': expected})
        system.run()
        for _ in range(500):
            if system.waiting_approval:
                raise AssertionError('Verification selection unexpectedly needs approval')
            system.tick()
            if system.status in ['Completed', 'Failed']:
                break
        assert system.status == ('Failed' if name == 'reporting_failure' else 'Completed')
        (destination/f'{name}.json').write_text(json.dumps(system.export(), indent=2))
        results.append({'name': name, 'record_ref': reading['record_ref'], 'status': system.status,
                        'assessment': system.assessments[0]['assessment'], 'messages': len(system.bus.log),
                        'reports': len(system.reports), 'events': len(system.events), 'steps': system.step})
    (destination/'summary.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

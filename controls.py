from data_loader import custom_reading


def automatic_inputs(frame, source, pressure=None, flow=None):
    if source == 'Dataset Readings':
        return [{**row, 'source': source} for row in frame.to_dict('records')]
    if pressure is None or flow is None:
        return []
    reference = frame.iloc[0].to_dict()
    return [custom_reading(reference, pressure, flow, reference['Vibration_mms'], 1)]


def automatic_team_positions(frame):
    positions = {}
    for name, index in [('Team A', frame.Longitude.idxmin()), ('Team B', frame.Longitude.idxmax())]:
        row = frame.loc[index]
        positions[name] = {'record_ref': row.record_ref, 'position': [float(row.Latitude), float(row.Longitude)]}
    return positions


def assessment_status(run):
    if run is None or not run.cursor:
        return 'بانتظار القراءات · Awaiting readings', 'waiting'
    reference = run.current_ref or run.readings[run.cursor-1]['record_ref']
    result = next((item for item in reversed(run.assessments) if item['record_ref'] == reference), None)
    if result is None:
        return 'جارٍ فحص القراءة · Checking', 'checking'
    return {'Normal': ('طبيعي · Normal', 'normal'),
            'Suspected': ('اشتباه بتسرب · Suspected', 'suspected'),
            'Leak indicated': ('تسرب حسب قواعد الكشف · Leak indicated', 'leak')}[result['assessment']]

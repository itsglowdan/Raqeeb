from pathlib import Path
import math
import pandas as pd

DATA_PATH = Path(__file__).parent / 'data' / 'riyadh_leakage_dataset_with_units.csv'
COLUMNS = ['Pressure_PSI', 'Flow_Rate_Lmin', 'Vibration_mms', 'Zone', 'Block', 'Pipe',
           'Location_Code', 'Latitude', 'Longitude', 'Leakage_Flag']
LABELS = {'record_ref': 'Record Reference', 'original_index': 'Original Reading Index',
          'Zone': 'District', 'Block': 'Section', 'Pipe': 'Pipeline',
          'Location_Code': 'Location Code', 'Pressure_PSI': 'Pressure (PSI)',
          'Flow_Rate_Lmin': 'Flow (L/min)', 'Vibration_mms': 'Vibration (mm/s)',
          'Leakage_Flag': 'Dataset Leakage Label'}


def validate_reading(row, labeled=True):
    for key in COLUMNS:
        if key == 'Leakage_Flag' and not labeled:
            continue
        if key not in row or row[key] is None:
            raise ValueError(f'Missing {key}')
    for key in ['Pressure_PSI', 'Flow_Rate_Lmin', 'Vibration_mms', 'Latitude', 'Longitude']:
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            raise ValueError(f'{key} must be numeric') from None
        if not math.isfinite(value):
            raise ValueError(f'{key} must be finite')
        if key not in ['Latitude', 'Longitude'] and value < 0:
            raise ValueError(f'{key} cannot be negative')
    if not -90 <= float(row['Latitude']) <= 90 or not -180 <= float(row['Longitude']) <= 180:
        raise ValueError('Invalid coordinates')
    for key in ['Zone', 'Block', 'Pipe', 'Location_Code']:
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f'Invalid {key}')
    if labeled and row['Leakage_Flag'] not in (0, 1):
        raise ValueError('Leakage_Flag must be 0 or 1')


def load_data(path=DATA_PATH):
    frame = pd.read_csv(path, float_precision='round_trip')
    if list(frame.columns) != COLUMNS:
        raise ValueError('Unexpected CSV columns or column order')
    for index, row in enumerate(frame.to_dict('records'), 1):
        try:
            validate_reading(row)
        except ValueError as error:
            raise ValueError(f'Original reading {index}: {error}') from error
    # References live in memory; the source CSV is never rewritten.
    frame.insert(0, 'original_index', range(1, len(frame) + 1))
    frame.insert(0, 'record_ref', [f'CSV-{i:05d}' for i in frame.original_index])
    return frame


def filter_data(frame, district='All', section='All', pipeline='All', query=''):
    selected = frame
    for field, value in [('Zone', district), ('Block', section), ('Pipe', pipeline)]:
        if value != 'All':
            selected = selected[selected[field] == value]
    if query.strip():
        mask = selected[['record_ref', 'Location_Code', 'Zone', 'Block', 'Pipe']].astype(str).apply(
            lambda column: column.str.contains(query.strip(), case=False, regex=False)).any(axis=1)
        selected = selected[mask]
    return selected.sort_values('original_index', kind='stable')


def summarize(frame):
    return {'readings': len(frame), 'flagged': int(frame.Leakage_Flag.sum()),
            'pressure': float(frame.Pressure_PSI.mean()) if len(frame) else None,
            'flow': float(frame.Flow_Rate_Lmin.mean()) if len(frame) else None}


def custom_reading(reference, pressure, flow, vibration, sequence_number):
    row = {key: reference[key] for key in ['Zone', 'Block', 'Pipe', 'Location_Code', 'Latitude', 'Longitude']}
    row.update(Pressure_PSI=pressure, Flow_Rate_Lmin=flow, Vibration_mms=vibration,
               record_ref=f'CUSTOM-{sequence_number:05d}', coordinate_reference=reference['record_ref'],
               source='Custom simulation input', original_index=None)
    validate_reading(row, labeled=False)
    return row

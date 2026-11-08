import math

from monitoring import ZONES, display_reading


def make_reading(pressure, flow, zone, block, pipe):
    try:
        pressure, flow = float(pressure), float(flow)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter numeric pressure and flow") from error
    if not all(math.isfinite(value) and value >= 0 for value in (pressure, flow)):
        raise ValueError('Pressure and flow must be finite, non-negative numbers')
    if zone not in ZONES or block not in {f'Block_{i}' for i in range(1, 6)} or pipe not in {f'Pipe_{i}' for i in range(1, 6)}:
        raise ValueError('Invalid network location')
    return display_reading({'Pressure': pressure, 'Flow_Rate': flow,
                            'Zone': zone, 'Block': block, 'Pipe': pipe})

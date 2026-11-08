import csv
import math
from pathlib import Path


DATA_FILE = Path(__file__).parent / "data" / "raqeeb_data.csv"
COLUMNS = ["Pressure", "Flow_Rate", "Zone", "Block", "Pipe", "Leakage_Flag"]


def load_data(path=DATA_FILE):
    readings = []
    labels = []

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != COLUMNS:
            raise ValueError("Unexpected dataset columns")

        for line, row in enumerate(reader, start=2):
            if any(value is None or not value.strip() for value in row.values()):
                raise ValueError(f"Missing value on line {line}")
            pressure = float(row["Pressure"])
            flow = float(row["Flow_Rate"])
            if not all(math.isfinite(value) and value >= 0 for value in (pressure, flow)):
                raise ValueError(f"Invalid reading on line {line}")
            if row["Leakage_Flag"] not in ("0", "1"):
                raise ValueError(f"Invalid leakage label on line {line}")

            readings.append({
                "Pressure": pressure,
                "Flow_Rate": flow,
                "Zone": row["Zone"],
                "Block": row["Block"],
                "Pipe": row["Pipe"],
            })
            # Keep test labels separate from sensor readings.
            labels.append(int(row["Leakage_Flag"]))

    if not readings:
        raise ValueError("The dataset is empty")
    return readings, labels


if __name__ == "__main__":
    readings, labels = load_data()
    print(f"Readings: {len(readings)}")
    print(f"Leak labels: {sum(labels)}")

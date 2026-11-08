# Raqeeb

A Python multi-agent simulation for water leak detection and maintenance dispatch.

## Current step

The dataset is ready and the data loader is implemented. Agents and the interface will be added next.

## Run

Use Python 3.10 or later. This step uses only the Python standard library.

```bash
python data_loader.py
```

## Data

`data/raqeeb_data.csv` contains 5,000 rows from the units version of the Kaggle dataset. Only these columns are retained:

| Column | Meaning |
| --- | --- |
| Pressure | Pressure in PSI |
| Flow_Rate | Flow in litres per minute |
| Zone, Block, Pipe | Network identifiers |
| Leakage_Flag | Reference label: 1 for a leak, 0 otherwise |

Values and labels are unchanged. Temperature, RPM, operational hours, vibration, coordinates and Location_Code are omitted. The location can be identified using Zone, Block and Pipe together.

The loader returns readings and reference labels separately. Agents must use the readings to detect leaks; labels are for evaluation only.

This is synthetic data for a university simulation, not measurements from a Saudi water network. Selecting pressure and flow does not establish compatibility with a specific SCADA installation. There are no timestamps or repair-team positions. Those will need separate simulation data; nearest-team dispatch cannot be calculated from these identifiers alone.

Source: Talha.97S, [Smart Water Leak Detection Dataset](https://www.kaggle.com/datasets/talha97s/smart-water-leak-detection-dataset), Kaggle. The source lists the MIT license and describes the labels as rule based. See `data/LICENSE.txt`.

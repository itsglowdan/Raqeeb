# Raqeeb

A Python multi-agent simulation for water leak detection and maintenance dispatch.

## Agents

Pressure Monitor, Usage Monitor, Leak Locator, Dispatch and Repair Team. Two repair-team instances compete for the task. The simulation delivers one queued message per step.

The agents confirm leaks using both pressure and flow, locate the incident, ask for supervisor approval for major leaks, and assign the closest available team. Failed teams are replaced when another team is available.

## Run

Use Python 3.10 or later. Run these commands inside the project folder. A virtual environment is recommended.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed in the terminal. Select a scenario, press **Load / Reset**, then **Run**. **Pause** stops automatic steps; **Next step** delivers one step manually. Major leaks show approval and rejection buttons. Changed settings apply only after Load / Reset.

The three examples are Normal, Minor leak, and Major leak + team failure. Use Dataset mode to choose any of the 5,000 rows. A run processes one reading. Team positions and repair durations are simulated. The map needs an internet connection for its background; the coordinate table remains available.

## Checks

```bash
python data_loader.py
python -m unittest -v test_simulation.py
```

Ten tests cover normal readings, confirmation, approval, rejection, failure recovery, unavailable teams, threshold boundaries, distance and label separation. See [model design](docs/model_design.md) for PEAS, environment analysis, protocols and scenarios.

## Files

- `app.py`: Streamlit interface and controls.
- `agents.py`: five agent roles and distance calculation.
- `simulation.py`: message queue, step scheduling, scenario selection and evaluation.
- `data_loader.py`: data loading and validation.
- `test_simulation.py`: simulation checks.
- `docs/screenshots/`: screenshots of the three scenarios.

## Data

`data/raqeeb_data.csv` contains 5,000 rows from the units version of the Kaggle dataset. Only these columns are retained:

| Column | Meaning |
| --- | --- |
| Pressure | Pressure in PSI |
| Flow_Rate | Flow in litres per minute |
| Zone, Block, Pipe | Network identifiers |
| Latitude, Longitude | Original simulated coordinates in decimal degrees |
| Leakage_Flag | Reference label: 1 for a leak, 0 otherwise |

Values and labels are unchanged. Temperature, RPM, operational hours, vibration and Location_Code are omitted. The location can be identified using Zone, Block and Pipe together.

The loader returns readings and reference labels separately. Agents must use the readings to detect leaks; labels are for evaluation only.

This is synthetic data for a university simulation, not measurements from a Saudi water network. Selecting pressure and flow does not establish compatibility with a specific SCADA installation. There are no timestamps or repair-team positions. The application creates separate simulated team positions to calculate distances to the incident coordinates. The source gives different coordinates for repeated readings of the same Zone/Block/Pipe combination. These are retained unchanged as reading locations, not treated as a fixed pipe location or a real network map.

Source: Talha.97S, [Smart Water Leak Detection Dataset](https://www.kaggle.com/datasets/talha97s/smart-water-leak-detection-dataset), Kaggle. The source lists the MIT license and describes the labels as rule based. See `data/LICENSE.txt`.

## Evaluation limits

At the default limits (pressure < 54 PSI and flow > 90 L/min), evaluation on all rows gives TP=323, FP=34, TN=4643 and FN=0: accuracy 99.32%, precision 90.48%, recall 100%, F1 95%. These are descriptive results on a synthetic rule-labelled dataset, using thresholds selected after inspecting it. They do not measure performance on unseen or Saudi utility data.

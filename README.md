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

Open the local URL printed in the terminal. Choose a starting row or a scenario, press **Load / Reset**, then **Run**. Monitoring continues until **Pause**, including after normal readings and completed repairs. **Next step** advances one 0.5-second simulation tick while paused. Major leaks show city-specific approval/rejection buttons. Other cities keep monitoring while approval is pending. Changed settings apply only after Load / Reset.

The three examples are Normal, Minor leak, and Major leak + team failure. A scenario selects the first row, then the stream continues through subsequent rows. Dataset mode selects the starting row directly. At the end, replay starts again; the cycle number is displayed. The stream is a simulation, not a live SCADA connection. It runs while this browser session is open; Pause freezes incoming readings and repairs. Reset clears monitoring history. The map needs internet for its background; the coordinate table remains available.

## Checks

```bash
python data_loader.py
python -m unittest -v test_simulation.py test_monitoring.py
```

Twenty-one tests cover normal readings, confirmation, approval, rejection, failure recovery, unavailable teams, thresholds, distance, label separation, continuous replay, Pause, independent cities, duplicate incident handling, persistent teams, estimated cost, execution errors, fixed display locations and bounded histories. See [model design](docs/model_design.md) for PEAS, environment analysis, protocols and scenarios.

## Files

- `app.py`: Streamlit interface and controls.
- `style.css` and `.streamlit/config.toml`: blue project identity and display styling.
- `agents.py`: five agent roles and distance calculation.
- `simulation.py`: per-reading message queue, agent execution traces and evaluation.
- `monitoring.py`: continuous replay, independent city incident queues, persistent local fleets, history and costs.
- `data_loader.py`: data loading and validation.
- `test_simulation.py` and `test_monitoring.py`: simulation and continuous monitoring checks.
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

This is synthetic data for a university simulation, not measurements from a Saudi water network. Selecting pressure and flow does not establish compatibility with a specific SCADA installation. There are no timestamps or repair-team positions. The original coordinates stay unchanged in the CSV. For the interface only, Zone_1 maps to Riyadh, Zone_2 to Madinah, Zone_3 to Abha, Zone_4 to Makkah and Zone_5 to Dammam. Each Block/Pipe gets a fixed virtual position near its assigned city. These are demonstration locations, not Saudi utility measurements or network topology. Each city has two simulated local teams; their positions and failures persist between incidents until Reset. No city shares its teams with another city.

Source: Talha.97S, [Smart Water Leak Detection Dataset](https://www.kaggle.com/datasets/talha97s/smart-water-leak-detection-dataset), Kaggle. The source lists the MIT license and describes the labels as rule based. See `data/LICENSE.txt`.

## Evaluation limits

At the default limits (pressure < 54 PSI and flow > 90 L/min), evaluation on all rows gives TP=323, FP=34, TN=4643 and FN=0: accuracy 99.32%, precision 90.48%, recall 100%, F1 95%. These are descriptive results on a synthetic rule-labelled dataset, using thresholds selected after inspecting it. They do not measure performance on unseen or Saudi utility data.

## Monitoring dashboard

- City cards show latest pressure/flow, sensor classification, open incident count and task state. An unresolved incident keeps a city red even if a later sensor reading looks normal. A completed repair does not modify sensor values. Red can also describe the latest confirmed reading; the task text indicates whether anything remains open.
- Select a city using its View button or City details. Pressure and flow line charts include detection thresholds. The time axis is simulation arrival time, since Kaggle has no timestamps. Charts do not represent an actual historical sequence from the water network.
- Global charts show cumulative unique incidents, completed repairs, messages, team failures and execution errors.
- Local traces measure actual Python execution time with `perf_counter`, excluding UI intervals and approval wait. This follows monitoring ideas from CAI461 Lab 9 (LangSmith); no LangSmith SDK, account, API key or external tracing service is used.
- Estimated cost = repair-start fee + straight-line dispatch distance × SAR/km. Defaults are 250 SAR and 5 SAR/km, editable in the sidebar. Costs are counted once when a team starts repairing. They are illustrative assumptions, not real tariffs. LLM/API cost is zero because no paid model/API is called.
- Pressure/Usage agents check every incoming reading. Confirmed incidents enter a city queue; one repair workflow per city runs at a time, while other cities progress independently. Repeated alerts for the same open Zone/Block/Pipe are merged. After a completed repair, a new abnormal observation may create a new incident. Rejected or unserviceable incidents remain unresolved; Reset clears them.
- History is bounded: 600 observations, 600 monitoring points, 1,500 messages, 1,500 traces, 500 recent incidents plus all open incidents. Session counters are cumulative even after older rows leave a chart/log. Downloads contain the retained message window only. Each city queue has a 100-incident limit; any admission drops are shown explicitly.

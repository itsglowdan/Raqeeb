# Raqeeb

A Python multi-agent simulation for water leak detection and maintenance dispatch.

## Run

Use Python 3.10 or later. Open a terminal in the folder containing `app.py`.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Choose a starting row or scenario, press **Load / Reset**, then **Run**. The system processes every remaining row once and stops at the end. **Pause** freezes the simulation; **Run** resumes without resetting. A scenario selects its matching starting row. Reset starts a new session.

The pressure and usage checks run on separate visible steps. The top panel highlights the agent roles that acted in the current tick and shows their city and latest delivered messages. Agent cards cover all cities; selecting a city below the overview filters its charts and map. View buttons pin a city; Follow active city tracks the incoming reading.

## Agents

Pressure Monitor and Usage Monitor confirm a leak only when both pressure and flow are abnormal. Leak Locator identifies the incident. Dispatch requests supervisor approval for major leaks and chooses the nearest available local Repair Team. Each city has Team A and Team B. Failed teams stay unavailable until Reset. Incidents in other cities continue while one city waits for approval. Repeated alerts for an open pipe are merged.

At the dataset end, runnable repair work finishes before the session stops. Pending approvals stay visible; approving or rejecting one resumes that workflow without reading the dataset again. Unserviceable and rejected incidents remain open.

## Data and locations

The CSV retains 5,000 rows, with pressure in PSI, flow in L/min, Zone, Block, Pipe, latitude, longitude and a reference leakage label. `Leakage_Flag` is used only for evaluation.

The original CSV coordinates are preserved. The interface uses fixed virtual locations around Riyadh, Madinah, Abha, Makkah and Dammam. These are demonstration locations, not real Saudi utility readings. Each city owns two simulated teams, whose positions persist between repairs. Distances are straight-line. Charts use simulation time; the source has no timestamps.

Dataset: Talha.97S, [Smart Water Leak Detection Dataset](https://www.kaggle.com/datasets/talha97s/smart-water-leak-detection-dataset). See [dataset license](data/LICENSE.txt).

## Checks

```bash
python -m unittest -v test_simulation.py test_monitoring.py
```

The tests cover finite traversal, Pause/resume, separate agent steps, approvals, failure recovery, duplicate incidents, fixed positions, bounded history and the full dataset. The design is in [docs/model_design.md](docs/model_design.md).

Default detection limits give TP=323, FP=34, TN=4643 and FN=0 on the original synthetic dataset. Accuracy is 99.32%, precision 90.48%, recall 100% and F1 95%. These are descriptive results using limits chosen after inspecting the dataset, not independent validation on Saudi utility measurements.

History retains 600 observations and monitoring samples, 1,500 messages and traces, and 500 recent incidents plus open incidents. Counters cover the whole session. Message downloads contain the retained window. The browser session must remain open for the simulation to advance.

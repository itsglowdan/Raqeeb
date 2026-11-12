# Raqeeb | رقيب

A Python multi-agent water-leak monitoring simulation. The dashboard uses the supplied Riyadh dataset, exact per-record coordinates and real agent-message exchanges. It is not a physical sensor deployment.

## Install and run

Use Python 3.10 or newer. Open CMD or PowerShell **inside the folder containing `app.py` and `requirements.txt`**:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501 if the browser does not open. Leave the terminal running; Ctrl+C stops the application. GitHub ZIP downloads sometimes contain another `Raqeeb-main` folder: enter that inner folder first. No API key, LLM or paid service is required.

## Automatic reading inputs

1. Choose **Dataset Readings** in the sidebar. All 5,000 original records load automatically in their original row order. Press **Run**; no record selection or Add action is needed.
2. Or choose **Custom Readings** and enter only pressure and flow. The current values automatically replace the custom input. The first original dataset record supplies its exact location and reference vibration value; no location selection is required. This is an unlabeled custom simulation input, not an original dataset observation.
3. Optionally adjust detection/coordination parameters in the expandable settings. Both sources use those parameters.
4. Team start locations are assigned automatically to the records with minimum and maximum dataset longitude. These are explicit software simulation positions, not real maintenance depots. Record references and exact coordinates remain in the run export.

There is no Reading Sequence editor, Include all filtered records checkbox, Dataset records picker, Add reading action, or manual team-location picker. Editing custom pressure/flow updates the prepared input automatically; changing source replaces it. The original CSV remains untouched.

The large main status card shows the current reading's **Normal, Suspected or Leak indicated rule assessment**, or Checking while that reading awaits assessment. Before any readings it shows Awaiting readings. It never presents Paused/Running as the water condition. Execution status appears beside the sidebar controls. The reading-progress bar and processed/total counter have been removed.

## Run and monitor

- **Run** starts automatic execution of the prepared finite sequence.
- **Pause** freezes reading advancement, message delivery, simulated team work, report timeout counters and task dispatch.
- **Resume** preserves the exact run position, configuration and messages.
- Completion occurs after all selected readings and pending tasks finish or are explicitly reported as failed. The dataset never loops automatically. Browser navigation does not recreate agents.
- Major dual-rule assessments wait for user approval in the agent panel. Approve/reject actions are disabled while paused.
- **Experiments → Start fresh experiment** creates isolated execution state on the next Run. It archives the old run snapshot and keeps the configured sequence. Changing inputs or parameters prepares a fresh run on the next Run click; an unchanged paused run uses Resume.

The previous light blue interface is restored. All inputs and Run/Pause/Resume/Load-Reset controls are in the sidebar. The main view shows execution status, live agents, pressure/flow charts and actual assessments versus simulated task completions. Counters, Message log, Incidents, Dataset evaluation, Experiments, Readings and Reports remain available. **Map is the last tab**, retaining the new Riyadh dataset's exact coordinates, geographic clustering and record details. **Riyadh overview is the final section**; View Zone selects that zone's charts and map.

The underlying agents, finite playback behavior and supplied CSV are unchanged by the interface restoration. Labels remain separate from assessments. Plots use reading order or explicit execution steps, not invented measurement timestamps.

## Agents and messages

The five Phase 1 roles are retained: Pressure Monitor, Usage Monitor, Leak Locator, Dispatch and Repair Team (Team A and Team B instances). Supporting Reading and Reporting agents handle validation and traceable records. There are eight independent agent instances with distinct state.

`Reading → Pressure ↔ Usage → Locator → Dispatch ↔ Teams`, with `Dispatch ↔ Reporting` acknowledgments. Each agent receives queued ACL-like messages rather than sharing one cosmetic detection routine. CFP/PROPOSE/ACCEPT implement actual nearest-available-team negotiation. Team tasks are software simulations only; they do not repair infrastructure or change dataset readings.

Messages contain message ID, sender, receiver, performative, content, ontology, conversation ID, execution step, UTC runtime timestamp, record reference and optional task reference. Dataset leakage labels are removed before sending measurements into the assessment protocol. They are used only for dataset summaries and evaluation.

## User-controlled experiments

No preset scenarios are installed. Use the sidebar to enter custom pressure/flow or select automatic dataset playback and Experiments to enter an optional name, purpose and expected outcome. Configure team availability, assignment failure or Reporting Agent refusal/lost acknowledgment there. Restore controls can recover an active or paused agent. Save/export actual outcomes separately from expectations.

Suggested manual test plans (enter these yourself; outcomes below are expectations):

| Test | Inputs and configuration | Expected behavior |
|---|---|---|
| Normal | Custom pressure 65, flow 80 at the automatically assigned reference location; default limits | Normal assessment, no team negotiation, acknowledged report |
| Dual anomaly | Custom pressure 50, flow 110 | Dual-rule assessment, exact location, closest available configured team selected, simulated task recorded |
| Agent failure | Same dual anomaly, Reporting Agent unavailable; timeout 20 steps, one retry | Actual refusals, bounded retry, explicit failed reporting task and terminal Failed run |

For approval/reassignment, try pressure 35 and flow 110, enable Team A assignment failure; it takes effect if Team A wins the distance negotiation. Approval precedes negotiation; Team B is selected after Team A fails. Normal means neither configured rule is crossed; one crossed rule is Suspected; both crossed rules mean Leak indicated. These are simulation thresholds, not official Saudi engineering limits.

## Data

`data/riyadh_leakage_dataset_with_units.csv` is the supplied file, unchanged byte for byte. It has 5,000 readings, 323 labels equal to 1, ten original columns, five Zone identifiers and 125 Location_Code identifiers. Coordinates range from 24.611017–24.821573 latitude and 46.572815–46.738981 longitude. These are supplied Riyadh demonstration coordinates; their relationship to physical infrastructure is not independently verified.

Each original row receives an in-memory `CSV-00001` style reference and one-based Original Reading Index. Location_Code is not unique: records sharing it can have different coordinates. The application never averages/reassigns those coordinates or invents district names. Friendly District/Section/Pipeline labels only rename the presentation.

There are no measurement timestamps, sensor connectivity states, pipeline routes or flow directions. Row order is not measurement time. Flow is not leak rate or water loss. All execution timestamps and playback intervals are application runtime information.

Default rule evaluation on these same 5,000 records: TP 323, TN 4,643, FP 34, FN 0; accuracy 99.32%, precision 90.48%, recall 100%, F1 95.00%. This is descriptive agreement with dataset labels, not evidence of real-world accuracy or a held-out ML evaluation.

## Tests and evidence

```bat
python -m unittest discover -s tests -v
python tests/verify_runs.py
```

See [verification](docs/verification.md), [actual exported verification runs](docs/verification/), [design and PEAS](docs/model_design.md), [academic report draft](docs/report.md), and [submission checklist](docs/requirements_review.md). Verification runs were executed during development; they do not claim that group members performed the required manual experiments.

## Files

- `data_loader.py`: validation, stable references, filtering and summaries.
- `controls.py`: automatic input preparation, automatic team locations and assessment status.
- `protocol.py`: ACL-like immutable message objects and queue.
- `agents.py`: independent approved agent roles and supporting agents.
- `simulation.py`: finite scheduler, state, coordination, retries and exports.
- `app.py`, `ui.py`, `style.css`: Python Streamlit UI and supported chart/map components.
- `tests/`: behavioral verification.

## Limitations and map setup

Folium/Leaflet and OpenStreetMap supply the background only, without an API key. Preserve map attribution. Internet access is needed for map assets/tiles; the coordinate table remains available if the map background fails. Disable **Geographic background** for a points-only view. A browser tile error displays an explicit map warning. Exact coordinate records can always be exported. No external service enriches monitoring records.

State is stored per Streamlit browser session, not in a database. Download run JSON before closing the session; saved snapshots are not permanent server storage. Experiments run serially to make coordination traceable. Agent failure handling has bounded retries; the simplified transport is an in-process reliable queue, not a distributed network.

Academic submission also requires the Business Model Canvas, full report, poster, presentation, group/instructor GitHub access and Blackboard submission. Prepared drafts are in `docs/`; the team must review and submit them. The in-app Reports page only exports data and execution evidence.

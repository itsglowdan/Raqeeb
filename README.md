# Raqeeb | رقيب

A Python multi-agent water-leak monitoring simulation. The dashboard uses the supplied Riyadh dataset, exact per-record coordinates and real agent-message exchanges. It is not a physical sensor deployment.

## Install and run

Use Python 3.10 or newer. Open CMD or PowerShell **inside the folder containing `app.py` and `requirements.txt`**:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501 if the browser does not open. Leave the terminal running; Ctrl+C stops the application. GitHub ZIP downloads sometimes contain another `Raqeeb-main` folder: enter that inner folder first. No API key, LLM or paid service is required.

## Prepare readings

1. Open **Settings**. Dataset filters apply consistently to summaries, tables, charts, map and exports.
2. **Dataset Readings:** choose all filtered records or specific record references, then **Add dataset readings**. Original row order is preserved.
3. **Custom Readings:** select District, Section, Pipeline and one exact reference record for coordinates. Enter pressure, flow and vibration, then **Add reading** for each intended sample. Inputs start empty. They are explicitly unlabeled and never added to the original CSV.
4. Review the sequence and adjustable pressure/flow/major thresholds, timeout, retry limit and simulated team duration. Both sources use these parameters. Vibration is retained and charted; the approved detection rule uses pressure and flow only.
5. Team start positions are configurable dataset record references, not known depots. Distances are straight-line, not travel routes.

A dataset sequence and a custom sequence can also be combined. Dataset records are sorted by original index; custom records follow in insertion order. Duplicate dataset records are not added twice. Every custom input has its own reference.

## Run and monitor

- **Run** starts automatic execution of the prepared finite sequence.
- **Pause** freezes reading advancement, message delivery, simulated team work, report timeout counters and task dispatch.
- **Resume** preserves the exact run position, configuration and messages.
- Completion occurs after all selected readings and pending tasks finish or are explicitly reported as failed. The dataset never loops automatically. Browser navigation does not recreate agents.
- Major dual-rule assessments wait for user approval in the agent panel. Approve/reject actions are disabled while paused.
- **Experiments → Start fresh experiment** creates isolated execution state on the next Run. It archives the old run snapshot and keeps the configured sequence. Configuration edits affect a fresh run, not Resume.

The sidebar contains the only execution controls. Dashboard order: dataset summaries, geographic overview, live agents, messages, then charts and readings. The map shows point records and genuine record-count clusters, without invented pipelines. Select a point or reference to view its original details. Map filters fit the displayed records; Reset map view restores the fitted view. Readings table selection links back to the map.

## Agents and messages

The five Phase 1 roles are retained: Pressure Monitor, Usage Monitor, Leak Locator, Dispatch and Repair Team (Team A and Team B instances). Supporting Reading and Reporting agents handle validation and traceable records. There are eight independent agent instances with distinct state.

`Reading → Pressure ↔ Usage → Locator → Dispatch ↔ Teams`, with `Dispatch ↔ Reporting` acknowledgments. Each agent receives queued ACL-like messages rather than sharing one cosmetic detection routine. CFP/PROPOSE/ACCEPT implement actual nearest-available-team negotiation. Team tasks are software simulations only; they do not repair infrastructure or change dataset readings.

Messages contain message ID, sender, receiver, performative, content, ontology, conversation ID, execution step, UTC runtime timestamp, record reference and optional task reference. Dataset leakage labels are removed before sending measurements into the assessment protocol. They are used only for dataset summaries and evaluation.

## User-controlled experiments

No preset scenarios are installed. Use Settings to prepare the desired inputs and Experiments to enter an optional name, purpose and expected outcome. Configure team availability, assignment failure or Reporting Agent refusal/lost acknowledgment there. Restore controls can recover an active or paused agent. Save/export actual outcomes separately from expectations.

Suggested manual test plans (enter these yourself; outcomes below are expectations):

| Test | Inputs and configuration | Expected behavior |
|---|---|---|
| Normal | Custom pressure 65, flow 80, vibration 3 at any exact reference; default limits | Normal assessment, no team negotiation, acknowledged report |
| Dual anomaly | Custom pressure 50, flow 110, vibration 3 | Dual-rule assessment, exact location, closest available configured team selected, simulated task recorded |
| Agent failure | Same dual anomaly, Reporting Agent unavailable; timeout 20 steps, one retry | Actual refusals, bounded retry, explicit failed reporting task and terminal Failed run |

For approval/reassignment, try pressure 35 and flow 110, select Team A's starting reference equal to the custom coordinate reference and enable Team A assignment failure. Approval precedes negotiation; Team B is selected after Team A fails. Normal means neither configured rule is crossed; one crossed rule is Suspected; both crossed rules mean Leak indicated. These are simulation thresholds, not official Saudi engineering limits.

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
- `protocol.py`: ACL-like immutable message objects and queue.
- `agents.py`: independent approved agent roles and supporting agents.
- `simulation.py`: finite scheduler, state, coordination, retries and exports.
- `app.py`, `ui.py`, `style.css`: Python Streamlit UI and supported chart/map components.
- `tests/`: behavioral verification.

## Limitations and map setup

Folium/Leaflet and OpenStreetMap supply the background only, without an API key. Preserve map attribution. Internet access is needed for map assets/tiles; the coordinate table remains available if the map background fails. Disable **Geographic background** for a points-only view. A browser tile error displays an explicit map warning. Exact coordinate records can always be exported. No external service enriches monitoring records.

State is stored per Streamlit browser session, not in a database. Download run JSON before closing the session; saved snapshots are not permanent server storage. Experiments run serially to make coordination traceable. Agent failure handling has bounded retries; the simplified transport is an in-process reliable queue, not a distributed network.

Academic submission also requires the Business Model Canvas, full report, poster, presentation, group/instructor GitHub access and Blackboard submission. Prepared drafts are in `docs/`; the team must review and submit them. The in-app Reports page only exports data and execution evidence.

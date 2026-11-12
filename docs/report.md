# RAQEEB — Phase 2 report draft

Course: AI 461, Agent-Based Systems, section 72U.

Team names from the supplied Phase 1 document: Danah Alsubaie, Layan Alrazin, Shmokh Aljomah, Deem Alrashoud and Layan Alfares. The team must review the final submission and add its required cover-page details locally.

## Abstract

Water leaks can waste treated water and increase the work required to monitor distribution networks. Raqeeb is a Python multi-agent simulation that explores how independent software agents can check suspicious measurements and coordinate a response. The system uses a supplied dataset of 5,000 readings with pressure, flow, vibration, network identifiers, coordinates and leakage labels. An ordinary environment function validates each selected record. Pressure and Usage Monitor agents exchange messages to verify two configurable anomaly conditions. When both conditions hold, a Leak Locator preserves the exact record location and a Dispatch Agent requests offers from two simulated maintenance teams. Major assessments require supervisor approval. Ordinary recording functions preserve traceable results without additional agents. The application keeps dataset leakage labels separate from system assessments and does not describe simulated tasks as physical repairs. A bilingual Streamlit dashboard provides geographic record clusters, agent states, message logs, configurable failure tests and actual message downloads. Technical verification covers ordinary readings, dual anomalies, maintenance-team failures, pause and resume, and team reassignment. The intended beneficiaries are water-network supervisors, utility operators and maintenance coordinators evaluating agent cooperation. The project demonstrates communication and task handling in an educational environment; it does not establish real-world detection performance or replace engineering validation.

## 1. Introduction

Saudi water-network operators need timely and understandable monitoring information. Unusual pressure or flow can require investigation, but a single anomaly does not prove a leak. The project explores cross-checking between agents and traceable coordination, rather than assuming that every abnormal reading is a confirmed physical incident.

Raqeeb retains the approved Phase 1 model: pressure monitoring, usage monitoring, leak localization, dispatch and maintenance-team representation. Ordinary validation and recording functions support the five approved agent roles. Target users are utility supervisors, water authorities and maintenance coordinators. Objectives are to demonstrate distinct agents, actual ACL-like exchanges, dual-rule assessment, location preservation, nearest-available simulated task allocation, human approval and explicit failure handling.

## 2. Business Model Canvas

The following describes a possible future product, not current customers, partners or revenue.

| Canvas element | Proposed model |
|---|---|
| Value proposition | Cross-check anomalous measurements and expose a clear task/message history to reduce unnecessary investigation |
| Customer segments | Water utilities, municipalities, large facilities and industrial network operators |
| Channels | Direct demonstrations, project website, industry exhibitions and integration partners |
| Customer relationships | Operator training, onboarding support, feedback sessions and maintenance agreements |
| Key resources | Python agents, validated network data, domain expertise, secure computing and future authorized sensor integrations |
| Key activities | Agent development, testing, calibration, operator training, integration and software maintenance |
| Key partners | Potential utility pilot partners, sensor suppliers, engineering firms and hosting providers; no existing partnership is claimed |
| Revenue streams | Potential deployment licensing, support subscriptions and integration services; none currently earned |
| Cost structure | Development, engineering review, testing, hosting, integration and future hardware/support; no invented monetary estimates |

## 3. Model Design

### 3.1 Overview and environment

See [complete model design](model_design.md) for the interaction diagram, agent-by-agent PEAS, type justifications, variables and protocol details. The environment is an accessible, deterministic, dynamic-while-running, discrete software simulation. Readings are finite and serial. User actions such as approval, pause or restoration are explicit external inputs.

### 3.2 Data handling

The supplied `riyadh_leakage_dataset_with_units.csv` is preserved byte for byte. It contains 5,000 records, ten original columns, five Zone values, 125 Location_Code values and 323 leak-indicated labels. Each row receives a stable in-memory original-index reference. The same location identifier can have many different coordinates, so the map never assigns one representative coordinate to an entire identifier.

Pressure, flow and vibration retain original numerical precision internally. Friendly display labels do not rewrite identifiers. Custom readings are separate, explicitly unlabeled inputs. The application automatically uses the first dataset record as their exact coordinate and vibration reference while users enter pressure and flow. The CSV has no measurement timestamps, sensor connectivity fields, pipeline geometry, connectivity or flow direction. Those fields are not synthesized.

### 3.3 Behaviors and decision rules

Pressure below 54 PSI and flow above 90 L/min together produce a default rule assessment of Leak indicated. One condition produces Suspected; neither produces Normal. A dual-rule result with pressure at or below 40 PSI requires supervisor approval. These are adjustable demonstration parameters, not official safety limits. Vibration is retained and charted but does not affect this approved dual-monitor rule. Leakage_Flag is removed from the payload before detection and never drives assessment.

Dispatch negotiates with Team A and B through CFP, PROPOSE, ACCEPT and REFUSE. Available teams calculate straight-line distance from configured coordinate references. The shortest offer is accepted. Each team can independently be configured to fail once on assignment; Dispatch requests new offers and can use Team B. All work is simulated. No physical infrastructure is repaired and no readings are changed after a task completes.

### 3.4 Communication and reporting

Agents communicate through an in-process message queue. Messages preserve sender, receiver, performative, content, ontology, conversation/message IDs, runtime timestamp, execution step and record/task references. Validation and recording are local functions, not agent requests. Team failure is reported by INFORM; Dispatch re-negotiates with the remaining team. Failed teams refuse subsequent offers until restored. When neither team is available, an explicit unresolved result ends the workflow. Local result records preserve original reading and conversation references.

## 4. Implementation and UI

The implementation is Python with Streamlit, pandas, Altair and Folium/streamlit-folium. The fixed title is outside a timed dynamic fragment, so routine playback steps update only the dashboard body. Display labels District, Section and Pipeline map to unchanged Zone, Block and Pipe source fields. Folium supplies supported Leaflet components; there is no separate JavaScript application or low-code workflow. `agents.py` contains independent agent classes, `protocol.py` the transport, `simulation.py` the scheduler/state/export logic, and `data_loader.py` validation and references. `app.py` and `ui.py` render session-owned state without recreating agents on navigation.

The restored light blue interface places inputs and execution controls in the sidebar, with live agents first, monitoring charts next, detail tabs for messages, incidents, evaluation, readings and the map, the map as the last tab, and Riyadh overview at the bottom. Dashboard counters show actual read/assessment/task counts across all districts, not live sensor counts. Reference dataset labels are used only for evaluation and map-label display. The clustered geographic view uses exact coordinates and labels point statuses as dataset labels. Agent activity and actual messages follow. Network-wide pressure and flow charts show processed reading order without point markers; the third chart compares actual rule assessments with completed simulated tasks by execution step. No measurement-time history, water loss or invented routes is displayed.

Run automatically advances the configured sequence and its queued tasks. Pause freezes all execution, including queued messages and team tasks. Resume continues without duplicate readings. Configuration changes apply to a fresh experiment. A sequence finishes after all tasks complete or have explicit failure outcomes. Each incident retains its assigned-team attempts, failures, reassignments and simulated task completion. The full actual message log is displayed without truncation. Logs and state persist across navigation; downloaded exports provide permanent evidence beyond the browser session.

## 5. Scenarios and Verification

The UI has no preset scenarios. Users choose automatic dataset playback or enter custom pressure/flow and configure fault conditions in the sidebar. The interface supports Arabic and English, aggregates results across zones and identifies affected locations automatically. Expected outcomes can be documented separately in the academic test record. Required manual plans are described in README. Expected outcomes remain separate from observed results.

Four technical development verification runs were executed using actual dataset records. Full inputs, configuration, messages and outcomes are in [verification exports](verification/). They are not represented as group-member experiments.

| Run | Input | Expected | Observed |
|---|---|---|---|
| Normal | CSV-00001, default rules | Normal, no dispatch | Completed; Normal; 4 messages; 1 local record; 4 steps |
| Dual anomaly | CSV-00029, default rules | Dual verification and nearest available simulated team | Completed; Leak indicated; 13 messages; 2 local records; 14 steps |
| Team A failure | CSV-00029; Team A fails after assignment | Failure reported and task reassigned | Completed by Team B; 19 messages; 2 local records; 1 failure event; 21 steps |
| Team B failure | CSV-00029; Team B starts nearest and fails after assignment | Failure reported and task reassigned | Completed by Team A; 19 messages; 2 local records; 1 failure event; 21 steps |

These counts are observed execution values, not constants displayed in the app. Additional behavioral tests verify coordinate associations, label separation, rule boundaries, approval rejection, pause/resume, failure reassignment, unavailable teams, team restoration, local record traceability and isolated runs. Browser verification evidence and remaining limitations are recorded separately in [verification](verification.md).

### Browser evidence

Actual development captures: [current five-role interface](screenshots/original_roles.png). These do not replace the team’s own manual experiment documentation.

### Evaluation

On the same supplied 5,000-record dataset, default rule agreement is TP 323, TN 4,643, FP 34 and FN 0. Accuracy = 99.32%; precision = 90.48%; recall = 100%; F1 = 95.00%. This evaluates rule agreement with labels in the supplied data, not held-out learning performance or field accuracy. Adjustable thresholds change these results. No machine-learning model is claimed.

## 6. Conclusion

Raqeeb implements the proposed multi-agent cooperation in a controlled Python environment. Agents verify readings, preserve source locations, negotiate simulated work and expose actual exchanges through an interactive dashboard. Team failure, refusal and reassignment demonstrate failure handling. The implementation meets the core software objectives within a finite playback simulation.

Future work requires authorized, time-stamped operational data, engineering calibration, real pipeline geometry, authenticated integrations and durable storage. The current project cannot establish real-world leak confirmation, sensor availability, physical repair success or water-loss reduction. The team must still perform and document its own manual experiments, review academic artifacts and complete submission.

## References

[1] Project 2, “Python Multi-Agent System: Project Requirements,” supplied course guideline.

[2] AI 461, “Python Project Rubric,” supplied assessment rubric.

[3] Raqeeb team, “RAQEEB Project 2 — Phase 1,” supplied approved introduction and Business Model Canvas.

[4] Talha.97S, “Smart Water Leak Detection Dataset,” Kaggle. https://www.kaggle.com/datasets/talha97s/smart-water-leak-detection-dataset. Numerical dataset provenance retained from earlier project work; current Riyadh coordinate CSV supplied by the project user.

[5] Streamlit, “Documentation.” https://docs.streamlit.io/.

[6] Folium, “Documentation.” https://python-visualization.github.io/folium/.

[7] FIPA, “ACL Message Structure Specification.” http://www.fipa.org/specs/fipa00061/.

## Appendix A — Source and execution

All implementation source is committed alongside this draft. Entry point: `app.py`; dependencies: `requirements.txt`; full agent and scheduler code: `agents.py`, `simulation.py`, `protocol.py`; behavioral tests: `tests/test_system.py`. Install with `python -m pip install -r requirements.txt`; run with `python -m streamlit run app.py`. The final formatted report should include the required code appendix or instructor-approved repository appendix, plus screenshots from the team's own experiments. This Markdown draft is not a final submitted report.

# Raqeeb | رقيب

Python multi-agent water-leak monitoring simulation using the supplied Riyadh dataset. The light blue interface supports Arabic and English. It shows network-wide results and identifies affected zones automatically.

## Run

Python 3.10 or later. Open CMD or PowerShell in the folder containing `app.py` and `requirements.txt`:

```bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501 if needed. Keep the terminal open; Ctrl+C stops the app. ZIP downloads may have an extra inner `Raqeeb-main` folder. No API key or LLM is required.

## Controls

- **اللغة / Language:** Arabic (default) or English. Switching language translates labels, agent states, charts, map details and table headings without resetting execution or entered values. Original dataset identifiers and ACL protocol codes remain unchanged.
- **Dataset Readings:** all 5,000 original records are prepared automatically in row order. Press Run directly.
- **Custom Readings:** enter pressure and flow, then Run. Location and reference vibration come automatically from the first original record. This is one unlabeled custom input; it does not generate future sensor measurements or inherit Leakage_Flag.
- **Agent parameters:** pressure/flow/major rules, simulated work duration and playback interval. These are demonstration settings, not official engineering safety limits.
- **Team conditions:** availability, independent one-shot Team A/Team B assignment failures, team restoration. These controls allow manual failure tests without an Experiments page.
- Team locations are assigned automatically to the original records with minimum and maximum longitude. They are simulated start positions, not real depots.
- **Run / Pause / Resume:** automatic finite execution; Pause freezes all messages, simulated work and pending task progression. Resume continues the same state. Changed inputs/parameters prepare a new run on the next Run click. Reset clears execution using the current inputs.

## Network-wide dashboard

There is no manual Zone selector or View Zone action. The large assessment card summarizes all assessed records; a leak assessment remains visible when a later record in another zone is normal. Affected zones and exact Section/Pipeline references are listed automatically. These are accumulated rule assessments, not proof of currently active physical leaks or repairs. The five-zone summary at the bottom shows assessment counts for the whole run.

Pressure and flow use plain connected **lines without point markers**, covering all processed zones in reading order. That axis is not measurement time and does not describe one physical pipe's time series. A single custom input is shown as numeric values with a clear explanation; two observations are needed to draw a changing line. No extra readings are fabricated to create a trend. A third step-line chart displays actual cumulative leak assessments and completed simulated tasks by integer execution step.

The remaining detail tabs are **Message log, Incidents, Dataset evaluation, Readings, Map**. Experiments and Reports tabs have been removed. Actual messages can still be downloaded from Message log. Academic report drafts remain in `docs/`; they are separate from the application interface.

## Map

The final tab retains all original Riyadh record coordinates, real record-count clusters, pan/zoom/fullscreen, background toggle and inline details. It automatically highlights an assessed problem location. Individual points can be clicked for inspection; no zone selection is required. Marker cyan/coral colors refer to dataset labels, separately from runtime assessments. Records sharing Location_Code can have different coordinates and are never averaged or reassigned.

OpenStreetMap provides the geographic background only. Attribution is preserved. Map assets/tiles need internet; a tile error displays a translated warning and coordinate tables remain available. No pipeline routes, flow directions or sensor connectivity are invented.

## Agents

The approved five roles are Pressure Monitor, Usage Monitor, Leak Locator, Dispatch and Repair Team (A/B instances). Six instances represent those five roles. Reading validation and result recording are ordinary functions, not additional agents. Actual ACL-like messages preserve sender/receiver, performative, content, ontology, IDs, record references, execution step and UTC runtime timestamp.

Pressure <54 PSI plus flow >90 L/min gives the default dual-rule leak assessment. One crossed threshold gives Suspected; neither gives Normal. A dual-rule result at pressure <=40 PSI needs supervisor approval. Available teams negotiate through CFP/PROPOSE/ACCEPT/REFUSE; Dispatch selects the nearest straight-line offer. Team work is simulated and never changes source readings. A configured assignment failure in either A or B triggers re-negotiation with the remaining available team. Each team can fail once per run; the failure occurs only if it is assigned. If neither is available, the workflow terminates with an explicit unresolved outcome.

Leakage_Flag never enters detection. Default agreement on the supplied dataset: TP 323, TN 4,643, FP 34, FN 0; accuracy 99.32%, precision 90.48%, recall 100%, F1 95.00%. This is agreement with the same dataset labels, not held-out machine-learning or real-world validation.

## Data and tests

`data/riyadh_leakage_dataset_with_units.csv` is the supplied 5,000-row, ten-column CSV, unchanged byte for byte. Its 323 positive labels, original field names, precision, IDs and exact per-record coordinates are preserved. An in-memory CSV-00001-style reference and one-based Original Reading Index identify rows. Supplied Riyadh demonstration coordinates have not been independently verified as infrastructure locations. There are no measurement timestamps or pipeline connectivity fields. Flow is not leak rate or water loss.

```bat
python -m unittest discover -s tests -v
python tests/verify_runs.py
```

Manual test plans: pressure 65/flow 80 (normal), 50/110 (dual anomaly), and 50/110 with Team A assignment failure enabled (reassignment). Enter the values yourself; no preset scenarios are loaded. For major approval, use pressure 35/flow 110. Team A failure takes effect if A wins the nearest-team negotiation; the technical verification fixes its position to make this reproducible. Use sidebar fault controls, actual messages and screenshots to document the required three manual scenarios.

See [design and PEAS](docs/model_design.md), [verification](docs/verification.md), [technical run exports](docs/verification/), [academic report draft](docs/report.md), and [submission checklist](docs/requirements_review.md). Development verification is not claimed as group-member participation. State is per browser session, not durable database storage.

Main modules: `data_loader.py` (validation/references), `protocol.py` (messages), `agents.py` (behaviors), `simulation.py` (scheduler), `controls.py` (automatic inputs), `presentation.py` (network summaries/charts), `i18n.py` (translation), and `app.py`/`ui.py` (Streamlit rendering).

## شرح مختصر

اختاري العربية أو الإنجليزية من أعلى السايد بار. الداتا جاهزة تلقائيًا؛ اضغطي تشغيل. للإدخال اليدوي اكتبي الضغط والتدفق فقط. تظهر النتائج لجميع المناطق، والنظام يحدد المنطقة التي ظهرت فيها المشكلة تلقائيًا. إعدادات تعطل الفرق والوكلاء موجودة في قسم حالة الفرق والوكلاء. حالة التشغيل منفصلة عن حالة الفحص، وتبديل اللغة يحافظ على التشغيل والقيم.

Final academic report, Business Model Canvas, poster, presentation, collaborator access and Blackboard submission remain team submission responsibilities. Drafts/checklist are supplied separately; no automatic submission or physical intervention is performed.

The title remains outside periodic dashboard updates, avoiding per-step title-card remounts. User-facing labels are District, Section and Pipeline; original CSV columns remain Zone, Block and Pipe.

## Team attempts and complete message log

The agent-flow strip shows **Repair Team Agent / وكيل الصيانة** as one role. The two individual team cards still expose A/B execution details. Incidents records every actual assignment attempt with team name, Assigned/In progress/Failed/Completed state, reassignment source, execution steps and overall incident outcome. A failed A/B row remains visible when the other team completes the simulated task. No offered-only or unavailable team is falsely marked assigned/completed. A later reading does not erase an earlier team's incident history.

Message log displays **every actual message in the current run**, in its original order, with a total count and sender/receiver/type/content columns first. The table scrolls without trimming messages, and download contains the same complete raw log. The small Recent activity preview above monitoring is intentionally separate from the full log. Both features support Arabic and English. Underlying dataset columns and coordinates remain unchanged.

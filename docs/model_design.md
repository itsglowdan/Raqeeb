# Model design

## Flow

Pressure Monitor → Usage Monitor → Pressure Monitor → Leak Locator → Dispatch → Repair Teams

The pressure agent asks the usage agent to check flow for the same reading. Only low pressure AND high flow confirm a leak. The locator sends the reading coordinates and network identifiers to dispatch. Major leaks wait for a supervisor. Dispatch asks both teams for offers and accepts the closest available team's offer. A team failure starts a new offer round. Repairs finish after a configurable number of steps.

There are five agent roles. Each city has two instances of the Repair Team role. Each reading has an in-memory agent message queue. ContinuousMonitor completes the three pressure/usage check messages on arrival. A confirmed incident joins its city queue. Each city advances one active incident by one message per simulation tick; cities progress independently. Each city owns two persistent team states, which are restored when a new incident starts. This is a local simulation, not a distributed service. Trace durations measure actual execution time and vary by machine.

## Agents and PEAS

| Agent / type | Performance | Environment | Actuators | Sensors | Reason |
| --- | --- | --- | --- | --- | --- |
| Pressure Monitor / Reactive | Correct pressure alerts and joint confirmations | Current network reading | REQUEST flow check; REQUEST location | Pressure and flow-check reply | Uses threshold rules |
| Usage Monitor / Reactive | Correct high-flow checks | Current network reading | INFORM pressure agent | Flow and pressure agent request | Responds to the current reading |
| Leak Locator / Reactive | Correct incident identifiers and coordinates | Network identifiers and reading position | REQUEST dispatch | Confirmed incident | Reads known location fields |
| Dispatch / Deliberative | Assign closest available team without bypassing approval | Incident, approval, team offers | CFP, ACCEPT, REFUSE | Offers, failure/completion messages, supervisor decision | Compares alternatives and replans after failure |
| Repair Team / Hybrid | Complete accepted repairs; report inability | Simulated team position, availability and task | PROPOSE, REFUSE, INFORM | CFP and ACCEPT | Reacts to offers and maintains a multi-step repair task |

## Environment

The simulator is accessible: all simulated readings and states are available to the program. It is deterministic: the same reading, controls and approval actions give the same result. It is dynamic during execution: task states and availability change each step. Scheduling and messages are discrete, while pressure, flow and coordinates are continuous-valued. Real water networks may instead be partially observable and stochastic.

Run continuously replays dataset rows, wrapping at the end, until Pause. One tick represents 0.5 simulated seconds; the adjustable arrival interval defaults to 2 simulation seconds. Dataset order does not represent real sensor history. No real pressure-drop rate is inferred. The original CSV stays intact; only displayed coordinates are mapped to fixed virtual Saudi locations. A scenario sets the first row; later rows continue normally. Pause freezes the whole simulated clock. Next step advances one tick. Monitoring depends on an open browser session.

## Parameters

| Parameter | Default | Effect |
| --- | --- | --- |
| Pressure limit | 54 PSI | Pressure strictly below this value is abnormal |
| Flow limit | 90 L/min | Flow strictly above this value is abnormal |
| Major pressure limit | 40 PSI | A confirmed leak at or below this pressure needs approval |
| Repair duration | 8 steps | Duration after task acceptance; not physical travel time |
| Team A failure | Off, except failure example | First team fails after acceptance |
| Both teams unavailable | Off | Tests unresolved incidents when no team can respond |

Limits are demonstration settings, not Saudi SCADA specifications or calibrated safety thresholds. They were chosen after inspecting this synthetic dataset; reported metrics are descriptive and not independent validation. Severity is a simple pressure-based simulation rule, not measured leak volume.

The five Zones are mapped to Riyadh, Madinah, Abha, Makkah and Dammam. Each city has two teams, starting 0.002 and 0.04 degrees north of its city center. Pipe display positions use city latitude + (block number − 3) × 0.012 and longitude + (pipe number − 3) × 0.012 degrees. These are invented positions for comparison, not extra sensor readings. Team positions and failures persist across that city’s incidents until Reset. Distance uses the haversine formula on coordinates, not road routes. A completed simulated repair moves the team to the incident position without changing the source dataset.

## Communication

Messages have `sender`, `receiver`, `performative`, `content`, `ontology`, `conversation_id`, `step` and `delivered`. The ontology is `water-leak`. Each observed reading gets a unique conversation (`reading-1`, `reading-2`, etc.) within the monitoring session. Messages also identify the city, original dataset row, replay cycle and simulated time. Repeated alerts for an open pipe cancel the duplicate location request and merge into the existing incident; these requests are marked `cancelled`. The log includes both queued and delivered messages; `delivered` distinguishes them.

| Initiator → responder | Performative | Example content | Expected response |
| --- | --- | --- | --- |
| Pressure Monitor → Usage Monitor | REQUEST | reading and pressure_low=true | INFORM with flow_high |
| Usage Monitor → Pressure Monitor | INFORM | flow_high=true | Confirm only if pressure is also low |
| Pressure Monitor → Leak Locator | REQUEST | Same sensor reading | Locate the incident |
| Leak Locator → Dispatch | REQUEST | area, latitude, longitude, major | Approval wait or team search |
| Supervisor → Dispatch | ACCEPT / REFUSE | Empty content; current incident | Start offers or leave unresolved |
| Dispatch → each team | CFP | Incident location | PROPOSE distance or REFUSE reason |
| Team → Dispatch | PROPOSE | distance_km=0.22 | Compare all responses |
| Dispatch → selected team | ACCEPT | Incident location | Repair or report failure |
| Dispatch → other offering team | REFUSE | A closer team was selected | Return to available |
| Team → Dispatch | INFORM | state=failed / completed | Reassign / mark completed |

## Three demonstration scenarios

Use default settings for these examples. Every reading is selected from the retained Kaggle data, without changing its pressure or flow.

1. **Normal:** row 1. Both readings are normal. Pressure and usage agents exchange a request/reply. No dispatch occurs.
2. **Minor leak:** row 29. Pressure is below 54 PSI and flow is above 90 L/min; pressure is above 40 PSI. All five roles participate. The closest available local team is selected and completes the repair; all cities keep receiving readings. The winner depends on the fixed virtual pipe position and persistent team locations.
3. **Major leak + team failure:** row 567. Pressure is at or below 40 PSI and flow is above 90 L/min. The affected city waits for approval while other cities continue monitoring. After approval, the nearest available local team is selected. With Team A failure enabled, Team A fails when assigned; dispatch asks for new offers and Team B completes the repair. If Team B is initially closer, Team A has not yet been assigned and its failure is not triggered. Rejecting approval leaves that incident unresolved. The standalone deterministic agent test also verifies the exact Team A → Team B recovery sequence.

The automated tests also cover a single abnormal sensor, unavailable teams, changed thresholds and threshold boundaries. Screenshots in `screenshots/` show executed examples.

## Execution screenshots

- [Normal reading](screenshots/normal.png)
- [Minor leak repaired](screenshots/minor_leak.png)
- [Major leak awaiting approval](screenshots/major_approval.png)
- [Repair completed after team failure](screenshots/failure_recovery.png)

## Continuous monitoring and graphs

Cities display their latest sensor classification and any open task separately. A later normal reading does not clear an unresolved incident. Duplicate open pipe alerts are merged; new pipes queue behind that city's task. One city waiting for approval does not block the other four.

Pressure and flow plots use simulated arrival times with threshold rules. Global plots show incidents versus completions, cumulative messages/failures/errors, and estimated cumulative maintenance cost. Traces plot actual mean execution duration per agent against simulated time. Timing uses `perf_counter`, so it excludes the UI delay and supervisor wait.

Cost defaults to 250 SAR per actual repair start plus 5 SAR per straight-line kilometre. These assumptions are editable. The charge is recorded once per accepted-and-started task; failures before repair start are not charged. LLM/API cost is zero. Lab 9 is a reference for local tracing/monitoring presentation, not a requirement to use LangSmith or add LLM agents.

Histories are bounded to keep continuous sessions manageable: 600 observations and monitoring samples, 1,500 messages and traces, and 500 recent incidents plus open incidents. Full-session counters persist. Failed teams stay failed until Reset. There is no automatic retry for a rejected or unserviceable incident; it stays open and visible.

## Dashboard views

- [Pressure and flow trends](screenshots/sensor_trends.png)
- [Execution monitoring](screenshots/performance.png)
- [Estimated maintenance cost](screenshots/maintenance_cost.png)
- [Virtual Saudi incident map](screenshots/saudi_map.png)

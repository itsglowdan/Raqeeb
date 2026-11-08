# Model design

## Flow

Pressure Monitor → Usage Monitor → Pressure Monitor → Leak Locator → Dispatch → Repair Teams

The pressure agent asks the usage agent to check flow for the same reading. Only low pressure AND high flow confirm a leak. The locator sends the reading coordinates and network identifiers to dispatch. Major leaks wait for a supervisor. Dispatch asks both teams for offers and accepts the closest available team's offer. A team failure starts a new offer round. Repairs finish after a configurable number of steps.

There are five agent roles, with two instances of the Repair Team role. Each agent has its own state and receives messages from an in-memory queue. Execution is sequential and deterministic, one delivered message per step. This is a small local multi-agent simulation, not a distributed service.

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

Only one reading is processed per run. Dataset order does not represent time. No sensor history or real pressure-drop rate is inferred. Coordinate variation within a repeated pipe identifier is preserved, so coordinates represent an incident observation rather than a fixed network topology.

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

Team A starts 0.002 degrees north of the reading; Team B starts 0.04 degrees north and 0.03 degrees east. These are invented positions for comparison, not extra sensor readings. Distance uses the haversine formula on coordinates, not road routes. A completed simulated repair moves the team to the incident position without changing the source dataset.

## Communication

Messages have `sender`, `receiver`, `performative`, `content`, `ontology`, `conversation_id`, `step` and `delivered`. The ontology is `water-leak`. There is one conversation (`reading-1`) per run. The log includes both queued and delivered messages; `delivered` distinguishes them.

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
2. **Minor leak:** row 29. Pressure is below 54 PSI and flow is above 90 L/min; pressure is above 40 PSI. All five roles participate. Team A offers the shorter distance, is selected and completes the repair.
3. **Major leak + team failure:** row 567. Pressure is at or below 40 PSI and flow is above 90 L/min. Dispatch waits for approval. After approval, Team A is selected but fails. Dispatch requests new offers; Team A refuses and Team B completes the repair. Rejecting approval leaves the leak unresolved.

The automated tests also cover a single abnormal sensor, unavailable teams, changed thresholds and threshold boundaries. Screenshots in `screenshots/` show executed examples.

## Execution screenshots

- [Normal reading](screenshots/normal.png)
- [Minor leak repaired](screenshots/minor_leak.png)
- [Major leak awaiting approval](screenshots/major_approval.png)
- [Repair completed after team failure](screenshots/failure_recovery.png)

# Model design

## Agent flow

Pressure Monitor ↔ Usage Monitor → Leak Locator → Dispatch → Repair Teams

Five agent roles cooperate through an in-memory ACL-like message queue. Each city has two local Repair Team instances. Team positions and failures persist between incidents. The simulator is local and sequential; cities have independent incident queues.

Each reading is checked in three visible steps: pressure request, flow check, joint confirmation. Confirmed incidents enter their city queue. Each city advances one incident workflow per tick while other cities continue. A major leak waits for approval. If a team fails, dispatch asks for new offers. Repeated alerts for an open pipe are merged.

## Agents and PEAS

| Agent / type | Performance | Environment | Actuators | Sensors | Reason |
| --- | --- | --- | --- | --- | --- |
| Pressure Monitor / Reactive | Correct alerts and joint confirmation | Current reading | REQUEST flow check and location | Pressure and flow reply | Threshold rules |
| Usage Monitor / Reactive | Correct flow checks | Current reading | INFORM pressure agent | Flow and pressure request | Responds to current values |
| Leak Locator / Reactive | Correct incident location | Pipe identifiers and virtual position | REQUEST dispatch | Confirmed reading | Uses known fields |
| Dispatch / Deliberative | Closest available team; approval respected | Incident and team offers | CFP, ACCEPT, REFUSE | Offers, failures, completion and approval | Compares offers and replans |
| Repair Team / Hybrid | Complete repairs and report inability | Team position, availability and task | PROPOSE, REFUSE, INFORM | CFP and ACCEPT | Reacts to offers and maintains repair state |

## Environment

The simulator is accessible because its input and state are available to the program. Decisions are deterministic for the same inputs and approval actions. Execution-time measurements vary by machine. The environment changes during execution. Scheduling and messages are discrete, while sensor values and positions are continuous-valued. The CSV order is not actual historical sensor time.

Run processes the selected starting row through the final row once, without wrapping. Pause freezes the clock and resumes at the same point. Each tick represents 0.5 simulation seconds. At most one sensor-reading conversation is checked at a time, taking three ticks; the selected reading interval is a minimum interval. City incident workflows advance alongside it. After the final reading, runnable repair work drains before stopping. Approval waits do not force an endless loop; their controls remain available and can resume pending work after scanning finishes.

## Variables

| Variable | Default | Effect |
| --- | --- | --- |
| Pressure limit | 54 PSI | Strictly lower pressure is abnormal |
| Flow limit | 90 L/min | Strictly higher flow is abnormal |
| Major pressure limit | 40 PSI | Confirmed leaks at or below this value require approval |
| Repair duration | 8 steps | Duration after task acceptance |
| Minimum reading interval | 2 seconds | Minimum time between starting readings |
| Team A failure | Off except failure scenario | Fails when assigned |
| Both teams unavailable | Off | Leaves incidents unresolved |

Zone_1 maps to Riyadh, Zone_2 to Madinah, Zone_3 to Abha, Zone_4 to Makkah and Zone_5 to Dammam. For display, latitude = city latitude + (block number − 3) × 0.012, longitude = city longitude + (pipe number − 3) × 0.012 degrees. Original CSV coordinates and sensor values stay unchanged. Teams start 0.002 and 0.04 degrees north of the city center. Haversine distance selects the closest available team. This is not road routing or measured leak severity.

## Communication

Messages contain sender, receiver, performative, content, ontology, conversation ID, step, city, original row and simulation time. Each reading has a unique conversation ID. Delivered and cancelled flags distinguish processed messages from queued or merged duplicate requests.

| Sender → receiver | Performative | Content / outcome |
| --- | --- | --- |
| Pressure → Usage | REQUEST | Reading and low-pressure result |
| Usage → Pressure | INFORM | High-flow result; confirm only if both are abnormal |
| Pressure → Locator | REQUEST | Confirmed reading |
| Locator → Dispatch | REQUEST | Area, coordinates and major flag |
| Supervisor → Dispatch | ACCEPT / REFUSE | Proceed or leave unresolved |
| Dispatch → teams | CFP | Incident position |
| Team → Dispatch | PROPOSE / REFUSE | Distance offer or unavailability |
| Dispatch → selected team | ACCEPT | Start repair |
| Dispatch → other team | REFUSE | Closer team selected |
| Team → Dispatch | INFORM | Accepted, failed or completed |

Local traces measure actual Python execution duration, excluding UI delays and approval waits. Team failures are distinct from execution errors. Global counters and charts track incidents, repairs, messages, failures and errors. Pressure and flow charts use simulated arrival times and show detection limits. Reference labels are used only for evaluation.

## Scenarios

1. Normal: row 1. The monitors exchange checks without dispatching a team.
2. Minor leak: row 29. Pressure and flow confirm a leak; the nearest available local team repairs it automatically.
3. Major leak and team failure: row 567. The affected incident waits for approval while other readings continue. With Team A failure enabled, assignment to Team A produces a failure and another offer round; Team B completes the task. Rejecting approval leaves the incident unresolved. The nearest team can change as positions persist.

## Interface

The agent panel is first, showing actual per-role activity, city, status, and delivered messages. City cards are below it. Selecting a city filters its sensor charts and map. Additional tabs show performance, messages, incidents and evaluation. Activity highlighting follows actual calls, stops while paused, and supports reduced-motion preferences.

## Screenshots

- [Live agents](screenshots/agents.png)
- [Kingdom overview](screenshots/overview.png)
- [Monitoring](screenshots/monitoring.png)

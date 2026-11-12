# Verification record

Development verification, 12 November 2026. These are actual development checks, not a claim that group members have completed their required manual experiments.

## Current architecture

Five approved roles: Pressure Monitor, Usage Monitor, Leak Locator, Dispatch and Repair Team. Team A/B are two instances of the last role: six independent instances overall. Validation and record creation are ordinary functions. No auxiliary Reading/Reporting agent is instantiated or receives messages. Obsolete reporting-agent fault and timeout/retry controls are removed.

## Data integrity

The supplied CSV remains byte-for-byte unchanged. SHA-256: `d9b94e6923b1952e327d13019b624d4300ad04744306c1fdd0d860e93a10ecb3`.

Observed: 5,000 records, ten original columns, no missing values, 323 positive labels. The presentation mappings are Zone → District, Block → Section, Pipe → Pipeline. Original columns, identifiers (including Zone_4) and exact row-coordinate associations are preserved.

## Backend checks

`python -m unittest discover -s tests -v`: 39 behavioral tests cover validation, precision, display-only field mappings, exact coordinate associations, automatic input preparation, label exclusion, genuine ACL exchanges, rule boundaries, nearest-team negotiation, approval/rejection, pause/resume, failure/reassignment, restoration, unavailable teams, isolated runs, local record traceability, network-wide aggregation, language mappings and plain line charts.

A full 5,000-record run with explicit approval of major assessments completed: 5,000 assessments, 23,236 actual messages, 5,357 local records and no execution-error events. Defaults agree with dataset labels at TP 323 / TN 4,643 / FP 34 / FN 0; these are not field accuracy claims.

`python tests/verify_runs.py` executes the current technical cases and saves their inputs/configuration/actual messages/outcomes in `verification/*.json`:

| Case | Input | Status | Messages | Local records | Steps |
|---|---|---|---:|---:|---:|
| Normal | CSV-00001 | Completed | 4 | 1 | 4 |
| Dual anomaly | CSV-00029 | Completed | 13 | 2 | 14 |
| Team A failure | CSV-00029, A fails on assignment | Completed after reassignment to B | 19 | 2 | 21 |
| Team B failure | CSV-00029, B starts nearest and fails on assignment | Completed after reassignment to A | 19 | 2 | 21 |

Failure handling records one actual team_failure event in the third case. The failed team refuses new offers until restored. The workflow records an explicit unresolved result if neither team is available.

## Browser checks

Chromium/Playwright verified:

- Dataset playback advances through records from different districts without any district picker.
- The title card keeps the **same connected DOM node**, with zero removal events during multiple automatic execution steps. Only the dynamic dashboard fragment refreshes during routine playback.
- Pause/Resume and finite custom-input completion work.
- Only the six approved-role instances appear; there is no Supporting agents panel or auxiliary-agent state.
- The map still uses exact dataset coordinates and renders in Arabic/English.
- Map reading details display District, Section and Pipeline; no source fields were renamed.
- Arabic/English switching preserves configured input and active execution. Earlier checks also cover lazy tabs, all-district line charts, actual record-count clusters, tile-error warnings and a 390px viewport.
- No uncaught page errors occurred in the final browser workflow.

[Current interface with original roles](screenshots/original_roles.png). Older screenshots in the repository are historical development evidence, not current architecture previews.

## Limits and submission

This is a finite educational simulation. There is no live sensor deployment, measured physical repair, real pipeline geometry or measurement timestamp. Teams and work duration are simulation state. Rule assessments are separate from supplied labels. Future readings and water-loss estimates are not generated. Session state is not durable storage; the actual message log can be downloaded.

The team must still review academic report/poster/presentation drafts, document its own three manual cases including team failure, add the agreed collaborators later and submit through Blackboard. No invitations or submission were performed automatically.

## Team attempt history and full log update

The flow strip has five role names and ends in Repair Team Agent (وكيل الصيانة), while A/B instance cards retain their separate execution details. Each team now has an independent one-shot assignment-failure setting. Assignment history is saved per record, including assignment ID, team, attempt state, reassignment source, execution steps and overall incident result. ACCEPT and accepted/failed/completed replies carry the corresponding assignment ID as task_ref.

Eight additional behavioral tests cover B→A reassignment, both teams failing with bounded termination, no failure before actual assignment, one-shot failure after restoration, persistence across later readings, paused pending assignments, unassigned/unavailable cases, and equality of complete message-table rows with the actual MessageBus log. These are included in the 39-test total.

The full log table is not limited to the three recent-activity items. It contains every current-run message in send order; complete raw JSON is downloadable. The incidents table keeps failed attempts visible after successful reallocation, with team name/status first. [Team incident history](screenshots/team_incidents.png).

Final browser workflow passed the five-role flow strip, A failure followed by B completion, full 19-message raw download with matching displayed count, B assignment failure with an unresolved outcome when A is unavailable, and Arabic labels for the B failure option and Incidents tab. No uncaught browser page errors occurred.

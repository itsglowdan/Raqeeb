# Verification record

Development checks completed on 12 November 2026. This record distinguishes automated verification, browser-driven development experiments and the group's still-required manual submission work.

## Dataset integrity

The supplied file and committed CSV were compared byte for byte and matched.

SHA-256: `d9b94e6923b1952e327d13019b624d4300ad04744306c1fdd0d860e93a10ecb3`.

Observed: 5,000 rows, ten original columns, no missing values, 323 labels equal to 1, 4,677 labels equal to 0. Stable row references preserve repeated identifier/coordinate associations. No older CSV is used by the application.

## Backend checks

`python -m unittest discover -s tests -v`: **23 tests passed**. Coverage includes source precision, filtering and summaries, exact custom coordinate references, invalid measurements, genuine correlated communication, label exclusion, threshold boundaries, nearest-team choice, approval rejection, pause/resume with no duplication, reassignment after failure, unavailable teams, reporting refusal, bounded acknowledgment timeouts, restoration, report idempotence, isolated runs and confusion-matrix values.

A full 5,000-record scheduler run with explicit approval of major tasks completed: 5,000 assessments, 38,950 messages, 5,357 report records and no execution-error events. This was a development execution check, not a replay of measured real-world time.

`python tests/verify_runs.py` creates three actual development verification runs. Inputs, configuration, expected outcome metadata, observed outcomes, actual messages and failure events are saved in `verification/*.json`. Summary:

| Run | Status | Messages | Reports | Steps |
|---|---|---:|---:|---:|
| Normal CSV-00001 | Completed | 7 | 1 | 7 |
| Dual anomaly CSV-00029 | Completed | 18 | 2 | 19 |
| Reporting refusal CSV-00029 | Failed | 22 | 0 | 57 |

Counts reflect those specific executions and are not hardcoded UI metrics.

## Browser checks

Chromium/Playwright exercised the running Streamlit app:

- Entered custom pressure/flow/vibration, added a sequence, started automatic execution and observed completion.
- Paused, verified unchanged run step/state during the pause, resumed, and navigated between pages without restarting the run.
- Executed a dual-anomaly custom input and observed simulated task coordination.
- Made Reporting Agent unavailable, observed bounded retries and terminal Failed status, and exported the actual experiment JSON containing report_failed events.
- Opened Reports and exported run data; opened Settings and checked a 390-pixel mobile viewport.
- Loaded the geographic map; applied District/Section/Pipeline filters; verified exact record details, map zoom/reset and View record navigation.
- Confirmed six initial geographic clusters contained 984 + 965 + 207 + 819 + 8 + 2,017 = 5,000 records.
- Verified OpenStreetMap raster tiles loaded successfully. Triggered the supported Leaflet tileerror event and observed the explicit background-unavailable warning while record points remained available.
- Final browser flows had no uncaught page errors.

The cloud browser required its external asset requests to use the environment's trusted Python HTTP client and inherited proxy/CA settings. TLS verification remained enabled. This was test-harness networking only; no bypass or proxy configuration was added to the application.

## Interface restoration check

[Current restored interface](screenshots/restored_interface.png)

The classic light blue single-screen interface was restored while retaining the exact supplied Riyadh CSV and the clustered OpenStreetMap component. Browser verification passed sidebar Run/Pause/Resume, finite completion, View Zone selection, the final Map tab, inline record details and Experiments, with no uncaught page errors. All 23 backend tests still pass. The captures below record the earlier dark interface; they remain historical development evidence rather than previews of the restored appearance.

## Captured UI evidence

These are genuine application captures from development verification, not fabricated mockups or group-member submission evidence.

- [Dashboard and exact-coordinate clusters](screenshots/dashboard.png)
- [Normal custom-input run](screenshots/normal.png)
- [Dual-anomaly custom-input run](screenshots/minor.png)
- [Reporting failure run](screenshots/failure.png)
- [Settings](screenshots/settings.png)
- [Mobile settings](screenshots/mobile.png)

## Remaining limitations

The app is a finite educational simulation. Rules have not been calibrated on independent physical network data. Background tiles and map libraries require internet; coordinate tables/exports do not. The dataset has no measurement times, pipeline connectivity or sensor availability. Team positions and work duration are explicitly configured simulation parameters. Session state is not durable storage; users must download evidence. No real deployment, Blackboard submission, collaborator invitations or physical intervention was performed.

The group must still run and save its own three manually configured experiments, review/finalize the academic report, poster and presentation, add the required GitHub collaborators later as agreed, and submit through Blackboard.

## Automatic controls update

The dataset and custom input are now prepared automatically without sequence editing or manual coordinate selection. Team positions are selected from original dataset longitude-extreme records. The main status card displays the current assessment, separate from sidebar execution state. Twenty-seven automated tests pass, including four new behavioral checks covering automatic full-dataset loading/order, replacement of custom values, exact automatic team coordinates, and assessment status preserved during Pause.

Browser verification also passed one-click Dataset Run, Pause/Resume, automatic custom-input replacement without Add, Normal/Suspected/Leak cards, and preservation of the leak assessment during Pause. No removed sequence/location selectors or processed/total progress bar were rendered, and no uncaught browser errors occurred. [Current automatic controls](screenshots/automatic_controls.png).

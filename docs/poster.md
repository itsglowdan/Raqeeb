# RAQEEB | رقيب — Poster content draft

## Problem

Unusual pressure or flow requires investigation. A single anomaly can create an unnecessary alert. Operators need traceable verification and coordination.

## Idea

A Python multi-agent simulation cross-checks pressure and flow, preserves each record's location, negotiates with simulated teams and records outcomes.

## Agents and interaction

Reading → Pressure ↔ Usage → Locator → Dispatch ↔ Team A/B. Dispatch also exchanges reporting requests and acknowledgments with the Reporting Agent. Major dual-rule assessments require a supervisor's approval.

## Data and environment

5,000 supplied Riyadh demonstration readings, 323 leak-indicated dataset labels. Dataset labels and agent assessments remain separate. Exact row coordinates are retained. No real sensor integration, physical repairs or pipeline routes are claimed.

## Verification results

Actual development verification: normal run completed in 7 steps with 7 messages; dual anomaly completed in 19 steps with 18 messages; reporting refusal run ended Failed after bounded retries in 57 steps with 22 messages. See exported evidence for inputs and full traces. These are development verification runs, not the team's manual submission experiments.

## Value and future work

Transparent multi-agent cooperation supports operator understanding. Future work requires authorized operational data, engineering calibration, real network geometry and persistent storage.

## Visual placement

Use one architecture diagram, one readable dashboard screenshot and one experiment outcome screenshot from the current implementation. Keep dataset labels distinct from runtime results. Include actual team names and instructor-required course information in the final designed poster.

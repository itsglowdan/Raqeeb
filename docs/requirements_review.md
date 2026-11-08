# Submission requirements review

Reviewed against the supplied Project 2 requirements.

| Requirement | Evidence | Status |
| --- | --- | --- |
| Real-world problem, users and objectives | Report sections 1–2 | Prepared |
| Nine-part Business Model Canvas | Report section 3 | Prepared |
| Four or more interacting agents | Five roles; two shared Repair Team instances | Implemented |
| PEAS, agent types and justification | Model design and report section 4 | Prepared |
| Environment classification | Model design and report section 4 | Prepared |
| Behaviors, parameters and environment | Agents, monitoring engine and design | Implemented/documented |
| ACL-like communication and examples | Message log and report protocol table | Implemented/documented |
| Three testing scenarios | Normal, minor leak, major leak with failure | Tested |
| Failure/conflict recovery | Team failure reassignment and shared-fleet reservation tests | Tested |
| Live agent status and message log | Top agent panel and Message log tab | Implemented |
| Run controls and adjustable parameters | Run/Pause and sidebar controls | Implemented |
| Python implementation | All application logic and UI authored in Python; Streamlit serves the UI | Implemented |
| Public source repository | itsglowdan/Raqeeb | Published |
| requirements.txt and setup/run README | Root files | Prepared |
| Abstract, introduction, business model, design, conclusion, references | docs/report.md | Prepared |
| Screenshots for all three scenarios | docs/screenshots/normal.png, minor.png, failure.png | Captured |
| Group members and instructors as collaborators | Owner will add these later | Pending |
| Final team review and Blackboard submission | Outside repository automation | Pending |

The chart count is not prescribed in the project requirements. Three charts are retained without removing required interface features. The runtime has no financial feature; the report's business model includes the required qualitative cost-structure component.

Dataset limits: synthetic readings; no timestamps or real Riyadh topology. Original measurements and labels stay unchanged. Display positions and team states are simulated. Performance metrics are descriptive, not independent field validation. See the report for details.

## Validation

- 25 automated tests passed, including all 5,000 rows, concurrent shared-team repairs, busy-team waiting and stale-offer reservation checks.
- Browser checks passed for Run/Pause, stopping at the dataset end, exactly three monitoring charts, zone selection, the final overview position, major approval, team failure recovery and mobile overflow.
- The normal, minor and major demonstration rows are 1, 36 and 567. The two leak examples have positive reference labels. No reference label enters the agents' decision inputs.

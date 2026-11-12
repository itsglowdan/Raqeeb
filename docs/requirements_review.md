# Submission review

The latest user specification is the implementation brief. The attached course guideline and rubric define academic requirements; they do not authorize fabricated data or completed submission claims. The supplied Phase 1 document defines the approved agent roles and team names.

| Requirement | Implementation or artifact |
|---|---|
| At least four distinct agents | Eight instances: five approved role families plus Reading and Reporting support |
| Genuine ACL-like communication | `protocol.py` queue, correlated message/task IDs and actual logs |
| PEAS, agent types, environment | `model_design.md` |
| Behaviors, variables and protocols | `model_design.md`, source classes |
| Configurable important parameters | Settings: pressure, flow, major limit, report timeout/retries, simulated work duration |
| User-controlled scenarios, no presets | Settings sequence builder and Experiments metadata/fault controls |
| Failure/conflict response | Reporting refusal/timeout with bounded retries; Team A failure and re-negotiation |
| Interactive status and logs | Main live-agent panel and Experiments tab with actual state/messages; sidebar execution controls |
| Data and map integrity | Supplied CSV unchanged; exact per-record coordinates; point clusters; no invented geometry |
| Python implementation | Python application and Streamlit/Folium/Altair components; no separate frontend app |
| Setup and dependencies | `requirements.txt`, README Windows/Python commands |
| Meaningful verification | `tests/test_system.py`, actual `docs/verification/*.json`, browser evidence |
| Business Model Canvas | Nine elements in report draft, aligned with Phase 1 |
| Report | `report.md` draft: abstract, introduction, business model, model design, implementation, scenarios, conclusion, references, source appendix guidance |
| Poster and presentation | Content drafts in `poster.md` and `presentation.md`; final formatted artifacts and delivery remain team work |

## Before submission

- The team must conduct and save its own three manual experiments, including at least one failure/conflict. Development verification exports are separate evidence, not a claim of group-member participation.
- Review the report draft, add required final formatting and code appendix, and include the team's own scenario screenshots. Check abstract length after edits (course requirement: 150–250 words).
- Complete the final designed poster and presentation. Practice explaining actual agent cooperation and observed outcomes.
- Add group members and Dr. Eman / T. Manairh to GitHub. The user already said this will be done later; account names have not been invented or invitations sent.
- Upload the final academic artifacts and repository link to Blackboard according to the instructor's deadline. No submission has been made by this application.

The rubric weights are idea 10%, business model 10%, implementation 30%, poster 10%, report 25% and presentation 15%. The software alone does not satisfy the poster, presentation or final submission requirements.

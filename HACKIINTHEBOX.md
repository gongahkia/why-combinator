**PRD v2 (Scope-Corrected): AI Hackathon in a Box**

## 1. Scope Lock (Based on Your Answers)
1. Primary use case is `hackathon-in-a-box`.
2. Core promise includes `actual execution in sandboxes`, not just ideation.
3. `Subagent spawning` is a required core mechanic in v1.
4. Product positioning is `AI hackathon platform` first.
5. Primary user is hackathon participants who need to prototype and iterate multiple ideas in parallel fast.
6. Non-adjacent branches are removed from core scope.
7. MVP target is usable in `one day of continuous prompting`.
8. Metrics include speed, quality, and cost, with hackathon outcomes as top priority.

## 2. Product Statement
ThinkTankOS is an AI hackathon platform where a user submits a problem statement, spins up multiple autonomous agents in parallel sandboxes, and gets runnable prototype branches plus a ranked synthesis within a single continuous session.

## 3. Target Users (v1)
1. Hackathon organizers.
2. Hackathon participants (non-technical and technical mixed teams).
3. Innovation teams running “internal hackathons” without heavy logistics.

## 4. Core Jobs To Be Done
1. Turn one problem statement into many executable prototype attempts quickly.
2. Let each attempt branch via subagents for faster exploration.
3. Compare outputs with transparent scoring and pick winners.
4. Merge best parts into a final demo-ready outcome.

## 5. In-Scope vs Out-of-Scope
### In-Scope (v1)
1. Parallel agent execution in isolated sandboxes.
2. Subagent tree creation with limits and budgets.
3. Prototype artifact generation (code, docs, demo scripts, experiment logs).
4. Tournament-style branch comparison and ranking.
5. Human checkpoint to approve final merged branch.

### Out-of-Scope (v1)
1. Broad enterprise verticalization (M&A, public sector planning, education).
2. Full production deployment automation.
3. Deep enterprise compliance packs beyond basic audit logs and controls.
4. External plugin marketplace.

## 6. Core User Flow
1. User inputs challenge, constraints, and judging criteria.
2. System launches `N` parent agents with distinct strategies.
3. Each parent agent can spawn subagents for decomposition, build, test, and critique.
4. Agents execute inside sandboxes and produce artifacts.
5. Evaluator scores each branch on speed, viability, novelty, and hackathon fit.
6. User reviews leaderboard, reruns branches, and merges selected outputs.
7. System generates final hackathon package: demo brief, code artifacts, and pitch summary.

## 7. Functional Requirements (MVP)
1. Challenge creation with objective, constraints, and max runtime budget.
2. Parallel sandbox orchestration for at least 5 concurrent parent agents.
3. Subagent spawning with configurable depth and token/runtime caps.
4. Artifact persistence per branch with reproducible run logs.
5. Built-in evaluator rubric with weighted scoring.
6. Branch replay and “fork from this point” controls.
7. Final synthesis mode that combines selected branches.
8. Exportable hackathon deliverable bundle.

## 8. Non-Functional Requirements (MVP)
1. Time-to-first-results under 3 minutes.
2. Full challenge completion in a single working session.
3. Stable reruns with deterministic-enough logs for judging.
4. Isolated execution and basic policy guardrails.
5. Cost controls per challenge and per branch.

## 9. MVP Definition: “Single-Day Continuous Prompting”
1. A team can start from zero and end with a judged prototype portfolio in one day.
2. No engineering setup required beyond challenge prompt and constraints.
3. The system must support rapid iterate-rerun cycles without manual infra work.
4. Output must be presentation-ready for hackathon judging by session end.

## 10. Success Metrics (Prioritized)
1. `% of hackathon challenges producing at least 3 viable prototype branches`.
2. `Median time` from prompt to first runnable prototype.
3. `Final adoption rate` of generated outputs in judging/demo.
4. `Cost per challenge` versus traditional hackathon staffing/logistics.
5. User-rated quality of branch diversity and final synthesis.

## 11. Adjacent Off-Branches (Kept, But Secondary)
1. Internal innovation sprint mode for companies.
2. Agency concept lab for rapid client pitch generation.
3. Classroom hackathon mode for guided learning.

## 12. Risks and Mitigations
1. Risk: too many low-quality branches.
Mitigation: stronger evaluator and early branch pruning.
2. Risk: runaway compute from subagent recursion.
Mitigation: strict depth, budget, and stop conditions.
3. Risk: user overwhelm.
Mitigation: leaderboard + clustering + top-branch auto-highlight.

## 13. Next Step
If you want, I can now generate `PRD v3` in one of these formats:
1. Investor-ready 1-pager.
2. Build-ready engineering spec (components, APIs, data model).
3. 1-day MVP execution playbook (prompt templates + runbook + scoring rubric).

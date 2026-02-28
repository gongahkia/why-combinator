No further clarifications needed. Your inputs are enough to finalize.

## Final PRD (Hackathon-Only Scope)

### 1. Product Definition
A multi-agent **AI hackathon platform** where:
1. User submits a problem statement and judging criteria.
2. Multiple **Hacker Agents** run in parallel sandboxes to produce MVPs.
3. Hacker Agents can spawn subagents.
4. **Judge Agents** score outputs using user-defined domains and weights.
5. System maximizes MVP output count within fixed time while enforcing minimum quality.

### 2. Scope Lock
1. Focus is strictly hackathon scenarios.
2. Ignore enterprise and non-hackathon scopes in v1.
3. Core features are sandbox execution, subagents, and judging.

### 3. Primary Roles
1. **Hacker Agents**: Generate and ship MVPs.
2. **Judge Agents**: Evaluate based on configured criteria/domains.
3. **User (Organizer/Participant)**: Defines constraints, judges, weights, risk appetite, and final scoring mode.

### 4. Core Configuration (User-Controlled)
1. `Iteration Window`: fixed total runtime (example: 2 hours).
2. `Idea Generation vs Idea Complexity` slider:
1. Left: prioritize high count of simpler MVPs.
2. Right: prioritize fewer but deeper MVPs.
3. `Minimum Quality Threshold`: required bar for MVP acceptance.
4. `Risk Appetite`: conservative / balanced / aggressive.
5. `Judging Criteria + Weights`: user-defined, editable mid-run.
6. `Novelty Penalty Weight`: configurable with defaults.
7. `Score Aggregation Mode`: average / weighted panel / head-judge override.

### 5. Judging Model
1. At least one Judge Agent must be a **domain expert**.
2. Additional Judge Agents should cover sensible domains (example: compliance for regulated/legal-heavy prompts).
3. Users can fully define judge panel profiles.
4. Judge profiles can be ingested from:
1. URL
2. Parseable structured format (JSON/YAML/CSV template)

### 6. Mandatory Output Rules
1. Every Hacker Agent must submit at least one MVP package.
2. MVP minimum bar:
1. Runnable artifact/prototype
2. Short README
3. Value hypothesis
3. Non-producing Hacker Agents are heavily penalized (not hard-disqualified by default).

### 7. Anti-Convergence / Anti-Safety Controls
1. **Similarity penalty** via automatic novelty scoring across outputs (semantic + artifact overlap signals).
2. **“Too safe” penalty** measured against baseline ideas generated at challenge start.
3. Both penalties are weighted in final score using user-configurable values (with defaults).

### 8. Optimization Objective
1. Primary objective: maximize number of accepted MVPs.
2. Constraint: each accepted MVP must pass minimum quality threshold.
3. Constraint: completion within fixed iteration window.
4. Behavior tuned by Idea Generation vs Complexity slider.

### 9. End-to-End Flow
1. User defines challenge + constraints + judges + scoring config.
2. System generates baseline ideas for safe-risk reference.
3. Hacker Agents run in parallel sandboxes and spawn subagents.
4. Judge Agents continuously score and rank outputs.
5. User can adjust judging weights mid-run.
6. System returns leaderboard + all MVP bundles + rationale and penalties.

### 10. Scoring (High-Level)
Final score combines:
1. Quality score (must clear threshold)
2. Novelty score
3. Feasibility score
4. User criteria score
5. Penalties:
1. Similarity penalty
2. Too-safe penalty (vs baseline)
3. Non-production penalty

### 11. MVP Success Metrics
1. Number of accepted MVPs per challenge window.
2. Median time to first accepted MVP.
3. Diversity index across accepted MVPs.
4. Share of Hacker Agents producing valid MVPs.
5. User satisfaction with judging fairness and usefulness.

### 12. Non-Goals (v1)
1. Non-hackathon enterprise workflows.
2. Full production deployment automation.
3. Open external marketplace.

If you want, I can now convert this into:
1. A build-ready engineering spec (APIs, schemas, orchestration logic).
2. A scoring formula spec with default weights and penalty math.
3. A runbook template for real hackathon operations.

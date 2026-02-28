# 2-Minute Demo Storyboard

Total runtime: `120s` (`3600` frames at `30fps`)

## Segment Plan

| Segment | Time (s) | Frames | Product Focus | Visual Plan | Voiceover Script |
|---|---:|---:|---|---|---|
| 1. Intro Hook | 0-8 | 0-239 | Product framing | Bold title card + system headline + pulse animation over architecture map | "This is an autonomous hackathon orchestration system that takes ideas from challenge prompt to judged leaderboard with reproducible scoring." |
| 2. Challenge Setup | 8-24 | 240-719 | Challenge creation | Organizer UI form fields animate in: title, prompt, risk appetite, complexity, iteration window | "An organizer defines the challenge prompt, scoring posture, and run constraints in under a minute." |
| 3. Run Start | 24-36 | 720-1079 | Deterministic run kickoff | API request/response overlay for `POST /challenges/{id}/runs/start` + seeded reproducibility badge | "Starting a run captures a deterministic seed and frozen configuration snapshot for replay-safe evaluation." |
| 4. Agent Execution | 36-54 | 1080-1619 | Hacker/subagent execution | Timeline lane view of hacker and subagent tasks, container events, and heartbeats | "Agents execute in isolated sandboxes, with budget guards, spawn controls, and resilient task recovery." |
| 5. Judge Ingestion | 54-68 | 1620-2039 | Judge profiles + ingestion safety | Judge panel cards + URL ingestion panel showing allowlist/sanitization checks | "Judge profiles can be registered from JSON, YAML, CSV, or URL ingestion paths protected by network and redirect-chain guards." |
| 6. Checkpoint Scoring | 68-84 | 2040-2519 | Scoring pipeline | Checkpoint worker flow: quality, novelty strategy, anti-gaming, penalties, final score composition | "Checkpoint scoring blends quality, novelty, feasibility, and criteria with configurable novelty strategy and anti-gaming penalties." |
| 7. Replay + Analytics | 84-96 | 2520-2879 | Replay determinism | Replay endpoint callout + diff analytics panel comparing original vs replayed final scores | "Every checkpoint can be replayed against frozen snapshots, producing deterministic score diffs for audit and analytics." |
| 8. Leaderboard + Realtime | 96-110 | 2880-3299 | Ranking and streams | Live leaderboard with websocket delta markers + segmentation filter pills for team and track | "Leaderboard updates stream in real time, with stable cursor pagination and optional segmentation filters by team or track." |
| 9. Artifact Retrieval | 110-118 | 3300-3539 | Artifact controls | Artifact list, malware quarantine status, retention badge, and presigned download action | "Artifacts are scanned, retained by policy, and served through short-lived signed URLs for controlled access." |
| 10. Closing CTA | 118-120 | 3540-3599 | Wrap-up | End slate with key outcomes and repo/API references | "The full flow is automated, observable, and reproducible end to end." |

## Visual Language Notes

- Typography: `Sora` for display, `IBM Plex Sans` for body, `IBM Plex Mono` for API overlays.
- Color system: warm paper background, high-contrast ink text, orange action accents, green success markers.
- Motion style: fast structural transitions (slide, wipe, stack reorder), restrained easing for status counters.
- Overlay style: realistic API payload snippets, queue metrics, and run lifecycle events aligned to actual endpoint names.

## Coverage Checklist

- Challenge setup
- Run start
- Agent execution
- Judging
- Scoring
- Leaderboard
- Artifact retrieval

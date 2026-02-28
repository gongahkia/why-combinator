# 2-Minute Demo Storyboard

Total runtime: `120s` (`3600` frames at `30fps`)

## Segment Plan

| Segment | Time (s) | Frames | Product Focus | Visual Plan | Voiceover Script |
|---|---:|---:|---|---|---|
| 1. Intro Hook | 0-12 | 0-359 | Product framing | Bold title card + system headline + pulse animation over architecture map | "Autonomous orchestration takes a challenge from brief to judged leaderboard with deterministic scoring." |
| 2. Challenge Setup | 12-24 | 360-719 | Challenge creation | Organizer UI form fields animate in: title, prompt, risk appetite, complexity, iteration window | "Organizers set challenge constraints, risk posture, and quality targets before execution starts." |
| 3. Run Start | 24-36 | 720-1079 | Deterministic run kickoff | API request/response overlay for `POST /challenges/{id}/runs/start` + seeded reproducibility badge | "Run start captures a deterministic seed and frozen snapshot for reproducible replay." |
| 4. Agent Execution | 36-48 | 1080-1439 | Hacker/subagent execution | Timeline lane view of hacker and subagent tasks, container events, and heartbeats | "Hacker and subagents execute in isolated sandboxes with budget controls and checkpoints." |
| 5. Judge Ingestion | 48-60 | 1440-1799 | Judge profiles + ingestion safety | Judge panel cards + URL ingestion panel showing allowlist/sanitization checks | "Judge profiles ingest from mixed formats while URL guards block unsafe redirect chains." |
| 6. Checkpoint Scoring | 60-72 | 1800-2159 | Scoring pipeline | Checkpoint worker flow: quality, novelty strategy, anti-gaming, penalties, final score composition | "Checkpoint scoring blends quality and novelty with anti-gaming penalties." |
| 7. Replay + Analytics | 72-84 | 2160-2519 | Replay determinism | Replay endpoint callout + diff analytics panel comparing original vs replayed final scores | "Replay diffs compare original and rerun outputs to confirm deterministic behavior." |
| 8. Leaderboard + Realtime | 84-96 | 2520-2879 | Ranking and streams | Live leaderboard with websocket delta markers + segmentation filter pills for team and track | "Realtime leaderboard updates remain stable under concurrent writes and segment filters." |
| 9. Artifact Retrieval | 96-108 | 2880-3239 | Artifact controls | Artifact list, malware quarantine status, retention badge, and presigned download action | "Approved artifacts use short-lived signed URLs while blocked uploads are quarantined." |
| 10. Closing CTA | 108-120 | 3240-3599 | Wrap-up | End slate with key outcomes and repo/API references | "The flow is fully automated, observable, and reproducible in a two-minute demo." |

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

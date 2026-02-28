## Hackathon Service + Why-Combinator Integration

This repository now supports a direct integration with the sibling `why-combinator` simulation engine for market-feasibility stress tests on hackathon runs.

### Overlap

- Both systems are multi-agent and phase/state driven.
- Both systems support deterministic seeds and replay-friendly execution.
- Both systems output scoring/metrics intended for decision support.

### Combined Mode

`POST /runs/{run_id}/analytics/market-simulation` executes a deterministic `why-combinator` simulation mapped from challenge settings and returns:

- `latest_metrics` (adoption, churn, market share, burn, revenue, runway)
- recommendation strengths/weaknesses
- overlap highlights and integration mode metadata

### Environment

- `WHY_COMBINATOR_REPO_PATH` (optional): absolute path to a local why-combinator repo.
- `WHY_COMBINATOR_DATA_DIR` (optional): storage directory for simulation state; defaults to `<ARTIFACT_STORAGE_PATH>/why-combinator`.

If `why-combinator` is not installed/importable, the endpoint returns `503` with an integration setup message.

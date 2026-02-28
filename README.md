[![](https://img.shields.io/badge/why--combinator_2.0.0-integrated-green)](https://github.com/gongahkia/why-combinator)
![](https://img.shields.io/badge/status-active-blue)

# `Why-Combinator`

[CLI](https://aws.amazon.com/what-is/cli/)-first and API-first multi-agent hackathon orchestration platform with integrated market-simulation analytics.

## Stack

* *Core Runtime*: [Python](https://www.python.org/), [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), [Celery](https://docs.celeryq.dev/), [Redis](https://redis.io/)
* *Agent Orchestration*: sandboxed hacker-agent execution, subagent graphing, deterministic replay seeds
* *Judging + Scoring*: weighted panel scoring, novelty/anti-gaming penalties, checkpoint snapshots, replay diff analytics
* *Market Simulation Bridge*: [why-combinator](https://github.com/gongahkia/why-combinator) compatibility layer for adoption/churn/runway stress testing
* *Demo Layer*: [Remotion](https://www.remotion.dev/) 120-second product walkthrough pipeline
* *Testing*: [pytest](https://docs.pytest.org/)

## What `Why-Combinator` can do *([for now](https://github.com/gongahkia/why-combinator/issues))*

* **Hackathon control plane**: Create challenges, configure risk/complexity controls, define iteration windows, and enforce minimum quality bars.
* **Parallel hacker execution**: Run multi-agent hacker flows with sandbox isolation, admission controls, and subagent spawning.
* **Judge system orchestration**: Ingest judge profiles via JSON/YAML/CSV/URL, enforce versioning, and apply domain-aware scoring.
* **Anti-convergence scoring**: Compute novelty, similarity penalties, and too-safe penalties with replay-safe checkpoint snapshots.
* **Realtime ranking**: Materialize leaderboards with cursor stability and segmentation labels.
* **Artifact governance**: Enforce malware quarantine, signed downloads, and retention policies.
* **Deterministic replay analytics**: Recompute and diff checkpoint scores with frozen snapshots.
* **Market simulation overlay**: `POST /runs/{run_id}/analytics/market-simulation` maps run constraints into startup-market stress metrics (adoption, churn, burn, runway, recommendation).
* **Demo production**: Reproducible 1080p render pipeline with captions, narration sync points, and QA checks.

## Usage

1. Clone and install dependencies.

```console
$ git clone https://github.com/gongahkia/why-combinator && cd why-combinator
$ pip install -e .
```

2. Configure infrastructure environment.

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hackathon
REDIS_URL=redis://localhost:6379/0
WHY_COMBINATOR_REPO_PATH=/absolute/path/to/why-combinator  # optional bridge override
```

3. Run the API service.

```console
$ uvicorn app.main:app --reload
```

4. Typical flow.

```console
$ curl -X POST http://localhost:8000/challenges ...
$ curl -X POST http://localhost:8000/challenges/<challenge_id>/runs/start
$ curl -X POST http://localhost:8000/runs/<run_id>/analytics/market-simulation -d '{"model":"mock"}'
$ curl http://localhost:8000/runs/<run_id>/analytics/replay/diff
```

5. Run tests.

```console
$ pytest -q
```

## Architecture

- Challenge + run orchestration in `app/api`, `app/orchestrator`, `app/queue`
- Scoring and replay in `app/scoring`
- Market-simulation bridge in `app/integrations/why_combinator_bridge.py`
- Demo pipeline in `demo/remotion`

## Reference

`Why-Combinator` began as a startup-simulation engine and now serves as an integrated hackathon orchestration + judging + market-simulation platform.

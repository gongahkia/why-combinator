[![](https://img.shields.io/badge/why_combinator_1.0.0-passing-light_green)](https://github.com/gongahkia/why-combinator/releases/tag/1.0.0)
[![](https://img.shields.io/badge/why_combinator_2.0.0-passing-green)](https://github.com/gongahkia/why-combinator/releases/tag/2.0.0)

# `Why-Combinator`

[CLI](https://aws.amazon.com/what-is/cli/) and [API](https://en.wikipedia.org/wiki/API)-first [multi-agent orchestration](#architecture) platform with [market-simulation](#what-why-combinator-can-do-for-now) analytics.

## Stack

* *Script*: [Python](https://www.python.org/), [Remotion](https://www.remotion.dev/) 
* *Backend*: [FastAPI](https://fastapi.tiangolo.com/), [Celery](https://docs.celeryq.dev/)
* *DB*: [SQLAlchemy](https://www.sqlalchemy.org/)
* *Cache*: [Redis](https://redis.io/)
* *Test*: [pytest](https://docs.pytest.org/)

## What `Why-Combinator` can do *([for now](https://github.com/gongahkia/why-combinator/issues))*

* **Hackathon control plane**: Create challenges, configure risk/complexity controls, define iteration windows, and enforce minimum quality bars.
* **Parallel hacker execution**: Run multi-agent hacker flows with sandbox isolation, admission controls, and subagent spawning.
* **Judge system orchestration**: Ingest judge profiles via JSON/YAML/CSV/URL, enforce versioning, and apply domain-aware scoring.
* **Anti-convergence scoring**: Compute novelty, similarity penalties, and too-safe penalties with replay-safe checkpoint snapshots.
* **Realtime ranking**: Materialize leaderboards with cursor stability and segmentation labels.
* **Artifact governance**: Enforce malware quarantine, signed downloads, and retention policies.
* **Deterministic replay analytics**: Recompute and diff checkpoint scores with frozen snapshots.
* **Demo production**: Reproducible 1080p render pipeline with captions, narration sync points, and QA checks.
* **Market simulation overlay**: Map run constraints into startup-market stress metrics (adoption, churn, burn, runway, recommendation).

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

...

## Reference

The name `Why-Combinator` is in reference to the startup accelerator [Y Combinator](https://www.ycombinator.com/). 

<div align="center">
    <img src="./asset/logo/Y.png" width=25%">
</div>
[![](https://img.shields.io/badge/why_combinator_1.0.0-passing-light_green)](https://github.com/gongahkia/why-combinator/releases/tag/1.0.0)
[![](https://img.shields.io/badge/why_combinator_2.0.0-passing-green)](https://github.com/gongahkia/why-combinator/releases/tag/2.0.0)

# `Why-Combinator`

[CLI](https://aws.amazon.com/what-is/cli/) and [API](https://en.wikipedia.org/wiki/API)-first [multi-agent orchestration](#architecture) platform with [market-simulation](#what-why-combinator-can-do-for-now) analytics.

## Stack

* *Script*: [Python](https://www.python.org/), [TypeScript](https://www.typescriptlang.org/), [Remotion](https://www.remotion.dev/), [React](https://react.dev/)
* *Backend*: [FastAPI](https://fastapi.tiangolo.com/), [uvicorn](https://www.uvicorn.org/), [Celery](https://docs.celeryq.dev/), [asyncpg](https://magicstack.github.io/asyncpg/), [Pydantic](https://docs.pydantic.dev/), [httpx](https://www.python-httpx.org/), [Docker](https://www.docker.com/)
* *DB*: [PostgreSQL](https://www.postgresql.org/), [SQLAlchemy](https://www.sqlalchemy.org/), [Alembic](https://alembic.sqlalchemy.org/), [aiosqlite](https://aiosqlite.omnilib.dev/), [TinyDB](https://tinydb.readthedocs.io/)
* *Cache*: [Redis](https://redis.io/)
* *Test*: [pytest](https://docs.pytest.org/)

## What `Why-Combinator` can do *([for now](https://github.com/gongahkia/why-combinator/issues))*

* **Hackathon control plane**: Create challenges, configure risk/complexity controls, define iteration windows, and enforce minimum quality bars.
* **Parallel hacker execution**: Run multi-agent hacker flows with Docker-sandboxed, network-restricted containers, admission controls, and subagent spawning.
* **Judge system orchestration**: Ingest judge profiles via JSON/YAML/CSV/URL, enforce versioning, and apply domain-aware scoring.
* **Deterministic replay analytics**: Recompute and diff checkpoint scores with frozen snapshots.
* **Demo production**: Reproducible 1080p video render pipeline with captions, narration sync points, and QA checks.
* **Market simulation overlay**: Map run constraints into startup-market stress metrics (adoption, churn, burn, runway, recommendation).
* **Rate limiting and quota enforcement**: Per-user token-bucket rate limits and soft quota caps on challenges, runs, and artifact storage.

## Screenshots

<div align="center">
    <img src="./asset/reference/1.png" width="45%">
    <img src="./asset/reference/4.png" width="45%">
</div>

<div align="center">
    <img src="./asset/reference/2.png" width="45%">
    <img src="./asset/reference/3.png" width="45%">
</div>

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
ARTIFACT_STORAGE_BACKEND=local                        # or s3
MODEL_API_KEY=<openai-key>                            # required for hacker/judge LLM calls
WHY_COMBINATOR_REPO_PATH=/absolute/path/to/why-combinator  # optional bridge override
```

3. Apply database migrations.

```console
$ alembic upgrade head
```

4. Start the API service and Celery workers (two separate terminals).

```console
$ uvicorn app.main:app --reload
$ celery -A app.queue.celery_app worker --loglevel=info -Q hacker-run,judge-run,checkpoint-score,checkpoint-backfill,outbox-relay,scheduler-monitor,run-heartbeat-watchdog,sandbox-cleanup,run-complete,score-submission,recovery
```

5. Typical flow.

```console
$ curl -X POST http://localhost:8000/challenges ...
$ curl -X POST http://localhost:8000/challenges/<challenge_id>/runs/start
$ curl -X POST http://localhost:8000/runs/<run_id>/analytics/market-simulation -d '{"model":"mock"}'
$ curl http://localhost:8000/runs/<run_id>/analytics/replay/diff
```

6. Run tests.

```console
$ pytest -q
```

## Architecture

![](./asset/reference/architecture.png)

## Reference

The name `Why-Combinator` is in reference to the startup accelerator [Y Combinator](https://www.ycombinator.com/). 

<div align="center">
    <img src="./asset/logo/Y.png" width=25%">
</div>
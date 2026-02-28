from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.challenges import ChallengeCreateRequest, create_challenge
from app.api.runs import start_run
from app.orchestrator.jobs import run_hacker_job
from app.orchestrator.reproducibility import (
    REPLAY_SEED_ALGORITHM,
    derive_agent_prompt_seed,
    derive_run_replay_seed,
)
from app.prompting.hacker import HackerPromptInput, render_hacker_agent_prompt


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str | int] = {}

    async def setnx(self, key: str, value: int) -> bool:
        if key in self.kv:
            return False
        self.kv[key] = value
        return True


@pytest.mark.asyncio
async def test_start_run_persists_deterministic_reproducibility_seed(session: AsyncSession) -> None:
    challenge = await create_challenge(
        ChallengeCreateRequest(
            title="Replay seed challenge",
            prompt="Build deterministic prompts for reproducible replay mode.",
            iteration_window_seconds=1200,
            minimum_quality_threshold=0.0,
            risk_appetite="balanced",
            complexity_slider=0.5,
        ),
        _rate_limit=None,
        session=session,
    )

    fake_redis = _FakeAsyncRedis()
    fake_settings = SimpleNamespace(default_run_budget_units=100, artifact_storage_path="/tmp/hackathon-artifacts")
    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=fake_redis, settings=fake_settings)))
    run = await start_run(challenge.id, request=fake_request, _rate_limit=None, session=session)

    reproducibility = run.config_snapshot["reproducibility"]
    assert reproducibility["seed_algorithm"] == REPLAY_SEED_ALGORITHM
    assert reproducibility["run_seed"] == derive_run_replay_seed(run.id)


def test_render_hacker_prompt_is_seeded_and_deterministic() -> None:
    prompt = render_hacker_agent_prompt(
        HackerPromptInput(
            challenge_title="Seeded challenge",
            challenge_prompt="Deliver one reproducible MVP attempt.",
            criteria={"novelty": 0.25, "quality": 0.35, "feasibility": 0.2, "criteria": 0.2},
            risk_appetite="balanced",
            complexity_slider=0.4,
            run_seed=77,
            agent_seed=88,
            agent_label="agent-x",
        )
    )

    assert "Replay run seed: 77" in prompt
    assert "Agent seed (agent-x): 88" in prompt
    assert prompt.index("- criteria: weight=0.2") < prompt.index("- novelty: weight=0.25")


def test_run_hacker_job_propagates_seed_into_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_spec: dict[str, object] = {}

    class _FakeRunner:
        def run(self, spec, limits):  # noqa: ANN001, ANN201
            captured_spec["spec"] = spec
            return SimpleNamespace(
                container_name="fake-container",
                exit_code=0,
                timed_out=False,
                startup_timed_out=False,
                stdout=(
                    '{"summary":"Deterministic summary output","value_hypothesis":'
                    '"Deterministic hypothesis output","artifacts":["bundle.zip"]}'
                ),
                stderr="",
                log_path="/tmp/fake-log.json",
            )

    monkeypatch.setenv("HACKER_RUNNER_ENABLED", "true")
    monkeypatch.setattr("app.orchestrator.jobs.HackerAgentRunner", _FakeRunner)
    monkeypatch.setattr("app.orchestrator.jobs.build_scoped_model_secret_env", lambda base_env, ttl_seconds: base_env)
    monkeypatch.setattr("app.orchestrator.jobs.load_hacker_runner_limits_from_env", lambda: SimpleNamespace())

    result = run_hacker_job("run-seeded", trace_id="trace-seeded", agent_id="agent-7", run_seed=42)

    expected_agent_seed = derive_agent_prompt_seed(42, "agent-7")
    assert result["run_seed"] == "42"
    assert result["agent_seed"] == str(expected_agent_seed)

    spec = captured_spec["spec"]
    assert spec.agent_id == "agent-7"
    assert spec.env["REPLAY_RUN_SEED"] == "42"
    assert spec.env["REPLAY_AGENT_SEED"] == str(expected_agent_seed)
    assert "Replay run seed: 42" in spec.env["HACKER_AGENT_PROMPT"]
    assert f"Agent seed (agent-7): {expected_agent_seed}" in spec.env["HACKER_AGENT_PROMPT"]


def test_run_hacker_job_returns_seed_metadata_when_runner_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HACKER_RUNNER_ENABLED", "false")

    result = run_hacker_job("run-disabled", trace_id="trace", agent_id="agent-disabled", run_seed=314)

    assert result["status"] == "runner-disabled"
    assert result["run_seed"] == "314"
    assert result["agent_seed"] == str(derive_agent_prompt_seed(314, "agent-disabled"))

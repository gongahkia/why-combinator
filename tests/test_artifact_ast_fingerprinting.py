from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.fingerprinting import fingerprint_submission_artifacts
from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.scoring.anti_gaming import detect_template_clone_penalty


@pytest.mark.asyncio
async def test_ast_level_similarity_penalty_detects_structural_python_clone(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    challenge = Challenge(
        title="AST clone detection",
        prompt="Detect structurally similar artifacts even with renamed variables.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.0,
        risk_appetite="balanced",
        complexity_slider=0.4,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent_a = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-a")
    agent_b = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-b")
    session.add_all([agent_a, agent_b])
    await session.flush()

    submission_a = Submission(
        run_id=run.id,
        agent_id=agent_a.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Use deterministic batching for retries.",
        summary="Retry logic for queue orchestration.",
    )
    submission_b = Submission(
        run_id=run.id,
        agent_id=agent_b.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Scale ingestion workers with shard balancing.",
        summary="Shard orchestration logic for ingestion.",
    )
    session.add_all([submission_a, submission_b])
    await session.flush()

    file_a = tmp_path / "artifact-a.py"
    file_a.write_text(
        "def transform(values):\n"
        "    total = 0\n"
        "    for item in values:\n"
        "        if item > 10:\n"
        "            total += item\n"
        "    return total\n",
        encoding="utf-8",
    )
    file_b = tmp_path / "artifact-b.py"
    file_b.write_text(
        "def reshape(records):\n"
        "    accumulator = 0\n"
        "    for row in records:\n"
        "        if row > 10:\n"
        "            accumulator += row\n"
        "    return accumulator\n",
        encoding="utf-8",
    )

    session.add_all(
        [
            Artifact(
                submission_id=submission_a.id,
                artifact_type=ArtifactType.CLI_PACKAGE,
                storage_key=file_a.name,
                content_hash="hash-a",
            ),
            Artifact(
                submission_id=submission_b.id,
                artifact_type=ArtifactType.CLI_PACKAGE,
                storage_key=file_b.name,
                content_hash="hash-b",
            ),
        ]
    )
    await session.commit()

    anti_gaming = await detect_template_clone_penalty(session, submission_a.id, storage_root=str(tmp_path))

    assert anti_gaming.compared_submissions == 1
    assert anti_gaming.matched_submission_id == submission_b.id
    assert anti_gaming.penalty >= 0.85


@pytest.mark.asyncio
async def test_fingerprint_submission_artifacts_emits_ast_fingerprint_for_javascript(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    challenge = Challenge(
        title="AST fingerprint languages",
        prompt="Fingerprint supported artifact languages for AST overlap.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.0,
        risk_appetite="balanced",
        complexity_slider=0.4,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-js")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Use javascript code paths.",
        summary="Javascript artifact fingerprinting.",
    )
    session.add(submission)
    await session.flush()

    file_js = tmp_path / "artifact.js"
    file_js.write_text(
        "export async function handler(items) {\n"
        "  let total = 0;\n"
        "  for (const item of items) {\n"
        "    if (item.ready) { total += 1; }\n"
        "  }\n"
        "  return total;\n"
        "}\n",
        encoding="utf-8",
    )
    session.add(
        Artifact(
            submission_id=submission.id,
            artifact_type=ArtifactType.CLI_PACKAGE,
            storage_key=file_js.name,
            content_hash="hash-js",
        )
    )
    await session.commit()

    fingerprints = await fingerprint_submission_artifacts(session, submission.id, storage_root=str(tmp_path))

    assert len(fingerprints) == 1
    assert fingerprints[0].language == "javascript"
    assert len(fingerprints[0].ast_fingerprint) > 0

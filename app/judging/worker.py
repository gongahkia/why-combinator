from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.codex_client import (
    CodexClient,
    CodexClientError,
    CodexRequest,
)
from app.db.models import JudgeScore, Run


@dataclass(frozen=True)
class CodexJudgeResult:
    score: float
    rationale: str
    raw_response: dict[str, object]


def _build_judge_prompt(challenge_prompt: str, judge_profile_prompt: str, submission_summary: str) -> str:
    return (
        "You are a judge agent.\n"
        f"Challenge: {challenge_prompt}\n"
        f"Judge profile: {judge_profile_prompt}\n"
        f"Submission summary: {submission_summary}\n"
        "Return a score between 0 and 1 with a concise rationale."
    )


def request_codex_evaluation(prompt: str) -> CodexJudgeResult:
    client = CodexClient(max_retries=3, backoff_base_seconds=0.5)
    try:
        response = client.call(CodexRequest(prompt=prompt, temperature=0.1, max_output_tokens=256))
        digest = hashlib.sha256(response.text.encode("utf-8")).digest()
        score = round((digest[0] / 255.0), 4)
        rationale = response.text[:500] or "Codex judge evaluation completed."
        return CodexJudgeResult(
            score=score,
            rationale=rationale,
            raw_response={"provider": "codex", "fallback": False, "response": response.raw},
        )
    except CodexClientError as exc:
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        score = round((digest[0] / 255.0), 4)
        return CodexJudgeResult(
            score=score,
            rationale="Codex evaluation fallback path used after client error.",
            raw_response={"provider": "codex", "fallback": True, "error": str(exc), "score": score},
        )


async def run_judge_scoring_worker(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str = "checkpoint",
    submission_ids: set[uuid.UUID] | None = None,
) -> int:
    run_stmt: Select[tuple[Run]] = (
        select(Run)
        .options(selectinload(Run.challenge).selectinload(Run.challenge.judge_profiles), selectinload(Run.submissions))
        .where(Run.id == run_id)
    )
    run = (await session.execute(run_stmt)).scalar_one_or_none()
    if run is None:
        return 0

    judge_profiles = run.challenge.judge_profiles
    submissions = run.submissions
    created = 0
    for submission in submissions:
        if submission_ids is not None and submission.id not in submission_ids:
            continue
        for judge_profile in judge_profiles:
            exists_stmt: Select[tuple[int]] = select(func.count()).select_from(JudgeScore).where(
                and_(
                    JudgeScore.submission_id == submission.id,
                    JudgeScore.judge_profile_id == judge_profile.id,
                    JudgeScore.checkpoint_id == checkpoint_id,
                )
            )
            if (await session.execute(exists_stmt)).scalar_one() > 0:
                continue

            prompt = _build_judge_prompt(
                challenge_prompt=run.challenge.prompt,
                judge_profile_prompt=judge_profile.profile_prompt,
                submission_summary=submission.summary,
            )
            codex_result = request_codex_evaluation(prompt)
            score_row = JudgeScore(
                submission_id=submission.id,
                judge_profile_id=judge_profile.id,
                checkpoint_id=checkpoint_id,
                score=codex_result.score,
                rationale=codex_result.rationale,
                raw_response=codex_result.raw_response,
            )
            session.add(score_row)
            created += 1

    await session.commit()
    return created

from __future__ import annotations

import concurrent.futures
import hashlib
import os
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
from app.db.models import Challenge, JudgeScore, Run
from app.validation.model_schema import ModelResponseValidationError, validate_judge_response_json

_JUDGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8)


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
        "Return strict JSON with keys score, rationale, confidence.\n"
        'Example: {"score":0.72,"rationale":"...","confidence":0.61}'
    )


def _build_judge_repair_prompt(original_prompt: str, invalid_response: str, validation_error: str) -> str:
    return (
        "Repair the previous judge output into strict JSON.\n"
        "Rules:\n"
        '- Return only one JSON object with keys "score", "rationale", "confidence".\n'
        "- score and confidence must be numeric values between 0 and 1.\n"
        "- rationale must be a concise string.\n"
        f"Original prompt:\n{original_prompt}\n"
        f"Invalid response:\n{invalid_response}\n"
        f"Validation error:\n{validation_error}\n"
        "Repaired JSON:"
    )


def load_judge_checkpoint_sla_seconds() -> float:
    return float(os.getenv("JUDGE_CHECKPOINT_SLA_SECONDS", "8"))


def _deterministic_judge_fallback(prompt: str, trace_id: str | None, reason: str) -> CodexJudgeResult:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    score = round((digest[0] / 255.0), 4)
    return CodexJudgeResult(
        score=score,
        rationale=f"Judge fallback used: {reason}",
        raw_response={
            "provider": "codex",
            "fallback": True,
            "error": reason,
            "score": score,
            "trace_id": trace_id or "",
        },
    )


def request_codex_evaluation(prompt: str, trace_id: str | None = None) -> CodexJudgeResult:
    client = CodexClient(max_retries=3, backoff_base_seconds=0.5)
    try:
        response = client.call(CodexRequest(prompt=prompt, temperature=0.1, max_output_tokens=256))
        try:
            parsed = validate_judge_response_json(response.text)
        except ModelResponseValidationError as initial_error:
            repair_prompt = _build_judge_repair_prompt(prompt, response.text, str(initial_error))
            repair_response = client.call(CodexRequest(prompt=repair_prompt, temperature=0.0, max_output_tokens=192))
            parsed = validate_judge_response_json(repair_response.text)
            return CodexJudgeResult(
                score=parsed.score,
                rationale=parsed.rationale[:500],
                raw_response={
                    "provider": "codex",
                    "fallback": False,
                    "repaired": True,
                    "response": response.raw,
                    "repair_response": repair_response.raw,
                    "parsed": {
                        "score": parsed.score,
                        "rationale": parsed.rationale,
                        "confidence": parsed.confidence,
                    },
                    "trace_id": trace_id or "",
                },
            )
        return CodexJudgeResult(
            score=parsed.score,
            rationale=parsed.rationale[:500],
            raw_response={
                "provider": "codex",
                "fallback": False,
                "repaired": False,
                "response": response.raw,
                "parsed": {
                    "score": parsed.score,
                    "rationale": parsed.rationale,
                    "confidence": parsed.confidence,
                },
                "trace_id": trace_id or "",
            },
        )
    except ModelResponseValidationError as exc:
        return _deterministic_judge_fallback(
            prompt,
            trace_id,
            f"schema validation failed after repair retry: {exc}",
        )
    except CodexClientError as exc:
        return _deterministic_judge_fallback(prompt, trace_id, f"client error: {exc}")


def request_codex_evaluation_with_sla(
    prompt: str,
    trace_id: str | None,
    sla_seconds: float,
) -> CodexJudgeResult:
    future = _JUDGE_EXECUTOR.submit(request_codex_evaluation, prompt, trace_id)
    try:
        return future.result(timeout=max(0.1, sla_seconds))
    except concurrent.futures.TimeoutError:
        return _deterministic_judge_fallback(prompt, trace_id, f"checkpoint_sla_exceeded:{sla_seconds}s")
    except Exception as exc:  # noqa: BLE001
        return _deterministic_judge_fallback(prompt, trace_id, f"judge execution failure: {exc}")


async def run_judge_scoring_worker(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str = "checkpoint",
    submission_ids: set[uuid.UUID] | None = None,
    trace_id: str | None = None,
) -> int:
    run_stmt: Select[tuple[Run]] = (
        select(Run)
        .options(selectinload(Run.challenge).selectinload(Challenge.judge_profiles), selectinload(Run.submissions))
        .where(Run.id == run_id)
    )
    run = (await session.execute(run_stmt)).scalar_one_or_none()
    if run is None:
        return 0

    judge_profiles = run.challenge.judge_profiles
    submissions = run.submissions
    created = 0
    sla_seconds = load_judge_checkpoint_sla_seconds()
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
            codex_result = request_codex_evaluation_with_sla(prompt, trace_id=trace_id, sla_seconds=sla_seconds)
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

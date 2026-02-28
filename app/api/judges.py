from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Challenge, JudgeProfile
from app.ingest.profile_parser import ProfileParseError, parse_profile_payload
from app.ingest.sanitize import URLSanitizationError, sanitize_ingestion_url
from app.ingest.url_fetch import URLFetchError, fetch_url_content

router = APIRouter(prefix="/challenges", tags=["judging"])


class JudgeProfileInput(BaseModel):
    domain: str = Field(min_length=2, max_length=255)
    scoring_style: str = Field(min_length=2, max_length=64)
    profile_prompt: str = Field(min_length=8)
    head_judge: bool = False


class JudgeProfileRegisterJSONRequest(BaseModel):
    profiles: list[JudgeProfileInput] = Field(min_length=1)


class JudgeProfileURLRequest(BaseModel):
    url: str = Field(min_length=8)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    max_bytes: int = Field(default=1024 * 1024, ge=1024, le=5 * 1024 * 1024)


class JudgeProfileResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    domain: str
    scoring_style: str
    profile_prompt: str
    head_judge: bool
    source_type: str
    created_at: datetime
    updated_at: datetime


def normalize_profiles(payload: object) -> list[JudgeProfileInput]:
    if isinstance(payload, dict) and "profiles" in payload:
        profiles = payload["profiles"]
    else:
        profiles = payload
    if not isinstance(profiles, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="profiles must be a list")
    return [JudgeProfileInput.model_validate(item) for item in profiles]


def parse_csv_profiles(payload: str) -> list[JudgeProfileInput]:
    reader = csv.DictReader(io.StringIO(payload))
    if reader.fieldnames is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="csv header is required")

    normalized: list[dict[str, object]] = []
    for row in reader:
        head_judge = str(row.get("head_judge", "")).strip().lower()
        normalized.append(
            {
                "domain": (row.get("domain") or "").strip(),
                "scoring_style": (row.get("scoring_style") or "").strip(),
                "profile_prompt": (row.get("profile_prompt") or "").strip(),
                "head_judge": head_judge in {"1", "true", "yes", "y"},
            }
        )
    return normalize_profiles(normalized)


async def persist_profiles(
    challenge_id: uuid.UUID,
    profiles: list[JudgeProfileInput],
    source_type: str,
    session: AsyncSession,
) -> list[JudgeProfileResponse]:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    db_profiles = [
        JudgeProfile(
            challenge_id=challenge_id,
            domain=item.domain,
            scoring_style=item.scoring_style,
            profile_prompt=item.profile_prompt,
            head_judge=item.head_judge,
            source_type=source_type,
        )
        for item in profiles
    ]
    session.add_all(db_profiles)
    await session.commit()
    for profile in db_profiles:
        await session.refresh(profile)

    return [
        JudgeProfileResponse(
            id=profile.id,
            challenge_id=profile.challenge_id,
            domain=profile.domain,
            scoring_style=profile.scoring_style,
            profile_prompt=profile.profile_prompt,
            head_judge=profile.head_judge,
            source_type=profile.source_type,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        for profile in db_profiles
    ]


@router.post(
    "/{challenge_id}/judge-profiles/json",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profiles_json(
    challenge_id: uuid.UUID,
    payload: JudgeProfileRegisterJSONRequest,
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    return await persist_profiles(challenge_id, payload.profiles, "inline_json", session)


@router.post(
    "/{challenge_id}/judge-profiles/yaml",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profiles_yaml(
    challenge_id: uuid.UUID,
    payload: str = Body(..., media_type="application/x-yaml"),
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid yaml: {exc}") from exc

    profiles = normalize_profiles(parsed)
    return await persist_profiles(challenge_id, profiles, "yaml", session)


@router.post(
    "/{challenge_id}/judge-profiles/csv",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profiles_csv(
    challenge_id: uuid.UUID,
    payload: str = Body(..., media_type="text/csv"),
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    profiles = parse_csv_profiles(payload)
    return await persist_profiles(challenge_id, profiles, "csv", session)


@router.post(
    "/{challenge_id}/judge-profiles/url",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profile_url(
    challenge_id: uuid.UUID,
    payload: JudgeProfileURLRequest,
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    try:
        sanitized_url = sanitize_ingestion_url(payload.url)
        content = fetch_url_content(sanitized_url, timeout_seconds=payload.timeout_seconds, max_bytes=payload.max_bytes)
        source_format, parsed = parse_profile_payload(content)
    except URLSanitizationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"url not allowed: {exc}") from exc
    except URLFetchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"url fetch failed: {exc}") from exc
    except ProfileParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"unable to parse fetched profile: {exc}") from exc

    profiles = normalize_profiles(parsed)
    return await persist_profiles(challenge_id, profiles, f"url_{source_format}", session)

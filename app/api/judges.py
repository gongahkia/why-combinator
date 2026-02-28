from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
import re

import yaml
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Challenge, JudgeProfile, JudgeProfileVersion
from app.ingest.allowlist import URLAllowlistError, assert_url_allowed_for_challenge
from app.ingest.profile_parser import ProfileParseError, parse_profile_payload
from app.ingest.sanitize import URLSanitizationError, sanitize_ingestion_url
from app.ingest.url_cache import fetch_url_content_cached
from app.ingest.url_fetch import URLFetchError
from app.judging.versioning import create_judge_profile_version_snapshot
from app.security.prompt_injection import PromptInjectionError, assert_no_prompt_injection

router = APIRouter(prefix="/challenges", tags=["judging"])


class JudgeProfileInput(BaseModel):
    domain: str = Field(min_length=2, max_length=255)
    scoring_style: str = Field(min_length=2, max_length=64)
    profile_prompt: str = Field(min_length=8)
    head_judge: bool = False

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,254}", normalized):
            raise ValueError("domain must match pattern [a-z][a-z0-9_-]{1,254}")
        return normalized

    @field_validator("scoring_style")
    @classmethod
    def validate_scoring_style(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"strict", "balanced", "creative", "risk_weighted"}
        if normalized not in allowed:
            allowed_csv = ", ".join(sorted(allowed))
            raise ValueError(f"scoring_style must be one of: {allowed_csv}")
        return normalized


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


class JudgeProfileVersionActivateRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class JudgeProfileVersionResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    version_number: int
    is_active: bool
    lock_version: int
    profile_count: int
    created_at: datetime
    updated_at: datetime


def _to_judge_profile_response(profile: JudgeProfile) -> JudgeProfileResponse:
    return JudgeProfileResponse(
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


def _to_judge_profile_version_response(version: JudgeProfileVersion) -> JudgeProfileVersionResponse:
    payload = version.profiles_payload if isinstance(version.profiles_payload, list) else []
    return JudgeProfileVersionResponse(
        id=version.id,
        challenge_id=version.challenge_id,
        version_number=version.version_number,
        is_active=version.is_active,
        lock_version=version.lock_version,
        profile_count=len(payload),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


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


def _detect_bulk_file_format(filename: str, content_type: str | None) -> str:
    lowered_name = filename.lower()
    if lowered_name.endswith(".json"):
        return "json"
    if lowered_name.endswith(".yaml") or lowered_name.endswith(".yml"):
        return "yaml"
    if lowered_name.endswith(".csv"):
        return "csv"

    lowered_type = (content_type or "").lower()
    if "json" in lowered_type:
        return "json"
    if "yaml" in lowered_type or "yml" in lowered_type:
        return "yaml"
    if "csv" in lowered_type:
        return "csv"

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"unsupported bulk profile file format: {filename}",
    )


def parse_bulk_profile_file(
    filename: str,
    content: bytes,
    content_type: str | None,
) -> tuple[list[JudgeProfileInput], str]:
    file_format = _detect_bulk_file_format(filename, content_type)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid utf-8 in bulk profile file: {filename}",
        ) from exc

    if file_format == "json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid json in bulk profile file {filename}: {exc}",
            ) from exc
        return normalize_profiles(parsed), "bulk_json"

    if file_format == "yaml":
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid yaml in bulk profile file {filename}: {exc}",
            ) from exc
        return normalize_profiles(parsed), "bulk_yaml"

    return parse_csv_profiles(text), "bulk_csv"


async def persist_profiles(
    challenge_id: uuid.UUID,
    profiles: list[JudgeProfileInput],
    source_type: str,
    session: AsyncSession,
) -> list[JudgeProfileResponse]:
    profile_rows = [(profile, source_type) for profile in profiles]
    return await _persist_profiles_with_sources(challenge_id, profile_rows, session)


async def _persist_profiles_with_sources(
    challenge_id: uuid.UUID,
    profile_rows: list[tuple[JudgeProfileInput, str]],
    session: AsyncSession,
) -> list[JudgeProfileResponse]:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    existing_head_stmt: Select[tuple[int]] = select(func.count()).select_from(JudgeProfile).where(
        JudgeProfile.challenge_id == challenge_id,
        JudgeProfile.head_judge.is_(True),
    )
    existing_head_count = (await session.execute(existing_head_stmt)).scalar_one()
    incoming_head_count = sum(1 for item, _source in profile_rows if item.head_judge)
    if existing_head_count + incoming_head_count > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at most one head_judge is allowed per challenge panel",
        )

    db_profiles = [
        JudgeProfile(
            challenge_id=challenge_id,
            domain=item.domain,
            scoring_style=item.scoring_style,
            profile_prompt=item.profile_prompt,
            head_judge=item.head_judge,
            source_type=source_type,
        )
        for item, source_type in profile_rows
    ]
    session.add_all(db_profiles)
    await session.flush()
    await create_judge_profile_version_snapshot(session, challenge_id, activate=True)
    await session.commit()
    for profile in db_profiles:
        await session.refresh(profile)

    return [_to_judge_profile_response(profile) for profile in db_profiles]


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
    "/{challenge_id}/judge-profiles/bulk",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profiles_bulk(
    challenge_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    if not files:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="at least one file is required")

    parsed_profiles: list[tuple[JudgeProfileInput, str]] = []
    for file in files:
        filename = (file.filename or "uploaded-profile").strip() or "uploaded-profile"
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"bulk profile file is empty: {filename}",
            )
        profile_inputs, source_type = parse_bulk_profile_file(filename, content, file.content_type)
        parsed_profiles.extend((profile_input, source_type) for profile_input in profile_inputs)

    return await _persist_profiles_with_sources(challenge_id, parsed_profiles, session)


@router.get(
    "/{challenge_id}/judge-profile-versions",
    response_model=list[JudgeProfileVersionResponse],
)
async def list_judge_profile_versions(
    challenge_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileVersionResponse]:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    versions_stmt: Select[tuple[JudgeProfileVersion]] = (
        select(JudgeProfileVersion)
        .where(JudgeProfileVersion.challenge_id == challenge_id)
        .order_by(JudgeProfileVersion.version_number.desc())
    )
    versions = (await session.execute(versions_stmt)).scalars().all()
    return [_to_judge_profile_version_response(version) for version in versions]


@router.post(
    "/{challenge_id}/judge-profile-versions/{version_id}/activate",
    response_model=JudgeProfileVersionResponse,
)
async def activate_judge_profile_version(
    challenge_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: JudgeProfileVersionActivateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> JudgeProfileVersionResponse:
    version = await session.get(JudgeProfileVersion, version_id)
    if version is None or version.challenge_id != challenge_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="judge profile version not found")
    if version.lock_version != payload.expected_lock_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="judge profile version lock mismatch",
        )

    await session.execute(
        update(JudgeProfileVersion)
        .where(JudgeProfileVersion.challenge_id == challenge_id)
        .values(is_active=False)
    )
    version.is_active = True
    version.lock_version += 1
    await session.commit()
    await session.refresh(version)
    return _to_judge_profile_version_response(version)


@router.post(
    "/{challenge_id}/judge-profiles/url",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profile_url(
    challenge_id: uuid.UUID,
    payload: JudgeProfileURLRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    try:
        sanitized_url = sanitize_ingestion_url(payload.url)
        assert_url_allowed_for_challenge(challenge_id, sanitized_url)
        content = await fetch_url_content_cached(
            request.app.state.redis,
            sanitized_url,
            timeout_seconds=payload.timeout_seconds,
            max_bytes=payload.max_bytes,
        )
        assert_no_prompt_injection(content.decode("utf-8", errors="ignore"), source="judge_profile_url_content")
        source_format, parsed = parse_profile_payload(content)
    except URLSanitizationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"url not allowed: {exc}") from exc
    except URLAllowlistError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"url blocked by allowlist: {exc}") from exc
    except URLFetchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"url fetch failed: {exc}") from exc
    except ProfileParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "malformed_profile",
                "message": "unable to parse fetched profile",
                "parser_error": exc.as_payload(),
            },
        ) from exc
    except PromptInjectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"url content blocked: {exc}",
        ) from exc

    profiles = normalize_profiles(parsed)
    return await persist_profiles(challenge_id, profiles, f"url_{source_format}", session)

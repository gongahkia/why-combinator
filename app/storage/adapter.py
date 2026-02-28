from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.storage.local import LocalObjectStorageAdapter


class ObjectStorageAdapter(Protocol):
    def put_object(self, submission_id: uuid.UUID, original_filename: str, content: bytes) -> str:
        ...

    def get_object(self, storage_key: str) -> bytes:
        ...

    def get_object_size(self, storage_key: str) -> int | None:
        ...

    def exists(self, storage_key: str) -> bool:
        ...

    def delete_object(self, storage_key: str) -> bool:
        ...


@dataclass(frozen=True)
class S3StorageSettings:
    bucket: str
    endpoint_url: str | None
    region: str
    access_key_id: str | None
    secret_access_key: str | None
    key_prefix: str
    use_ssl: bool


def load_artifact_storage_backend() -> str:
    return os.getenv("ARTIFACT_STORAGE_BACKEND", "local").strip().lower()


def _load_s3_settings_from_env() -> S3StorageSettings:
    bucket = os.getenv("ARTIFACT_STORAGE_S3_BUCKET", "").strip()
    if not bucket:
        raise ValueError("ARTIFACT_STORAGE_S3_BUCKET is required when ARTIFACT_STORAGE_BACKEND=s3")

    endpoint_url = os.getenv("ARTIFACT_STORAGE_S3_ENDPOINT_URL", "").strip() or None
    region = os.getenv("ARTIFACT_STORAGE_S3_REGION", "us-east-1").strip() or "us-east-1"
    access_key_id = os.getenv("ARTIFACT_STORAGE_S3_ACCESS_KEY_ID", "").strip() or None
    secret_access_key = os.getenv("ARTIFACT_STORAGE_S3_SECRET_ACCESS_KEY", "").strip() or None
    key_prefix = os.getenv("ARTIFACT_STORAGE_S3_KEY_PREFIX", "").strip().strip("/")
    use_ssl = os.getenv("ARTIFACT_STORAGE_S3_USE_SSL", "true").strip().lower() not in {"0", "false", "no"}

    return S3StorageSettings(
        bucket=bucket,
        endpoint_url=endpoint_url,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        key_prefix=key_prefix,
        use_ssl=use_ssl,
    )


def _build_s3_client(settings: S3StorageSettings) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for ARTIFACT_STORAGE_BACKEND=s3") from exc

    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        region_name=settings.region,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        use_ssl=settings.use_ssl,
    )


class S3ObjectStorageAdapter:
    def __init__(self, settings: S3StorageSettings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or _build_s3_client(settings)

    def _build_storage_key(self, submission_id: uuid.UUID, original_filename: str, content_hash: str) -> str:
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        key = f"{submission_id}/{content_hash}_{safe_name}"
        if self._settings.key_prefix:
            return f"{self._settings.key_prefix}/{key}"
        return key

    def put_object(self, submission_id: uuid.UUID, original_filename: str, content: bytes) -> str:
        content_hash = hashlib.sha256(content).hexdigest()
        key = self._build_storage_key(submission_id, original_filename, content_hash)
        self._client.put_object(
            Bucket=self._settings.bucket,
            Key=key,
            Body=content,
        )
        return key

    def get_object(self, storage_key: str) -> bytes:
        try:
            payload = self._client.get_object(Bucket=self._settings.bucket, Key=storage_key)
        except Exception as exc:  # noqa: BLE001
            raise FileNotFoundError(storage_key) from exc
        body = payload.get("Body")
        if body is None:
            raise FileNotFoundError(storage_key)
        data = body.read()
        return data if isinstance(data, bytes) else bytes(data)

    def get_object_size(self, storage_key: str) -> int | None:
        try:
            payload = self._client.head_object(Bucket=self._settings.bucket, Key=storage_key)
        except Exception:  # noqa: BLE001
            return None
        content_length = payload.get("ContentLength")
        if isinstance(content_length, int):
            return content_length
        return None

    def exists(self, storage_key: str) -> bool:
        return self.get_object_size(storage_key) is not None

    def delete_object(self, storage_key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self._settings.bucket, Key=storage_key)
            return True
        except Exception:  # noqa: BLE001
            return False


def build_object_storage_adapter(storage_root_path: str) -> ObjectStorageAdapter:
    backend = load_artifact_storage_backend()
    if backend == "local":
        return LocalObjectStorageAdapter(storage_root_path)
    if backend == "s3":
        settings = _load_s3_settings_from_env()
        return S3ObjectStorageAdapter(settings)
    raise ValueError(f"unsupported ARTIFACT_STORAGE_BACKEND: {backend}")

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest

from app.storage.adapter import S3ObjectStorageAdapter, build_object_storage_adapter
from app.storage.local import LocalObjectStorageAdapter


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str) -> dict[str, io.BytesIO]:  # noqa: N803
        payload = self.objects[(Bucket, Key)]
        return {"Body": io.BytesIO(payload)}

    def head_object(self, Bucket: str, Key: str) -> dict[str, int]:  # noqa: N803
        payload = self.objects[(Bucket, Key)]
        return {"ContentLength": len(payload)}

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop((Bucket, Key), None)


def test_storage_adapter_factory_defaults_to_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ARTIFACT_STORAGE_BACKEND", raising=False)

    adapter = build_object_storage_adapter(str(tmp_path))

    assert isinstance(adapter, LocalObjectStorageAdapter)
    key = adapter.put_object(uuid.uuid4(), "artifact.txt", b"hello")
    assert adapter.exists(key)
    assert adapter.get_object(key) == b"hello"
    assert adapter.get_object_size(key) == 5
    assert adapter.delete_object(key)


def test_storage_adapter_factory_supports_s3_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeS3Client()
    monkeypatch.setenv("ARTIFACT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("ARTIFACT_STORAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("ARTIFACT_STORAGE_S3_KEY_PREFIX", "artifacts")
    monkeypatch.setattr("app.storage.adapter._build_s3_client", lambda settings: fake_client)

    adapter = build_object_storage_adapter("/tmp/unused")

    assert isinstance(adapter, S3ObjectStorageAdapter)
    key = adapter.put_object(uuid.uuid4(), "artifact.txt", b"abc")
    assert key.startswith("artifacts/")
    assert adapter.exists(key)
    assert adapter.get_object(key) == b"abc"
    assert adapter.get_object_size(key) == 3
    assert adapter.delete_object(key)
    assert not adapter.exists(key)

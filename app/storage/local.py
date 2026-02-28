from __future__ import annotations

import hashlib
import io
import os
import tarfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath


class ArchiveExtractionError(ValueError):
    pass


def _ensure_safe_member_path(raw_name: str) -> None:
    name = raw_name.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ArchiveExtractionError(f"archive member path is absolute: {raw_name}")
    if any(part == ".." for part in path.parts):
        raise ArchiveExtractionError(f"archive member path escapes target directory: {raw_name}")


def validate_archive_members_safe(content: bytes, filename: str) -> None:
    lowered = filename.lower()
    if lowered.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for member in archive.infolist():
                _ensure_safe_member_path(member.filename)
        return
    if lowered.endswith(".tar") or lowered.endswith(".tar.gz") or lowered.endswith(".tgz"):
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            for member in archive.getmembers():
                _ensure_safe_member_path(member.name)
                if member.issym() or member.islnk():
                    _ensure_safe_member_path(member.linkname)
        return


class LocalObjectStorageAdapter:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "blobs").mkdir(parents=True, exist_ok=True)

    def put_object(self, submission_id: uuid.UUID, original_filename: str, content: bytes) -> str:
        content_hash = hashlib.sha256(content).hexdigest()
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        key = f"{submission_id}/{content_hash}_{safe_name}"
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        canonical_blob = self._root / "blobs" / content_hash
        if not canonical_blob.exists():
            canonical_blob.write_bytes(content)

        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            relative_blob_path = os.path.relpath(canonical_blob, target.parent)
            target.symlink_to(relative_blob_path)
        except OSError:
            target.write_bytes(content)
        return key

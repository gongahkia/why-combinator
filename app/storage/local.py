from __future__ import annotations

import hashlib
import uuid
from pathlib import Path


class LocalObjectStorageAdapter:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def put_object(self, submission_id: uuid.UUID, original_filename: str, content: bytes) -> str:
        content_hash = hashlib.sha256(content).hexdigest()
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        key = f"{submission_id}/{content_hash}_{safe_name}"
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

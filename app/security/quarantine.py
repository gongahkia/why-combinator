from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path


def _sanitize_filename(filename: str) -> str:
    candidate = filename.strip() or "artifact.bin"
    candidate = Path(candidate).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", candidate)
    return sanitized or "artifact.bin"


def quarantine_rejected_artifact(
    storage_root: str,
    *,
    submission_id: uuid.UUID,
    filename: str,
    content: bytes,
    reason: str,
) -> str | None:
    try:
        quarantine_root = Path(storage_root) / "quarantine" / str(submission_id)
        quarantine_root.mkdir(parents=True, exist_ok=True)

        safe_filename = _sanitize_filename(filename)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        artifact_path = quarantine_root / f"{stamp}_{safe_filename}"
        artifact_path.write_bytes(content)

        metadata = {
            "submission_id": str(submission_id),
            "filename": filename,
            "reason": reason,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "quarantined_at": datetime.now(UTC).isoformat(),
        }
        metadata_path = quarantine_root / f"{artifact_path.name}.metadata.json"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return str(artifact_path)
    except OSError:
        return None

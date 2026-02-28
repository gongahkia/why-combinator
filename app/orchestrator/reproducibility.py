from __future__ import annotations

import hashlib
import uuid

REPLAY_SEED_ALGORITHM = "sha256-v1"
_MAX_SEED = (2**31) - 1


def _stable_seed(material: str) -> int:
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % _MAX_SEED


def derive_run_replay_seed(run_id: uuid.UUID | str) -> int:
    return _stable_seed(f"run:{run_id}")


def derive_agent_prompt_seed(run_seed: int, agent_id: uuid.UUID | str) -> int:
    bounded_seed = max(0, int(run_seed))
    return _stable_seed(f"agent:{bounded_seed}:{agent_id}")


def coerce_replay_run_seed(config_snapshot: dict[str, object], run_id: uuid.UUID | str) -> int:
    reproducibility_raw = config_snapshot.get("reproducibility")
    if isinstance(reproducibility_raw, dict):
        run_seed = reproducibility_raw.get("run_seed")
        if isinstance(run_seed, int) and run_seed >= 0:
            return run_seed
    return derive_run_replay_seed(run_id)

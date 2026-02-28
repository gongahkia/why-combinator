from __future__ import annotations

import os


BLOCKED_METADATA_HOSTS: tuple[str, ...] = (
    "metadata.google.internal",
    "instance-data.ec2.internal",
    "metadata.azure.internal",
    "metadata.aliyun.internal",
)

BLOCKED_METADATA_IP_RANGES: tuple[str, ...] = (
    "169.254.169.254/32",
    "100.100.100.200/32",
    "169.254.170.2/32",
)


def load_hacker_runner_network_mode() -> str:
    return os.getenv("HACKER_RUNNER_NETWORK_MODE", "none").strip().lower()


def enforce_hacker_runner_network_policy(network_mode: str) -> None:
    # Policy requires isolated networking so metadata endpoints and identity ranges remain unreachable.
    if network_mode != "none":
        blocked_ranges = ", ".join(BLOCKED_METADATA_IP_RANGES)
        raise ValueError(
            "sandbox network policy requires HACKER_RUNNER_NETWORK_MODE=none "
            f"(cloud metadata ranges blocked: {blocked_ranges})"
        )


def metadata_sinkhole_hosts() -> tuple[str, ...]:
    return BLOCKED_METADATA_HOSTS

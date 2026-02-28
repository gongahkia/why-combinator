from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxImagePolicy:
    base_image: str
    pip_index_url: str
    npm_registry_url: str
    apt_mirror_url: str


def load_default_image_policy() -> SandboxImagePolicy:
    return SandboxImagePolicy(
        base_image=os.getenv("SANDBOX_BASE_IMAGE", "python:3.12-slim"),
        pip_index_url=os.getenv("SANDBOX_PIP_INDEX_URL", "https://pypi.org/simple"),
        npm_registry_url=os.getenv("SANDBOX_NPM_REGISTRY_URL", "https://registry.npmjs.org"),
        apt_mirror_url=os.getenv("SANDBOX_APT_MIRROR_URL", "http://deb.debian.org/debian"),
    )


def _render_dockerfile(policy: SandboxImagePolicy) -> str:
    return f"""
FROM {policy.base_image}
ENV PIP_INDEX_URL={policy.pip_index_url}
ENV NPM_CONFIG_REGISTRY={policy.npm_registry_url}
RUN sed -i 's|http://deb.debian.org/debian|{policy.apt_mirror_url}|g' /etc/apt/sources.list.d/debian.sources || true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 10001 sandbox
USER sandbox
WORKDIR /workspace
"""


def build_sandbox_image(tag: str, policy: SandboxImagePolicy | None = None) -> str:
    active_policy = policy or load_default_image_policy()
    dockerfile_content = _render_dockerfile(active_policy)
    with tempfile.TemporaryDirectory(prefix="sandbox-image-") as temp_dir:
        dockerfile_path = Path(temp_dir) / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
        subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(dockerfile_path), temp_dir],
            check=True,
            capture_output=True,
            text=True,
        )
    return tag

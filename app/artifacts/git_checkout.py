from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class GitCheckoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitCheckoutResult:
    checkout_path: str
    commit: str


def _validate_repo_url(repo_url: str) -> None:
    if repo_url.startswith("https://"):
        return
    if repo_url.startswith("git@"):
        return
    raise GitCheckoutError("repository URL must use https:// or git@ syntax")


def _run_git(args: list[str], cwd: Path, timeout_seconds: int) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise GitCheckoutError(completed.stderr.strip() or f"git command failed: {' '.join(args)}")
    return completed.stdout.strip()


def isolated_git_checkout(
    *,
    repository_url: str,
    commit: str,
    destination_root: str,
    shallow_depth: int = 1,
    timeout_seconds: int = 120,
) -> GitCheckoutResult:
    if not commit.strip():
        raise GitCheckoutError("commit pin is required for repository artifact checkout")
    _validate_repo_url(repository_url)

    root = Path(destination_root)
    root.mkdir(parents=True, exist_ok=True)
    isolated_dir = Path(tempfile.mkdtemp(prefix="repo-artifact-", dir=root))
    try:
        _run_git(
            [
                "clone",
                "--depth",
                str(max(1, shallow_depth)),
                "--filter=blob:none",
                "--no-tags",
                repository_url,
                str(isolated_dir),
            ],
            cwd=root,
            timeout_seconds=timeout_seconds,
        )
        _run_git(
            ["fetch", "--depth", str(max(1, shallow_depth)), "origin", commit],
            cwd=isolated_dir,
            timeout_seconds=timeout_seconds,
        )
        _run_git(["checkout", "--detach", commit], cwd=isolated_dir, timeout_seconds=timeout_seconds)
        resolved_commit = _run_git(["rev-parse", "HEAD"], cwd=isolated_dir, timeout_seconds=timeout_seconds)
        if not resolved_commit.startswith(commit):
            raise GitCheckoutError(f"resolved commit '{resolved_commit}' does not match requested pin '{commit}'")
        return GitCheckoutResult(checkout_path=str(isolated_dir), commit=resolved_commit)
    except Exception:
        shutil.rmtree(isolated_dir, ignore_errors=True)
        raise

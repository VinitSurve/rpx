"""Safe git CLI wrappers for local analytics."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_git_available() -> bool:
    """Check if the git CLI executable is available on PATH."""
    return shutil.which("git") is not None


def run_git(args: list[str], cwd: Path, timeout: float = 10.0) -> tuple[int, str, str]:
    """Execute a git command safely with timeout and output capture.

    Returns (returncode, stdout, stderr).
    """
    if not is_git_available():
        return -1, "", "git command not found on PATH"

    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "git command timed out"
    except (OSError, PermissionError) as e:
        return -1, "", str(e)


def is_git_repository(path: Path) -> bool:
    """Check if the directory is inside a valid git working tree."""
    code, stdout, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return code == 0 and stdout.strip().lower() == "true"


def get_git_root(path: Path) -> Path | None:
    """Find the top-level root of the git repository if present."""
    code, stdout, _ = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if code == 0 and stdout.strip():
        return Path(stdout.strip()).resolve()
    return None

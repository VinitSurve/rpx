"""Project metadata extraction, root detection, and environment diagnostics."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Sequence

from rpx.models import FileInfo, ProjectMetadata
from rpx.utils.filesystem import get_creation_time, get_safe_stat
from rpx.utils.git_utils import get_git_root, is_git_available, is_git_repository


def detect_project_root(target_path: Path) -> Path:
    """Find the logical project root starting from target_path.

    Checks for git root or manifest files going upwards up to 5 levels.
    """
    resolved = target_path.resolve()
    if not resolved.exists():
        return resolved

    # 1. If inside a Git repository, check if target_path is within git root
    git_root = get_git_root(resolved)
    if git_root and git_root.is_dir():
        # If target_path is git_root or subfolder, git_root is the primary project boundary
        # But if user explicitly gave a subfolder, and it contains project manifests, respect it
        manifest_markers = ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml"]
        if any((resolved / m).is_file() for m in manifest_markers):
            return resolved
        return git_root

    # 2. Check for project manifests walking up
    curr = resolved
    for _ in range(5):
        if any(
            (curr / m).is_file() for m in ["pyproject.toml", "package.json", "Cargo.toml", "go.mod"]
        ):
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent

    return resolved


def extract_project_name(project_root: Path) -> str:
    """Detect project name from manifest or directory name."""
    # Check pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            name = data.get("project", {}).get("name") or data.get("tool", {}).get(
                "poetry", {}
            ).get("name")
            if name:
                return str(name)
        except Exception:
            pass

    # Check package.json
    pkg_json = project_root / "package.json"
    if pkg_json.is_file():
        try:
            import json

            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name")
            if name:
                return str(name)
        except Exception:
            pass

    # Check Cargo.toml
    cargo = project_root / "Cargo.toml"
    if cargo.is_file():
        try:
            import tomllib

            with open(cargo, "rb") as f:
                data = tomllib.load(f)
            name = data.get("package", {}).get("name")
            if name:
                return str(name)
        except Exception:
            pass

    return project_root.name or str(project_root)


def build_metadata(
    project_root: Path,
    file_infos: Sequence[FileInfo],
    detected_ecosystems: Sequence[str],
    first_commit_date: str | None = None,
    last_commit_date: str | None = None,
    scan_duration: float = 0.0,
) -> ProjectMetadata:
    """Assemble all project metadata and runtime environment indicators."""
    stat_res = get_safe_stat(project_root)
    created_at = get_creation_time(stat_res)

    # Most recent file modification
    last_modified = None
    if file_infos:
        latest_file = max(file_infos, key=lambda f: f.modified_time)
        last_modified = latest_file.modified_time

    total_size = sum(f.size_bytes for f in file_infos)

    # Ecosystems / project types
    types = list(detected_ecosystems)
    if len(types) > 1 and "Monorepo" not in types:
        types.insert(0, "Monorepo")
    elif not types:
        types = ["General Software"]

    os_desc = f"{platform.system()} {platform.release()} ({platform.machine()})"

    return ProjectMetadata(
        name=extract_project_name(project_root),
        path=str(project_root.resolve()),
        project_types=types,
        created_at=created_at,
        first_commit_date=first_commit_date,
        last_modified=last_modified,
        last_commit_date=last_commit_date,
        total_size_bytes=total_size,
        scan_duration_seconds=scan_duration,
        os_info=os_desc,
        python_version=platform.python_version(),
        git_available=is_git_available(),
        is_git_repo=is_git_repository(project_root),
    )

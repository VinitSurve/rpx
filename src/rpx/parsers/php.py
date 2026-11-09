"""PHP Composer manifest and lockfile parsers."""

from __future__ import annotations

import json
from pathlib import Path

from rpx.models import DependencyInfo


def parse_composer_json(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse composer.json for declared packages."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return direct_deps, dev_deps

        for name, ver in data.get("require", {}).items():
            if name.lower() == "php":
                continue
            direct_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="direct",
                    ecosystem="composer",
                )
            )

        for name, ver in data.get("require-dev", {}).items():
            dev_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="dev",
                    ecosystem="composer",
                )
            )
    except (OSError, json.JSONDecodeError):
        pass

    return direct_deps, dev_deps


def parse_composer_lock(path: Path) -> list[DependencyInfo]:
    """Parse composer.lock for locked packages."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return locked

        for section in ("packages", "packages-dev"):
            for pkg in data.get(section, []):
                if isinstance(pkg, dict):
                    name = pkg.get("name")
                    ver = pkg.get("version")
                    if name:
                        locked.append(
                            DependencyInfo(
                                name=str(name),
                                resolved_version=str(ver) if ver else None,
                                dep_type="locked",
                                ecosystem="composer",
                            )
                        )
    except (OSError, json.JSONDecodeError):
        pass

    return locked


def inspect_composer_vendor(project_root: Path) -> list[DependencyInfo]:
    """Inspect vendor/ directory for installed Composer packages."""
    installed: list[DependencyInfo] = []
    vendor_dir = project_root / "vendor"
    if not vendor_dir.is_dir():
        return installed

    try:
        for org in vendor_dir.iterdir():
            if org.name.startswith(".") or org.name in ("bin", "composer"):
                continue
            if org.is_dir():
                for pkg in org.iterdir():
                    if not pkg.name.startswith(".") and pkg.is_dir():
                        installed.append(
                            DependencyInfo(
                                name=f"{org.name}/{pkg.name}",
                                dep_type="installed",
                                ecosystem="composer",
                            )
                        )
    except (OSError, PermissionError):
        pass

    return installed

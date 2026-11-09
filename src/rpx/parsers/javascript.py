"""JavaScript and TypeScript ecosystem manifest and lockfile parsers."""

from __future__ import annotations

import json
from pathlib import Path

from rpx.models import DependencyInfo


def parse_package_json(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse package.json returning (direct_deps, dev_deps)."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return direct_deps, dev_deps

        # Direct dependencies
        for name, ver in data.get("dependencies", {}).items():
            direct_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="direct",
                    ecosystem="npm",
                )
            )

        # Peer and optional dependencies
        for name, ver in data.get("optionalDependencies", {}).items():
            direct_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="optional",
                    ecosystem="npm",
                )
            )

        for name, ver in data.get("peerDependencies", {}).items():
            direct_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="peer",
                    ecosystem="npm",
                )
            )

        # Dev dependencies
        for name, ver in data.get("devDependencies", {}).items():
            dev_deps.append(
                DependencyInfo(
                    name=str(name),
                    constraint=str(ver),
                    dep_type="dev",
                    ecosystem="npm",
                )
            )

    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass

    return direct_deps, dev_deps


def parse_package_lock_json(path: Path) -> list[DependencyInfo]:
    """Parse package-lock.json to extract locked dependencies."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return locked

        # Lockfile v2 / v3
        if "packages" in data and isinstance(data["packages"], dict):
            for pkg_path, pkg_info in data["packages"].items():
                if not pkg_path or not isinstance(pkg_info, dict):
                    continue
                # Extract clean package name from node_modules/foo/node_modules/bar
                name = pkg_path.split("node_modules/")[-1]
                if name:
                    version = str(pkg_info.get("version", ""))
                    locked.append(
                        DependencyInfo(
                            name=name,
                            resolved_version=version,
                            dep_type="locked",
                            ecosystem="npm",
                        )
                    )
        # Lockfile v1 fallback
        elif "dependencies" in data and isinstance(data["dependencies"], dict):
            for name, pkg_info in data["dependencies"].items():
                if isinstance(pkg_info, dict):
                    version = str(pkg_info.get("version", ""))
                    locked.append(
                        DependencyInfo(
                            name=str(name),
                            resolved_version=version,
                            dep_type="locked",
                            ecosystem="npm",
                        )
                    )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass

    return locked


def parse_yarn_lock(path: Path) -> list[DependencyInfo]:
    """Parse yarn.lock to extract locked dependencies."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            current_name = None
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                # Package header line, e.g. "foo@^1.0.0", foo@^1.0.0:
                if not line.startswith(" ") and not line.startswith("\t"):
                    header = line_str.split(":")[0].strip().strip('"')
                    # Strip version specifier from header to get name
                    parts = header.split(",")
                    first_part = parts[0].strip().strip('"')
                    if "@" in first_part:
                        if first_part.startswith("@"):
                            # Scoped package, e.g. @babel/core@^7.0.0
                            sub_parts = first_part[1:].split("@")
                            current_name = "@" + sub_parts[0]
                        else:
                            current_name = first_part.split("@")[0]
                    else:
                        current_name = first_part
                elif current_name and line_str.startswith("version "):
                    version = line_str.split("version ")[1].strip().strip('"')
                    locked.append(
                        DependencyInfo(
                            name=current_name,
                            resolved_version=version,
                            dep_type="locked",
                            ecosystem="npm",
                        )
                    )
                    current_name = None
    except (OSError, UnicodeDecodeError):
        pass
    return locked


def parse_pnpm_lock(path: Path) -> list[DependencyInfo]:
    """Parse pnpm-lock.yaml to count locked packages."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            in_packages = False
            for line in f:
                if line.startswith("packages:"):
                    in_packages = True
                    continue
                if in_packages:
                    if line and not line[0].isspace():
                        # Exited packages section
                        break
                    # Lines like '  /@babel/code-frame/7.12.11:' or '  /lodash/4.17.21:'
                    stripped = line.strip()
                    if (
                        stripped.startswith("/")
                        or stripped.startswith("'")
                        or stripped.startswith('"')
                    ):
                        entry = stripped.strip(":'\"")
                        if entry.startswith("/"):
                            entry = entry[1:]
                        # Name/version split
                        parts = entry.rsplit("/", 1)
                        name = parts[0]
                        ver = parts[1] if len(parts) > 1 else ""
                        if name:
                            locked.append(
                                DependencyInfo(
                                    name=name,
                                    resolved_version=ver,
                                    dep_type="locked",
                                    ecosystem="npm",
                                )
                            )
    except (OSError, UnicodeDecodeError):
        pass
    return locked


def inspect_node_modules(project_root: Path) -> list[DependencyInfo]:
    """Inspect local node_modules directory to verify installed packages."""
    installed: list[DependencyInfo] = []
    nm_path = project_root / "node_modules"
    if not nm_path.is_dir():
        return installed

    try:
        for entry in nm_path.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.name.startswith("@") and entry.is_dir():
                # Scoped packages
                try:
                    for sub_entry in entry.iterdir():
                        if not sub_entry.name.startswith(".") and sub_entry.is_dir():
                            pkg_name = f"{entry.name}/{sub_entry.name}"
                            installed.append(
                                DependencyInfo(
                                    name=pkg_name,
                                    dep_type="installed",
                                    ecosystem="npm",
                                )
                            )
                except (OSError, PermissionError):
                    continue
            elif entry.is_dir():
                installed.append(
                    DependencyInfo(
                        name=entry.name,
                        dep_type="installed",
                        ecosystem="npm",
                    )
                )
    except (OSError, PermissionError):
        pass

    return installed

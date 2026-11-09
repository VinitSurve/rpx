"""Python ecosystem manifest, lockfile, and virtualenv parsers."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from rpx.models import DependencyInfo


def _clean_req_line(line: str) -> str | None:
    """Clean a requirements.txt line, removing comments and environment markers."""
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-") or line.startswith("--"):
        return None
    # Strip inline comments
    if " #" in line:
        line = line.split(" #")[0].strip()
    # Strip environment markers (; python_version >= '3.10')
    if ";" in line:
        line = line.split(";")[0].strip()
    return line if line else None


def parse_requirements_txt(path: Path, is_dev: bool = False) -> list[DependencyInfo]:
    """Parse requirements.txt or requirements-dev.txt for dependency specs."""
    deps: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = _clean_req_line(line)
                if not cleaned:
                    continue

                # Match package name and version operator (e.g. package>=1.0.0, package[extra]==2.0)
                match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[.*?\])?\s*([<>=!~].*)?$", cleaned)
                if match:
                    name = match.group(1).lower()
                    constraint = match.group(2) or ""
                    deps.append(
                        DependencyInfo(
                            name=name,
                            constraint=constraint.strip(),
                            dep_type="dev" if is_dev else "direct",
                            ecosystem="pypi",
                        )
                    )
                else:
                    # Plain package name without version constraint
                    parts = cleaned.split()
                    if parts:
                        deps.append(
                            DependencyInfo(
                                name=parts[0].lower(),
                                dep_type="dev" if is_dev else "direct",
                                ecosystem="pypi",
                            )
                        )
    except (OSError, UnicodeDecodeError):
        pass
    return deps


def parse_pyproject_toml(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse pyproject.toml for PEP 621, Poetry, or Flit dependencies."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        if not isinstance(data, dict):
            return direct_deps, dev_deps

        # 1. PEP 621 [project.dependencies]
        project = data.get("project", {})
        if isinstance(project, dict):
            raw_deps = project.get("dependencies", [])
            if isinstance(raw_deps, list):
                for dep_str in raw_deps:
                    if isinstance(dep_str, str):
                        cleaned = _clean_req_line(dep_str)
                        if cleaned:
                            match = re.match(
                                r"^([a-zA-Z0-9_\-\.]+)(?:\[.*?\])?\s*([<>=!~].*)?$", cleaned
                            )
                            if match:
                                direct_deps.append(
                                    DependencyInfo(
                                        name=match.group(1).lower(),
                                        constraint=(match.group(2) or "").strip(),
                                        dep_type="direct",
                                        ecosystem="pypi",
                                    )
                                )

            # Optional dependencies
            opt_deps = project.get("optional-dependencies", {})
            if isinstance(opt_deps, dict):
                for group_name, group_list in opt_deps.items():
                    is_dev = any(d in group_name.lower() for d in ["dev", "test", "lint"])
                    if isinstance(group_list, list):
                        for dep_str in group_list:
                            if isinstance(dep_str, str):
                                cleaned = _clean_req_line(dep_str)
                                if cleaned:
                                    match = re.match(
                                        r"^([a-zA-Z0-9_\-\.]+)(?:\[.*?\])?\s*([<>=!~].*)?$", cleaned
                                    )
                                    if match:
                                        target_list = dev_deps if is_dev else direct_deps
                                        target_list.append(
                                            DependencyInfo(
                                                name=match.group(1).lower(),
                                                constraint=(match.group(2) or "").strip(),
                                                dep_type="dev" if is_dev else "optional",
                                                ecosystem="pypi",
                                            )
                                        )

        # 2. Poetry [tool.poetry.dependencies]
        poetry = data.get("tool", {}).get("poetry", {})
        if isinstance(poetry, dict):
            p_deps = poetry.get("dependencies", {})
            if isinstance(p_deps, dict):
                for name, spec in p_deps.items():
                    if name.lower() == "python":
                        continue
                    constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                    direct_deps.append(
                        DependencyInfo(
                            name=name.lower(),
                            constraint=constraint,
                            dep_type="direct",
                            ecosystem="pypi",
                        )
                    )

            # Poetry group dependencies
            group = poetry.get("group", {})
            if isinstance(group, dict):
                for group_name, g_info in group.items():
                    if isinstance(g_info, dict):
                        g_deps = g_info.get("dependencies", {})
                        if isinstance(g_deps, dict):
                            is_dev = any(d in group_name.lower() for d in ["dev", "test", "lint"])
                            for name, spec in g_deps.items():
                                constraint = (
                                    spec if isinstance(spec, str) else str(spec.get("version", ""))
                                )
                                dev_deps.append(
                                    DependencyInfo(
                                        name=name.lower(),
                                        constraint=constraint,
                                        dep_type="dev" if is_dev else "optional",
                                        ecosystem="pypi",
                                    )
                                )

    except (OSError, tomllib.TOMLDecodeError):
        pass

    return direct_deps, dev_deps


def parse_poetry_or_uv_lock(path: Path) -> list[DependencyInfo]:
    """Parse poetry.lock or uv.lock for locked package distributions."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        packages = data.get("package", [])
        if isinstance(packages, list):
            for pkg in packages:
                if isinstance(pkg, dict):
                    name = pkg.get("name")
                    ver = pkg.get("version")
                    if name:
                        locked.append(
                            DependencyInfo(
                                name=str(name).lower(),
                                resolved_version=str(ver) if ver else None,
                                dep_type="locked",
                                ecosystem="pypi",
                            )
                        )
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return locked


def parse_pipfile(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Pipfile for declared dependencies."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        packages = data.get("packages", {})
        if isinstance(packages, dict):
            for name, spec in packages.items():
                constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                direct_deps.append(
                    DependencyInfo(
                        name=name.lower(),
                        constraint=constraint,
                        dep_type="direct",
                        ecosystem="pypi",
                    )
                )

        dev_packages = data.get("dev-packages", {})
        if isinstance(dev_packages, dict):
            for name, spec in dev_packages.items():
                constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                dev_deps.append(
                    DependencyInfo(
                        name=name.lower(),
                        constraint=constraint,
                        dep_type="dev",
                        ecosystem="pypi",
                    )
                )
    except (OSError, tomllib.TOMLDecodeError):
        pass

    return direct_deps, dev_deps


def parse_pipfile_lock(path: Path) -> list[DependencyInfo]:
    """Parse Pipfile.lock for locked packages."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for section in ("default", "develop"):
            sec_dict = data.get(section, {})
            if isinstance(sec_dict, dict):
                for name, info in sec_dict.items():
                    ver = info.get("version", "") if isinstance(info, dict) else ""
                    locked.append(
                        DependencyInfo(
                            name=str(name).lower(),
                            resolved_version=ver.lstrip("="),
                            dep_type="locked",
                            ecosystem="pypi",
                        )
                    )
    except (OSError, json.JSONDecodeError):
        pass
    return locked


def inspect_python_virtualenv(project_root: Path) -> list[DependencyInfo]:
    """Inspect local project virtual environments (.venv, venv, env) for installed packages.

    Exclusively checks project-local directories to never report system/global packages.
    """
    installed: list[DependencyInfo] = []
    candidate_dirs = [".venv", "venv", "env", ".env"]

    for cand_name in candidate_dirs:
        cand_path = project_root / cand_name
        if not cand_path.is_dir():
            continue

        # Look for lib/python*/site-packages
        lib_dir = cand_path / "lib"
        if not lib_dir.is_dir():
            continue

        try:
            for py_dir in lib_dir.iterdir():
                if not py_dir.is_dir() or not py_dir.name.startswith("python"):
                    continue
                sp_dir = py_dir / "site-packages"
                if not sp_dir.is_dir():
                    continue

                for dist in sp_dir.iterdir():
                    if dist.name.endswith(".dist-info"):
                        # e.g. requests-2.28.1.dist-info
                        parts = dist.name[: -len(".dist-info")].rsplit("-", 1)
                        pkg_name = parts[0].replace("_", "-").lower()
                        pkg_ver = parts[1] if len(parts) > 1 else None
                        installed.append(
                            DependencyInfo(
                                name=pkg_name,
                                resolved_version=pkg_ver,
                                dep_type="installed",
                                ecosystem="pypi",
                            )
                        )
        except (OSError, PermissionError):
            pass

    return installed

"""Rust Cargo manifest and lockfile parser."""

from __future__ import annotations

import tomllib
from pathlib import Path

from rpx.models import DependencyInfo


def parse_cargo_toml(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Cargo.toml returning (direct_deps, dev_deps)."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        # [dependencies]
        deps = data.get("dependencies", {})
        if isinstance(deps, dict):
            for name, spec in deps.items():
                constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                direct_deps.append(
                    DependencyInfo(
                        name=name,
                        constraint=constraint,
                        dep_type="direct",
                        ecosystem="cargo",
                    )
                )

        # [build-dependencies]
        build_deps = data.get("build-dependencies", {})
        if isinstance(build_deps, dict):
            for name, spec in build_deps.items():
                constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                direct_deps.append(
                    DependencyInfo(
                        name=name,
                        constraint=constraint,
                        dep_type="build",
                        ecosystem="cargo",
                    )
                )

        # [dev-dependencies]
        dev = data.get("dev-dependencies", {})
        if isinstance(dev, dict):
            for name, spec in dev.items():
                constraint = spec if isinstance(spec, str) else str(spec.get("version", ""))
                dev_deps.append(
                    DependencyInfo(
                        name=name,
                        constraint=constraint,
                        dep_type="dev",
                        ecosystem="cargo",
                    )
                )
    except (OSError, tomllib.TOMLDecodeError):
        pass

    return direct_deps, dev_deps


def parse_cargo_lock(path: Path) -> list[DependencyInfo]:
    """Parse Cargo.lock for locked crate packages."""
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
                                name=str(name),
                                resolved_version=str(ver) if ver else None,
                                dep_type="locked",
                                ecosystem="cargo",
                            )
                        )
    except (OSError, tomllib.TOMLDecodeError):
        pass

    return locked

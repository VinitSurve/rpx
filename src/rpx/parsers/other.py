"""Parsers for Ruby, .NET, Dart, and Swift ecosystems."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from rpx.models import DependencyInfo


# ===================== RUBY =====================
def parse_gemfile(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse Ruby Gemfile for declared gems."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    pattern = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            in_group = False
            current_group = ""
            for line in f:
                line_str = line.strip()
                if line_str.startswith("group "):
                    in_group = True
                    current_group = line_str
                    continue
                elif line_str == "end":
                    in_group = False
                    current_group = ""
                    continue

                match = pattern.match(line_str)
                if match:
                    gem_name = match.group(1)
                    constraint = match.group(2) or ""
                    is_dev = in_group and any(
                        g in current_group.lower() for g in ["development", "test"]
                    )
                    dep = DependencyInfo(
                        name=gem_name,
                        constraint=constraint,
                        dep_type="dev" if is_dev else "direct",
                        ecosystem="rubygems",
                    )
                    if is_dev:
                        dev_deps.append(dep)
                    else:
                        direct_deps.append(dep)
    except OSError:
        pass
    return direct_deps, dev_deps


def parse_gemfile_lock(path: Path) -> list[DependencyInfo]:
    """Parse Gemfile.lock for locked gems."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            in_specs = False
            for line in f:
                if line.strip() == "specs:":
                    in_specs = True
                    continue
                if in_specs:
                    if line and not line.startswith(" "):
                        break
                    # Format: "    gem_name (1.2.3)"
                    if line.startswith("    ") and not line.startswith("      "):
                        parts = line.strip().split(" ")
                        gem_name = parts[0]
                        version = parts[1].strip("()") if len(parts) > 1 else ""
                        locked.append(
                            DependencyInfo(
                                name=gem_name,
                                resolved_version=version,
                                dep_type="locked",
                                ecosystem="rubygems",
                            )
                        )
    except OSError:
        pass
    return locked


# ===================== .NET =====================
def parse_csproj(path: Path) -> list[DependencyInfo]:
    """Parse .csproj for PackageReference items."""
    deps: list[DependencyInfo] = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for ref in root.iter("PackageReference"):
            name = ref.attrib.get("Include") or ref.attrib.get("Update")
            version = ref.attrib.get("Version") or ""
            if not version:
                ver_elem = ref.find("Version")
                if ver_elem is not None and ver_elem.text:
                    version = ver_elem.text
            if name:
                deps.append(
                    DependencyInfo(
                        name=name,
                        constraint=version,
                        dep_type="direct",
                        ecosystem="nuget",
                    )
                )
    except (ET.ParseError, OSError):
        pass
    return deps


# ===================== DART / FLUTTER =====================
def parse_pubspec_yaml(path: Path) -> tuple[list[DependencyInfo], list[DependencyInfo]]:
    """Parse pubspec.yaml for dependencies."""
    direct_deps: list[DependencyInfo] = []
    dev_deps: list[DependencyInfo] = []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            section = None
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if line.startswith("dependencies:"):
                    section = "direct"
                    continue
                elif line.startswith("dev_dependencies:"):
                    section = "dev"
                    continue
                elif line and not line[0].isspace() and ":" in line:
                    section = None
                    continue

                if section and line.startswith("  ") and not line.startswith("    "):
                    parts = stripped.split(":", 1)
                    pkg_name = parts[0].strip()
                    constraint = parts[1].strip() if len(parts) > 1 else ""
                    if pkg_name.lower() not in ("flutter", "sdk"):
                        dep = DependencyInfo(
                            name=pkg_name,
                            constraint=constraint,
                            dep_type="dev" if section == "dev" else "direct",
                            ecosystem="pub",
                        )
                        if section == "dev":
                            dev_deps.append(dep)
                        else:
                            direct_deps.append(dep)
    except OSError:
        pass
    return direct_deps, dev_deps


# ===================== SWIFT =====================
def parse_swift_resolved(path: Path) -> list[DependencyInfo]:
    """Parse Package.resolved for locked Swift packages."""
    locked: list[DependencyInfo] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        pins = []
        if "pins" in data and isinstance(data["pins"], list):
            pins = data["pins"]
        elif "object" in data and isinstance(data["object"], dict):
            pins = data["object"].get("pins", [])

        for pin in pins:
            if isinstance(pin, dict):
                identity = pin.get("identity") or pin.get("package")
                state = pin.get("state", {})
                ver = state.get("version") if isinstance(state, dict) else ""
                if identity:
                    locked.append(
                        DependencyInfo(
                            name=str(identity),
                            resolved_version=str(ver) if ver else None,
                            dep_type="locked",
                            ecosystem="swiftpm",
                        )
                    )
    except (OSError, json.JSONDecodeError):
        pass
    return locked

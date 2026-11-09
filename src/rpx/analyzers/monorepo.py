"""Monorepo and multi-package workspace detector and analyzer."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Sequence

from rpx.models import FileRecord, MonorepoAnalysis, WorkspacePackage

_MANIFEST_FILENAMES = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "build.gradle.kts": "Java/Kotlin (Gradle)",
}


def _parse_package_json_info(full_path: Path) -> tuple[str | None, list[str]]:
    try:
        data = json.loads(full_path.read_text(encoding="utf-8", errors="replace"))
        name = data.get("name")
        deps: list[str] = []
        for sec in ("dependencies", "devDependencies", "peerDependencies"):
            sec_dict = data.get(sec)
            if isinstance(sec_dict, dict):
                deps.extend(sec_dict.keys())
        return (str(name) if name else None, deps)
    except Exception:
        return None, []


def _parse_pyproject_info(full_path: Path) -> tuple[str | None, list[str]]:
    try:
        with open(full_path, "rb") as f:
            data = tomllib.load(f)
        proj = data.get("project", {})
        name = proj.get("name") or data.get("tool", {}).get("poetry", {}).get("name")
        deps: list[str] = []
        for raw in proj.get("dependencies", []):
            if isinstance(raw, str):
                pkg = re.split(r"[<>=!~;\[\s]", raw.strip())[0]
                if pkg:
                    deps.append(pkg)
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            deps.extend(k for k in poetry_deps if k != "python")
        return (str(name) if name else None, deps)
    except Exception:
        return None, []


def _parse_cargo_info(full_path: Path) -> tuple[str | None, list[str]]:
    try:
        with open(full_path, "rb") as f:
            data = tomllib.load(f)
        pkg = data.get("package", {})
        name = pkg.get("name")
        deps: list[str] = []
        for sec in ("dependencies", "dev-dependencies"):
            sec_dict = data.get(sec)
            if isinstance(sec_dict, dict):
                deps.extend(sec_dict.keys())
        return (str(name) if name else None, deps)
    except Exception:
        return None, []


def _parse_gomod_info(full_path: Path) -> tuple[str | None, list[str]]:
    try:
        text = full_path.read_text(encoding="utf-8", errors="replace")
        mod_match = re.search(r"^\s*module\s+(\S+)", text, re.MULTILINE)
        name = mod_match.group(1) if mod_match else full_path.parent.name
        deps = re.findall(r"^\s*([a-zA-Z0-9.\-_/]+)\s+v[0-9]", text, re.MULTILINE)
        return name, deps
    except Exception:
        return None, []


def analyze_monorepo(
    project_root: Path,
    files: Sequence[FileRecord],
) -> MonorepoAnalysis:
    """Detect workspace managers, sub-packages, boundaries, and inter-package relationships."""
    workspace_tools: list[str] = []
    rel_map = {f.relative_path.replace("\\", "/"): f for f in files}

    # 1. Check root workspace configuration files
    if "turbo.json" in rel_map:
        workspace_tools.append("Turborepo")
    if "nx.json" in rel_map:
        workspace_tools.append("Nx")
    if "lerna.json" in rel_map:
        workspace_tools.append("Lerna")
    if "pnpm-workspace.yaml" in rel_map:
        workspace_tools.append("pnpm Workspaces")
    if "go.work" in rel_map:
        workspace_tools.append("Go Workspace")
    if "settings.gradle" in rel_map or "settings.gradle.kts" in rel_map:
        content = ""
        for gfile in ("settings.gradle", "settings.gradle.kts"):
            if gfile in rel_map:
                try:
                    content += (project_root / gfile).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
        if "include(" in content or "include " in content:
            workspace_tools.append("Gradle Multi-Project")

    root_pkg_json = project_root / "package.json"
    if root_pkg_json.is_file():
        try:
            pdata = json.loads(root_pkg_json.read_text(encoding="utf-8", errors="replace"))
            if "workspaces" in pdata:
                if "yarn.lock" in rel_map:
                    workspace_tools.append("Yarn Workspaces")
                else:
                    workspace_tools.append("npm Workspaces")
        except Exception:
            pass

    root_pyproject = project_root / "pyproject.toml"
    if root_pyproject.is_file():
        try:
            with open(root_pyproject, "rb") as f:
                py_data = tomllib.load(f)
            if "workspace" in py_data.get("tool", {}).get("uv", {}):
                workspace_tools.append("uv Workspace")
        except Exception:
            pass

    root_cargo = project_root / "Cargo.toml"
    if root_cargo.is_file():
        try:
            with open(root_cargo, "rb") as f:
                c_data = tomllib.load(f)
            if "workspace" in c_data:
                workspace_tools.append("Cargo Workspace")
        except Exception:
            pass

    root_pom = project_root / "pom.xml"
    if root_pom.is_file():
        try:
            pom_text = root_pom.read_text(encoding="utf-8", errors="replace")
            if "<modules>" in pom_text:
                workspace_tools.append("Maven Multi-Module")
        except OSError:
            pass

    # 2. Discover sub-package manifests in subdirectories
    raw_packages: dict[str, WorkspacePackage] = {}
    pkg_all_deps: dict[str, list[str]] = {}

    for f in files:
        if f.name not in _MANIFEST_FILENAMES:
            continue
        rel_dir = str(Path(f.relative_path).parent).replace("\\", "/")
        if rel_dir == ".":
            # Root manifest is not a child sub-package boundary unless we only want sub-packages
            continue

        ecosystem = _MANIFEST_FILENAMES[f.name]
        full_manifest = project_root / f.relative_path

        pkg_name: str | None = None
        declared_deps: list[str] = []

        if f.name == "package.json":
            pkg_name, declared_deps = _parse_package_json_info(full_manifest)
        elif f.name == "pyproject.toml":
            pkg_name, declared_deps = _parse_pyproject_info(full_manifest)
        elif f.name == "Cargo.toml":
            pkg_name, declared_deps = _parse_cargo_info(full_manifest)
        elif f.name == "go.mod":
            pkg_name, declared_deps = _parse_gomod_info(full_manifest)
        else:
            pkg_name = Path(rel_dir).name

        if not pkg_name:
            pkg_name = Path(rel_dir).name

        if rel_dir not in raw_packages:
            raw_packages[rel_dir] = WorkspacePackage(
                name=pkg_name,
                path=rel_dir,
                ecosystem=ecosystem,
                manifest_file=f.relative_path,
            )
            pkg_all_deps[pkg_name] = declared_deps

    # Determine if this repository is a monorepo
    is_monorepo = bool(workspace_tools) or len(raw_packages) >= 2
    if len(raw_packages) >= 2 and not workspace_tools:
        ecosystems = sorted({p.ecosystem for p in raw_packages.values()})
        workspace_tools.append(f"Multi-Package ({', '.join(ecosystems)})")

    if not raw_packages:
        return MonorepoAnalysis(
            is_monorepo=is_monorepo,
            workspace_type=workspace_tools[0] if workspace_tools else None,
            workspace_tools=workspace_tools,
            packages=[],
            package_relationships=[],
        )

    # 3. Assign each file to its deepest matching workspace package (no double counting)
    sorted_pkg_dirs = sorted(raw_packages.keys(), key=lambda p: len(p), reverse=True)
    pkg_lang_lines: dict[str, dict[str, int]] = {d: {} for d in sorted_pkg_dirs}

    for f in files:
        norm_path = f.relative_path.replace("\\", "/")
        for pkg_dir in sorted_pkg_dirs:
            if norm_path.startswith(pkg_dir + "/"):
                wp = raw_packages[pkg_dir]
                wp.file_count += 1
                wp.code_lines += f.code_lines
                if f.is_source and f.language:
                    lang_map = pkg_lang_lines[pkg_dir]
                    lang_map[f.language] = lang_map.get(f.language, 0) + max(1, f.code_lines)
                break

    for pkg_dir, wp in raw_packages.items():
        lang_map = pkg_lang_lines[pkg_dir]
        if lang_map:
            wp.primary_language = max(lang_map.items(), key=lambda kv: kv[1])[0]

    # 4. Resolve internal vs external package dependencies
    known_pkg_names = {wp.name: wp for wp in raw_packages.values()}
    relationships: list[tuple[str, str]] = []

    for wp in raw_packages.values():
        deps = pkg_all_deps.get(wp.name, [])
        for d in sorted(set(deps)):
            # Check exact or last-segment match for Go modules
            matched_internal = None
            if d in known_pkg_names and d != wp.name:
                matched_internal = d
            else:
                for kname in known_pkg_names:
                    if kname != wp.name and (d.endswith("/" + kname) or kname.endswith("/" + d)):
                        matched_internal = kname
                        break

            if matched_internal:
                if matched_internal not in wp.internal_dependencies:
                    wp.internal_dependencies.append(matched_internal)
                    relationships.append((wp.name, matched_internal))
            else:
                if d not in wp.external_dependencies:
                    wp.external_dependencies.append(d)

    packages_list = sorted(raw_packages.values(), key=lambda x: x.path)
    return MonorepoAnalysis(
        is_monorepo=is_monorepo,
        workspace_type=workspace_tools[0] if workspace_tools else "Multi-Package",
        workspace_tools=workspace_tools,
        packages=packages_list,
        package_relationships=relationships,
    )

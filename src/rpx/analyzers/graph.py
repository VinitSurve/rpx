"""Internal module dependency graph, cycle detection, and architectural layer insights."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Sequence

from rpx.models import DependencyGraph, FileRecord, ModuleNode

# Standard library module names in Python 3.11+
_PYTHON_STDLIB: frozenset[str] = getattr(
    sys,
    "stdlib_module_names",
    frozenset(
        {
            "abc",
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "collections",
            "concurrent",
            "contextlib",
            "copy",
            "csv",
            "ctypes",
            "dataclasses",
            "datetime",
            "decimal",
            "difflib",
            "email",
            "enum",
            "errno",
            "fnmatch",
            "fractions",
            "functools",
            "gc",
            "getpass",
            " glob",
            "gzip",
            "hashlib",
            "heapq",
            "hmac",
            "html",
            "http",
            "importlib",
            "inspect",
            "io",
            "ipaddress",
            "itertools",
            "json",
            "keyword",
            "linecache",
            "locale",
            "logging",
            "lzma",
            "math",
            "mimetypes",
            "multiprocessing",
            "numbers",
            "operator",
            "os",
            "pathlib",
            "pickle",
            "platform",
            "plistlib",
            "pprint",
            "profile",
            "pstats",
            "queue",
            "quopri",
            "random",
            "re",
            "reprlib",
            "resource",
            "runpy",
            "sched",
            "secrets",
            "select",
            "selectors",
            "shelve",
            "shlex",
            "shutil",
            "signal",
            "site",
            "smtplib",
            "socket",
            "socketserver",
            "sqlite3",
            "ssl",
            "stat",
            "statistics",
            "string",
            "stringprep",
            "struct",
            "subprocess",
            "sys",
            "sysconfig",
            "syslog",
            "tarfile",
            "tempfile",
            "textwrap",
            "threading",
            "time",
            "timeit",
            "tkinter",
            "token",
            "tokenize",
            "tomllib",
            "trace",
            "traceback",
            "tracemalloc",
            "tty",
            "turtle",
            "types",
            "typing",
            "unicodedata",
            "unittest",
            "urllib",
            "uuid",
            "venv",
            "warnings",
            "wave",
            "weakref",
            "webbrowser",
            "wsgiref",
            "xml",
            "xmlrpc",
            "zipapp",
            "zipfile",
            "zipimport",
            "zlib",
            "__future__",
        }
    ),
)

_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[^'"]+from\s+)?|export\s+[^'"]+from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""
)
_GO_IMPORT_RE = re.compile(r'"([^"]+)"')
_RUST_USE_RE = re.compile(r"^\s*(?:pub\s+)?use\s+([a-zA-Z0-9_:]+)")

# Layer hierarchy (higher rank can depend on lower rank; lower rank should not depend on higher rank)
LAYER_RANK: dict[str, int] = {
    "tests": 60,
    "cli": 50,
    "presentation": 45,
    "core": 35,
    "analyzers": 30,
    "models": 20,
    "utils": 10,
}


def infer_module_layer(module_name: str, file_path: str) -> str:
    """Infer architectural layer from module name or path."""
    lower_path = file_path.lower()
    parts = set(re.split(r"[/.\\_-]", lower_path))

    if "test" in parts or "tests" in parts or lower_path.startswith("tests/"):
        return "tests"
    if any(k in parts for k in ("cli", "main", "cmd", "commands", "explore", "watch", "ci")):
        return "cli"
    if any(
        k in parts
        for k in ("reporters", "reporter", "ui", "views", "templates", "components", "pages")
    ):
        return "presentation"
    if any(k in parts for k in ("analyzers", "analyzer", "services", "controllers", "handlers")):
        return "analyzers"
    if any(
        k in parts
        for k in ("scanner", "engine", "core", "app", "server", "cache", "snapshots", "ai")
    ):
        return "core"
    if any(
        k in parts
        for k in (
            "models",
            "model",
            "schemas",
            "schema",
            "entities",
            "types",
            "constants",
            "exceptions",
            "config",
        )
    ):
        return "models"
    if any(k in parts for k in ("utils", "util", "helpers", "common", "lib", "shared")):
        return "utils"
    return "core"


def _python_module_name(rel_path: str) -> str:
    """Convert a Python relative file path to its logical dotted module name."""
    norm = rel_path.replace("\\", "/")
    if norm.startswith("src/"):
        norm = norm[4:]
    if norm.endswith("/__init__.py"):
        norm = norm[: -len("/__init__.py")]
    elif norm.endswith(".py"):
        norm = norm[:-3]
    return norm.replace("/", ".")


def _js_module_name(rel_path: str) -> str:
    norm = rel_path.replace("\\", "/")
    for ext in (".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
        if norm.endswith(ext):
            norm = norm[: -len(ext)]
            break
    if norm.endswith("/index"):
        norm = norm[: -len("/index")]
    return norm


def _resolve_relative_python_import(
    current_mod: str, is_pkg_init: bool, level: int, target: str | None
) -> str:
    parts = current_mod.split(".")
    if not is_pkg_init:
        parts = parts[:-1]
    up = max(0, level - 1)
    if up > 0 and up <= len(parts):
        parts = parts[:-up]
    if target:
        return ".".join(parts + [target]) if parts else target
    return ".".join(parts)


def _find_cycles(adj: dict[str, set[str]]) -> list[list[str]]:
    """Detect directed cycles in the module dependency graph using DFS."""
    visited: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []
    seen_cycle_keys: set[tuple[str, ...]] = set()

    def _dfs(node: str) -> None:
        visited.add(node)
        on_stack.add(node)
        stack.append(node)

        for nbr in sorted(adj.get(node, ())):
            if nbr not in visited:
                _dfs(nbr)
            elif nbr in on_stack:
                idx = stack.index(nbr)
                cycle_nodes = stack[idx:]
                # Canonicalize rotation to avoid duplicates
                min_pos = min(range(len(cycle_nodes)), key=lambda i: cycle_nodes[i])
                canonical = tuple(cycle_nodes[min_pos:] + cycle_nodes[:min_pos])
                if canonical not in seen_cycle_keys:
                    seen_cycle_keys.add(canonical)
                    cycles.append(list(canonical) + [canonical[0]])

        stack.pop()
        on_stack.remove(node)

    for n in sorted(adj.keys()):
        if n not in visited:
            _dfs(n)

    return cycles


def analyze_dependency_graph(
    project_root: Path,
    files: Sequence[FileRecord],
) -> DependencyGraph:
    """Build internal module dependency graph, detect cycles, and infer architectural layers."""
    py_files = [f for f in files if f.is_source and f.language == "Python"]
    js_files = [
        f for f in files if f.is_source and f.language in ("JavaScript", "TypeScript", "JSX", "TSX")
    ]
    go_files = [f for f in files if f.is_source and f.language == "Go"]
    rust_files = [f for f in files if f.is_source and f.language == "Rust"]

    modules: dict[str, ModuleNode] = {}
    # Map known Python dotted paths to canonical module name
    py_mod_lookup: dict[str, str] = {}
    for f in py_files:
        mod_name = _python_module_name(f.relative_path)
        layer = infer_module_layer(mod_name, f.relative_path)
        modules[mod_name] = ModuleNode(
            name=mod_name,
            file_path=f.relative_path,
            language="Python",
            layer=layer,
        )
        py_mod_lookup[mod_name] = mod_name

    js_mod_lookup: dict[str, str] = {}
    for f in js_files:
        mod_name = _js_module_name(f.relative_path)
        layer = infer_module_layer(mod_name, f.relative_path)
        modules[mod_name] = ModuleNode(
            name=mod_name,
            file_path=f.relative_path,
            language=f.language or "JavaScript",
            layer=layer,
        )
        js_mod_lookup[mod_name] = mod_name

    for f in go_files + rust_files:
        mod_name = f.relative_path.replace("\\", "/")
        layer = infer_module_layer(mod_name, f.relative_path)
        modules[mod_name] = ModuleNode(
            name=mod_name,
            file_path=f.relative_path,
            language=f.language or "Go",
            layer=layer,
        )

    adj: dict[str, set[str]] = {m: set() for m in modules}
    ext_packages: dict[str, set[str]] = {}

    # 1. Parse Python imports via AST
    for f in py_files:
        mod_name = _python_module_name(f.relative_path)
        node = modules[mod_name]
        is_init = f.relative_path.endswith("__init__.py")
        full_path = project_root / f.relative_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=f.relative_path)
        except Exception:
            continue

        for stmt in ast.walk(tree):
            raw_targets: list[str] = []
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    raw_targets.append(alias.name)
            elif isinstance(stmt, ast.ImportFrom):
                base_mod = stmt.module or ""
                if stmt.level and stmt.level > 0:
                    resolved_base = _resolve_relative_python_import(
                        mod_name, is_init, stmt.level, base_mod or None
                    )
                else:
                    resolved_base = base_mod
                if resolved_base:
                    raw_targets.append(resolved_base)
                    for alias in stmt.names:
                        if alias.name != "*":
                            raw_targets.append(f"{resolved_base}.{alias.name}")

            for target in raw_targets:
                # Check if target or a prefix matches an internal module
                matched_internal: str | None = None
                parts = target.split(".")
                for i in range(len(parts), 0, -1):
                    candidate = ".".join(parts[:i])
                    if candidate in py_mod_lookup:
                        matched_internal = py_mod_lookup[candidate]
                        break

                if matched_internal:
                    if matched_internal != mod_name:
                        adj[mod_name].add(matched_internal)
                else:
                    top_pkg = parts[0]
                    if top_pkg and top_pkg not in _PYTHON_STDLIB:
                        if top_pkg not in node.external_imports:
                            node.external_imports.append(top_pkg)
                        ext_packages.setdefault(top_pkg, set()).add(mod_name)

    # 2. Parse JS/TS imports
    for f in js_files:
        mod_name = _js_module_name(f.relative_path)
        node = modules[mod_name]
        full_path = project_root / f.relative_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        parent_dir = Path(f.relative_path).parent
        for m in _JS_IMPORT_RE.finditer(content):
            spec = m.group(1).strip()
            if spec.startswith("."):
                rel_target = (parent_dir / spec).as_posix()
                # Normalize .. and .
                norm_parts: list[str] = []
                for p in rel_target.split("/"):
                    if p in ("", "."):
                        continue
                    if p == "..":
                        if norm_parts:
                            norm_parts.pop()
                    else:
                        norm_parts.append(p)
                cand = "/".join(norm_parts)
                cand = _js_module_name(cand)
                if cand in js_mod_lookup and cand != mod_name:
                    adj[mod_name].add(cand)
            else:
                pkg = (
                    spec.split("/")[0]
                    if not spec.startswith("@")
                    else "/".join(spec.split("/")[:2])
                )
                if pkg not in node.external_imports:
                    node.external_imports.append(pkg)
                ext_packages.setdefault(pkg, set()).add(mod_name)

    # 3. Populate internal_imports, imported_by, fan_in, fan_out, edges
    edges: list[tuple[str, str]] = []
    for src, targets in sorted(adj.items()):
        src_node = modules[src]
        src_node.internal_imports = sorted(targets)
        src_node.fan_out = len(targets)
        for dst in sorted(targets):
            edges.append((src, dst))
            dst_node = modules[dst]
            if src not in dst_node.imported_by:
                dst_node.imported_by.append(src)

    for mod_node in modules.values():
        mod_node.imported_by.sort()
        mod_node.fan_in = len(mod_node.imported_by)
        mod_node.external_imports.sort()

    cycles = _find_cycles(adj)

    # Rankings & architectural insights
    all_nodes = list(modules.values())
    highly_coupled = [
        n.name
        for n in sorted(
            all_nodes,
            key=lambda x: (x.fan_in + x.fan_out, x.fan_in),
            reverse=True,
        )
        if (n.fan_in + n.fan_out) >= 3
    ][:10]

    central_hubs = [
        n.name
        for n in sorted(all_nodes, key=lambda x: (x.fan_in, x.fan_out), reverse=True)
        if n.fan_in >= 2
    ][:10]

    entry_points = [
        n.name
        for n in sorted(all_nodes, key=lambda x: x.name)
        if (n.fan_in == 0 and n.fan_out > 0 and n.layer != "tests")
        or any(
            n.name.endswith(suffix)
            for suffix in (".cli", ".main", ".__main__", "cli", "main", "index", "app")
        )
    ][:10]

    layers: dict[str, list[str]] = {}
    for n in sorted(all_nodes, key=lambda x: x.name):
        layers.setdefault(n.layer, []).append(n.name)

    unexpected_layer_deps: list[dict[str, str]] = []
    for src, dst in edges:
        src_layer = modules[src].layer
        dst_layer = modules[dst].layer
        src_rank = LAYER_RANK.get(src_layer, 30)
        dst_rank = LAYER_RANK.get(dst_layer, 30)
        if src_rank < dst_rank:
            unexpected_layer_deps.append(
                {
                    "from_module": src,
                    "from_layer": src_layer,
                    "to_module": dst,
                    "to_layer": dst_layer,
                    "reason": f"Lower-level layer '{src_layer}' depends on higher-level layer '{dst_layer}'",
                }
            )

    ext_pkg_dict = {
        pkg: sorted(users)
        for pkg, users in sorted(ext_packages.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    }

    return DependencyGraph(
        total_modules=len(modules),
        total_internal_edges=len(edges),
        total_external_packages=len(ext_pkg_dict),
        modules=sorted(all_nodes, key=lambda x: (-(x.fan_in + x.fan_out), x.name)),
        edges=edges,
        external_packages=ext_pkg_dict,
        cycles=cycles,
        highly_coupled_modules=highly_coupled,
        central_hub_modules=central_hubs,
        entry_points=entry_points,
        inferred_layers=layers,
        unexpected_layer_dependencies=unexpected_layer_deps,
    )

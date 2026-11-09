"""Technical debt collector and heuristic dead-code detector."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Sequence

from rpx.config import RPXConfig
from rpx.models import (
    ComplexityAnalysis,
    DeadCodeIndicator,
    DebtAnalysis,
    DebtItem,
    DependencyAnalysis,
    DependencyGraph,
    FileRecord,
)

_DEBT_COMMENT_RE = re.compile(
    r"(?:#|//|/\*+|\*|--)\s*\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s-]*(.*)",
    re.IGNORECASE,
)

_DEBUG_PATTERNS: list[tuple[str, re.Pattern[str], set[str] | None]] = [
    ("pdb.set_trace()", re.compile(r"\bpdb\.set_trace\s*\("), {"Python"}),
    ("breakpoint()", re.compile(r"\bbreakpoint\s*\("), {"Python"}),
    (
        "console.log()",
        re.compile(r"\bconsole\.(?:log|debug)\s*\("),
        {"JavaScript", "TypeScript", "JSX", "TSX"},
    ),
    (
        "debugger statement",
        re.compile(r"^\s*debugger\s*;?\s*$"),
        {"JavaScript", "TypeScript", "JSX", "TSX"},
    ),
    ("var_dump / dd()", re.compile(r"\b(?:var_dump|dd)\s*\("), {"PHP"}),
]

# Known runtime/plugin packages that may not be directly imported in code
_NON_IMPORTED_PACKAGES = {
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
    "black",
    "isort",
    "flake8",
    "tox",
    "nox",
    "pre-commit",
    "uvicorn",
    "gunicorn",
    "daphne",
    "hypercorn",
    "setuptools",
    "wheel",
    "build",
    "twine",
    "pip",
    "pipx",
    "typescript",
    "eslint",
    "prettier",
    "vite",
    "webpack",
    "jest",
    "vitest",
    "ts-node",
    "nodemon",
    "tailwindcss",
    "postcss",
    "autoprefixer",
}


def _find_unused_python_imports(rel_path: str, content: str) -> list[DeadCodeIndicator]:
    """Identify unused top-level imports in a Python file using AST."""
    if rel_path.endswith("__init__.py"):
        # __init__.py often re-exports symbols intentionally
        return []

    try:
        tree = ast.parse(content, filename=rel_path)
    except SyntaxError:
        return []

    imported_names: list[tuple[str, str, int]] = []  # (bound_name, full_import, lineno)
    used_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imported_names.append((bound, alias.name, getattr(node, "lineno", 1)))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                full = f"{node.module}.{alias.name}" if node.module else alias.name
                imported_names.append((bound, full, getattr(node, "lineno", 1)))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Also check root of attribute chains or type annotations in strings
            pass
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Support stringified type annotations (from __future__ import annotations)
            for token in re.findall(r"\b[A-Za-z_]\w*\b", node.value):
                used_names.add(token)

    indicators: list[DeadCodeIndicator] = []
    for bound, full_name, lineno in imported_names:
        if bound not in used_names and not bound.startswith("_"):
            indicators.append(
                DeadCodeIndicator(
                    kind="unused_import",
                    name=full_name,
                    file_path=rel_path,
                    line_number=lineno,
                    confidence="high",
                    reason=f"Imported symbol '{bound}' is not referenced in {rel_path}",
                )
            )
    return indicators


def analyze_technical_debt(
    project_root: Path,
    files: Sequence[FileRecord],
    complexity: ComplexityAnalysis | None,
    dep_graph: DependencyGraph | None,
    dep_analysis: DependencyAnalysis | None,
    config: RPXConfig,
) -> DebtAnalysis:
    """Perform repository-wide technical debt and heuristic dead-code analysis."""
    items: list[DebtItem] = []
    dead_code: list[DeadCodeIndicator] = []

    todo_count = 0
    fixme_count = 0
    hack_count = 0
    xxx_count = 0
    debug_count = 0

    all_identifier_tokens: dict[str, int] = {}
    defined_private_py_funcs: list[tuple[str, str, int]] = []

    # 1. Scan source files for comment markers, debug statements, and AST unused imports
    for f in files:
        if not f.is_source or f.is_binary:
            continue

        full_path = project_root / f.relative_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        is_test_file = "test" in f.relative_path.lower() or f.relative_path.startswith("tests/")

        lines = content.splitlines()
        for line_idx, line in enumerate(lines, start=1):
            # Check TODO/FIXME/HACK/XXX/BUG comments
            m = _DEBT_COMMENT_RE.search(line)
            if m:
                tag = m.group(1).upper()
                note = m.group(2).strip()
                snippet = line.strip()[:120]

                if tag == "TODO":
                    todo_count += 1
                    sev = "low"
                elif tag in ("FIXME", "BUG"):
                    fixme_count += 1
                    sev = "medium"
                elif tag == "HACK":
                    hack_count += 1
                    sev = "medium"
                else:
                    xxx_count += 1
                    sev = "low"

                items.append(
                    DebtItem(
                        category="comment_marker",
                        severity=sev,
                        confidence="high",
                        file_path=f.relative_path,
                        line_number=line_idx,
                        message=f"{tag}: {note}" if note else f"{tag} marker",
                        snippet=snippet,
                    )
                )

            # Check debug statements (skip test files)
            if not is_test_file:
                stripped = line.strip()
                if not stripped.startswith(("#", "//", "/*", "*")):
                    for label, pat, langs in _DEBUG_PATTERNS:
                        if langs is None or f.language in langs:
                            if pat.search(line):
                                debug_count += 1
                                items.append(
                                    DebtItem(
                                        category="debug_statement",
                                        severity="medium"
                                        if "pdb" in label
                                        or "breakpoint" in label
                                        or "debugger" in label
                                        else "low",
                                        confidence="high",
                                        file_path=f.relative_path,
                                        line_number=line_idx,
                                        message=f"Leftover debug statement ({label})",
                                        snippet=stripped[:120],
                                    )
                                )

        # Python-specific dead-code heuristics
        if f.language == "Python":
            unused_imps = _find_unused_python_imports(f.relative_path, content)
            dead_code.extend(unused_imps)

            # Track private functions and token occurrences across repo
            for tok in re.findall(r"\b[A-Za-z_]\w*\b", content):
                all_identifier_tokens[tok] = all_identifier_tokens.get(tok, 0) + 1

            if not is_test_file:
                try:
                    tree = ast.parse(content, filename=f.relative_path)
                    for stmt in tree.body:
                        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if stmt.name.startswith("_") and not stmt.name.startswith("__"):
                                defined_private_py_funcs.append(
                                    (stmt.name, f.relative_path, getattr(stmt, "lineno", 1))
                                )
                except SyntaxError:
                    pass

    # Check private helper functions referenced only once (their own def)
    for fn_name, rel_path, lineno in defined_private_py_funcs:
        if all_identifier_tokens.get(fn_name, 0) <= 1:
            dead_code.append(
                DeadCodeIndicator(
                    kind="unused_function",
                    name=fn_name,
                    file_path=rel_path,
                    line_number=lineno,
                    confidence="medium",
                    reason=f"Private function '{fn_name}' appears only at its definition site",
                )
            )

    # 2. Incorporate complexity & size debt items
    if complexity:
        for fn in complexity.high_complexity_functions:
            sev = "high" if fn.cyclomatic_complexity > config.complexity_high_max else "medium"
            items.append(
                DebtItem(
                    category="high_complexity",
                    severity=sev,
                    confidence="high",
                    file_path=fn.file_path,
                    line_number=fn.start_line,
                    message=(
                        f"Function '{fn.name}' has cyclomatic complexity {fn.cyclomatic_complexity} "
                        f"(threshold: {config.complexity_medium_max})"
                    ),
                )
            )

        for fn in complexity.large_functions:
            sev = "high" if fn.line_count > config.max_function_lines * 2 else "medium"
            items.append(
                DebtItem(
                    category="oversized_function",
                    severity=sev,
                    confidence="high",
                    file_path=fn.file_path,
                    line_number=fn.start_line,
                    message=(
                        f"Function '{fn.name}' is {fn.line_count} lines long "
                        f"(threshold: {config.max_function_lines})"
                    ),
                )
            )

        for fn in complexity.deep_nesting_functions:
            items.append(
                DebtItem(
                    category="deep_nesting",
                    severity="medium",
                    confidence="high",
                    file_path=fn.file_path,
                    line_number=fn.start_line,
                    message=(
                        f"Function '{fn.name}' has control-flow nesting depth {fn.max_nesting_depth} "
                        f"(threshold: {config.max_nesting_depth})"
                    ),
                )
            )

        for fc in complexity.long_files:
            sev = "high" if fc.line_count > config.max_file_lines * 2 else "medium"
            items.append(
                DebtItem(
                    category="oversized_file",
                    severity=sev,
                    confidence="high",
                    file_path=fc.path,
                    line_number=1,
                    message=(
                        f"File '{fc.path}' has {fc.line_count} lines "
                        f"(threshold: {config.max_file_lines})"
                    ),
                )
            )

    # 3. Incorporate dependency graph debt & dead-code heuristics
    if dep_graph:
        for cycle in dep_graph.cycles:
            cycle_str = " -> ".join(cycle)
            first_mod = next((m for m in dep_graph.modules if m.name == cycle[0]), None)
            items.append(
                DebtItem(
                    category="circular_dependency",
                    severity="high",
                    confidence="high",
                    file_path=first_mod.file_path if first_mod else cycle[0],
                    line_number=1,
                    message=f"Circular module dependency detected: {cycle_str}",
                )
            )

        for viol in dep_graph.unexpected_layer_dependencies:
            src_mod = next((m for m in dep_graph.modules if m.name == viol["from_module"]), None)
            items.append(
                DebtItem(
                    category="architecture_violation",
                    severity="medium",
                    confidence="medium",
                    file_path=src_mod.file_path if src_mod else viol["from_module"],
                    line_number=1,
                    message=f"{viol['from_module']} ({viol['from_layer']}) imports {viol['to_module']} ({viol['to_layer']})",
                )
            )

        # Heuristic: unreferenced internal modules
        entry_set = set(dep_graph.entry_points)
        for mod in dep_graph.modules:
            if (
                mod.fan_in == 0
                and mod.name not in entry_set
                and mod.layer != "tests"
                and not mod.file_path.endswith("__init__.py")
                and len(dep_graph.modules) > 3
            ):
                dead_code.append(
                    DeadCodeIndicator(
                        kind="unreferenced_module",
                        name=mod.name,
                        file_path=mod.file_path,
                        line_number=1,
                        confidence="low",
                        reason=f"Module '{mod.name}' has 0 internal importers and is not detected as an entry point",
                    )
                )

    # 4. Heuristic: declared dependencies not seen in imports
    if dep_analysis and dep_graph and dep_graph.external_packages:
        imported_Normalized = {
            pkg.lower().replace("-", "_"): pkg for pkg in dep_graph.external_packages
        }
        for dep in dep_analysis.dependencies:
            if dep.category != "production":
                continue
            norm_dep = dep.name.lower().replace("-", "_")
            if (
                norm_dep not in imported_Normalized
                and dep.name.lower() not in _NON_IMPORTED_PACKAGES
                and dep.ecosystem == "Python"
            ):
                dead_code.append(
                    DeadCodeIndicator(
                        kind="unused_dependency",
                        name=dep.name,
                        file_path=dep.source_file,
                        line_number=None,
                        confidence="low",
                        reason=f"Declared dependency '{dep.name}' was not matched to any direct Python import (heuristic)",
                    )
                )

    # Sort items by severity (high -> medium -> low) then file_path
    sev_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(
        key=lambda d: (
            sev_order.get(d.severity, 3),
            d.file_path,
            d.line_number or 0,
        )
    )

    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    by_category: dict[str, int] = {}
    file_counts: dict[str, int] = {}

    for item in items:
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
        by_category[item.category] = by_category.get(item.category, 0) + 1
        file_counts[item.file_path] = file_counts.get(item.file_path, 0) + 1

    hotspot_files = sorted(
        [{"file_path": k, "debt_count": v} for k, v in file_counts.items()],
        key=lambda x: int(x["debt_count"]),
        reverse=True,
    )[: config.ranking_limit]

    return DebtAnalysis(
        total_items=len(items),
        by_severity=by_severity,
        by_category=by_category,
        todo_count=todo_count,
        fixme_count=fixme_count,
        hack_count=hack_count,
        xxx_count=xxx_count,
        debug_statement_count=debug_count,
        items=items,
        dead_code_indicators=dead_code,
        hotspot_files=hotspot_files,
    )

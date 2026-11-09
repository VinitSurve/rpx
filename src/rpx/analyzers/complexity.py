"""Language-aware code complexity analyzer (AST for Python, block/branch analysis for other languages)."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Sequence

from rpx.config import RPXConfig
from rpx.models import (
    ClassComplexity,
    ComplexityAnalysis,
    FileComplexity,
    FileRecord,
    FunctionComplexity,
)

# Regex patterns for function definitions in non-Python languages
_JS_TS_FUNC_RE = re.compile(
    r"^(?:\s*)(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)|"
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>|"
    r"(?:public|private|protected|static|async|\s)*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*(?::\s*[^{]+)?\{)"
)
_GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]+\)\s+)?([A-Za-z_]\w*)\s*\(([^)]*)\)")
_RUST_FUNC_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z_]\w*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
)
_C_JAVA_FUNC_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|final|virtual|override|inline|async|synchronized)\s+)*"
    r"[\w<>\[\],\s\*&]+\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(?:const\s*)?(?:throws\s+[\w,\s]+)?\{"
)
_CLASS_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+|final\s+|public\s+|private\s+)*"
    r"(?:class|struct|interface)\s+([A-Za-z_]\w*)"
)
_BRANCH_TOKEN_RE = re.compile(
    r"\b(?:if|else\s+if|elif|for|foreach|while|case|catch|except)\b|&&|\|\||\?(?!\.|:)"
)
_CONTROL_START_RE = re.compile(r"^\s*(?:if|else\s+if|elif|for|foreach|while|switch|try|match)\b")

_CONTROL_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "sizeof",
    "typeof",
}

BRACE_LANGUAGES = {
    "JavaScript",
    "TypeScript",
    "JSX",
    "TSX",
    "Go",
    "Rust",
    "Java",
    "Kotlin",
    "C",
    "C++",
    "C/C++ Header",
    "C++ Header",
    "C#",
    "Swift",
    "Dart",
    "PHP",
    "Scala",
}


def classify_complexity(cc: int, config: RPXConfig) -> str:
    """Classify cyclomatic complexity into low, medium, high, or critical."""
    if cc <= config.complexity_low_max:
        return "low"
    if cc <= config.complexity_medium_max:
        return "medium"
    if cc <= config.complexity_high_max:
        return "high"
    return "critical"


def _compute_ast_cyclomatic_and_depth(node: ast.AST) -> tuple[int, int]:
    """Compute cyclomatic complexity and max control-flow nesting depth for a Python AST node."""
    complexity = 1
    max_depth = 0

    def _walk(curr: ast.AST, depth: int) -> None:
        nonlocal complexity, max_depth
        if depth > max_depth:
            max_depth = depth

        for child in ast.iter_child_nodes(curr):
            # Do not descend into nested function or class definitions
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            next_depth = depth
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                ),
            ):
                complexity += 1
                next_depth = depth + 1
            elif isinstance(child, (ast.Assert, ast.IfExp)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += max(1, len(child.values) - 1)
            elif isinstance(child, ast.comprehension):
                complexity += 1 + len(child.ifs)
            elif isinstance(child, ast.Match):
                complexity += max(0, len(child.cases) - 1)
                next_depth = depth + 1

            _walk(child, next_depth)

    _walk(node, 0)
    return complexity, max_depth


def analyze_python_file_complexity(
    rel_path: str,
    content: str,
    line_count: int,
    config: RPXConfig,
) -> tuple[FileComplexity, bool]:
    """Analyze a Python file using the standard library `ast` module.

    Returns (FileComplexity, parse_succeeded).
    """
    try:
        tree = ast.parse(content, filename=rel_path)
    except SyntaxError:
        return (
            FileComplexity(
                path=rel_path,
                language="Python",
                line_count=line_count,
                is_long_file=line_count > config.max_file_lines,
            ),
            False,
        )

    functions: list[FunctionComplexity] = []
    classes: list[ClassComplexity] = []

    def _visit_scope(body: Sequence[ast.stmt], class_prefix: str = "") -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = f"{class_prefix}.{stmt.name}" if class_prefix else stmt.name
                start_line = getattr(stmt, "lineno", 1)
                end_line = getattr(stmt, "end_lineno", start_line) or start_line
                length = max(1, end_line - start_line + 1)

                # Count parameters excluding self/cls on methods
                all_args = (
                    list(stmt.args.posonlyargs) + list(stmt.args.args) + list(stmt.args.kwonlyargs)
                )
                param_names = [a.arg for a in all_args]
                if class_prefix and param_names and param_names[0] in ("self", "cls"):
                    param_count = len(param_names) - 1
                else:
                    param_count = len(param_names)
                if stmt.args.vararg:
                    param_count += 1
                if stmt.args.kwarg:
                    param_count += 1

                cc, nesting = _compute_ast_cyclomatic_and_depth(stmt)
                sev = classify_complexity(cc, config)

                functions.append(
                    FunctionComplexity(
                        name=fn_name,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line,
                        line_count=length,
                        cyclomatic_complexity=cc,
                        parameter_count=param_count,
                        max_nesting_depth=nesting,
                        is_method=bool(class_prefix),
                        severity=sev,
                    )
                )
                # Also inspect nested functions/classes
                _visit_scope(stmt.body, class_prefix=fn_name)

            elif isinstance(stmt, ast.ClassDef):
                cls_name = f"{class_prefix}.{stmt.name}" if class_prefix else stmt.name
                start_line = getattr(stmt, "lineno", 1)
                end_line = getattr(stmt, "end_lineno", start_line) or start_line
                length = max(1, end_line - start_line + 1)
                method_count = sum(
                    1
                    for item in stmt.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                classes.append(
                    ClassComplexity(
                        name=cls_name,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line,
                        line_count=length,
                        method_count=method_count,
                    )
                )
                _visit_scope(stmt.body, class_prefix=cls_name)

    _visit_scope(tree.body)

    if functions:
        avg_cc = round(sum(f.cyclomatic_complexity for f in functions) / len(functions), 2)
        max_cc = max(f.cyclomatic_complexity for f in functions)
        max_depth = max(f.max_nesting_depth for f in functions)
    else:
        # Compute module-level complexity if no functions exist
        mod_cc, mod_depth = _compute_ast_cyclomatic_and_depth(tree)
        avg_cc = float(mod_cc)
        max_cc = mod_cc
        max_depth = mod_depth

    return (
        FileComplexity(
            path=rel_path,
            language="Python",
            line_count=line_count,
            function_count=len(functions),
            class_count=len(classes),
            avg_complexity=avg_cc,
            max_complexity=max_cc,
            max_nesting_depth=max_depth,
            functions=functions,
            classes=classes,
            is_long_file=line_count > config.max_file_lines,
        ),
        True,
    )


def _count_params(param_str: str) -> int:
    cleaned = param_str.strip()
    if not cleaned:
        return 0
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if parts and parts[0] in ("self", "&self", "&mut self", "this"):
        return max(0, len(parts) - 1)
    return len(parts)


def analyze_brace_file_complexity(
    rel_path: str,
    language: str,
    content: str,
    line_count: int,
    config: RPXConfig,
) -> FileComplexity:
    """Analyze complexity of a brace-delimited source file (JS/TS, Go, Rust, Java, C/C++, etc.)."""
    lines = content.splitlines()
    functions: list[FunctionComplexity] = []
    classes: list[ClassComplexity] = []

    idx = 0
    total_lines = len(lines)

    while idx < total_lines:
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "#")):
            idx += 1
            continue

        # Check class declaration
        cls_match = _CLASS_RE.match(line)
        if cls_match and "{" in line:
            cls_name = cls_match.group(1)
            start_line = idx + 1
            brace_balance = line.count("{") - line.count("}")
            end_idx = idx
            while brace_balance > 0 and end_idx + 1 < total_lines:
                end_idx += 1
                brace_balance += lines[end_idx].count("{") - lines[end_idx].count("}")
            end_line = end_idx + 1
            classes.append(
                ClassComplexity(
                    name=cls_name,
                    file_path=rel_path,
                    start_line=start_line,
                    end_line=end_line,
                    line_count=max(1, end_line - start_line + 1),
                    method_count=0,
                )
            )

        # Match function declaration depending on language
        fn_name: str | None = None
        param_str = ""
        if language == "Go":
            m = _GO_FUNC_RE.match(line)
            if m:
                fn_name, param_str = m.group(1), m.group(2)
        elif language == "Rust":
            m = _RUST_FUNC_RE.match(line)
            if m:
                fn_name, param_str = m.group(1), m.group(2)
        elif language in ("JavaScript", "TypeScript", "JSX", "TSX"):
            m = _JS_TS_FUNC_RE.match(line)
            if m:
                fn_name = m.group(1) or m.group(3) or m.group(5)
                param_str = m.group(2) or m.group(4) or m.group(6) or ""
        else:
            m = _C_JAVA_FUNC_RE.match(line)
            if m:
                fn_name, param_str = m.group(1), m.group(2)

        if fn_name and fn_name not in _CONTROL_KEYWORDS and "{" in line:
            start_line = idx + 1
            brace_balance = line.count("{") - line.count("}")
            end_idx = idx
            cc = 1
            max_nesting = 0
            base_depth = max(1, brace_balance)

            # Check branch tokens on first line
            cc += len(_BRANCH_TOKEN_RE.findall(line))

            while brace_balance > 0 and end_idx + 1 < total_lines:
                end_idx += 1
                body_line = lines[end_idx]
                body_stripped = body_line.strip()
                if not body_stripped.startswith(("//", "/*", "*")):
                    cc += len(_BRANCH_TOKEN_RE.findall(body_line))
                    if _CONTROL_START_RE.match(body_line):
                        rel_depth = max(1, brace_balance - base_depth + 1)
                        if rel_depth > max_nesting:
                            max_nesting = rel_depth
                brace_balance += body_line.count("{") - body_line.count("}")

            end_line = end_idx + 1
            fn_len = max(1, end_line - start_line + 1)
            sev = classify_complexity(cc, config)
            functions.append(
                FunctionComplexity(
                    name=fn_name,
                    file_path=rel_path,
                    start_line=start_line,
                    end_line=end_line,
                    line_count=fn_len,
                    cyclomatic_complexity=cc,
                    parameter_count=_count_params(param_str),
                    max_nesting_depth=max_nesting,
                    is_method=False,
                    severity=sev,
                )
            )
            idx = end_idx + 1
            continue

        idx += 1

    if functions:
        avg_cc = round(sum(f.cyclomatic_complexity for f in functions) / len(functions), 2)
        max_cc = max(f.cyclomatic_complexity for f in functions)
        max_depth = max(f.max_nesting_depth for f in functions)
    else:
        total_branches = sum(
            len(_BRANCH_TOKEN_RE.findall(ln))
            for ln in lines
            if not ln.strip().startswith(("//", "/*", "*"))
        )
        avg_cc = float(1 + total_branches) if lines else 1.0
        max_cc = int(avg_cc)
        max_depth = 0

    return FileComplexity(
        path=rel_path,
        language=language,
        line_count=line_count,
        function_count=len(functions),
        class_count=len(classes),
        avg_complexity=avg_cc,
        max_complexity=max_cc,
        max_nesting_depth=max_depth,
        functions=functions,
        classes=classes,
        is_long_file=line_count > config.max_file_lines,
    )


def analyze_single_file_complexity(
    project_root: Path,
    file_rec: FileRecord,
    config: RPXConfig,
) -> tuple[FileComplexity | None, bool]:
    """Analyze a single FileRecord for code complexity.

    Returns (FileComplexity | None, parse_succeeded).
    """
    if not file_rec.is_source or not file_rec.language:
        return None, True

    full_path = project_root / file_rec.relative_path
    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, False

    line_count = file_rec.total_lines or len(content.splitlines())

    if file_rec.language == "Python":
        return analyze_python_file_complexity(file_rec.relative_path, content, line_count, config)
    if file_rec.language in BRACE_LANGUAGES:
        return (
            analyze_brace_file_complexity(
                file_rec.relative_path, file_rec.language, content, line_count, config
            ),
            True,
        )

    # Generic source fallback (tracks file length)
    return (
        FileComplexity(
            path=file_rec.relative_path,
            language=file_rec.language,
            line_count=line_count,
            avg_complexity=1.0,
            max_complexity=1,
            is_long_file=line_count > config.max_file_lines,
        ),
        True,
    )


def aggregate_complexity(
    file_complexities: Sequence[FileComplexity],
    config: RPXConfig,
) -> ComplexityAnalysis:
    """Aggregate individual FileComplexity records into a repository-wide ComplexityAnalysis."""
    all_functions: list[FunctionComplexity] = []
    all_classes: list[ClassComplexity] = []
    dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}

    for fc in file_complexities:
        all_functions.extend(fc.functions)
        all_classes.extend(fc.classes)
        for fn in fc.functions:
            dist[fn.severity] = dist.get(fn.severity, 0) + 1

    total_funcs = len(all_functions)
    total_classes = len(all_classes)

    if total_funcs > 0:
        avg_cc = round(sum(f.cyclomatic_complexity for f in all_functions) / total_funcs, 2)
        max_cc = max(f.cyclomatic_complexity for f in all_functions)
        avg_len = round(sum(f.line_count for f in all_functions) / total_funcs, 2)
    else:
        avg_cc = 0.0
        max_cc = 0
        avg_len = 0.0

    max_depth = (
        max((fc.max_nesting_depth for fc in file_complexities), default=0)
        if file_complexities
        else 0
    )

    high_funcs = sorted(
        [f for f in all_functions if f.cyclomatic_complexity > config.complexity_medium_max],
        key=lambda x: (x.cyclomatic_complexity, x.line_count),
        reverse=True,
    )
    large_funcs = sorted(
        [f for f in all_functions if f.line_count > config.max_function_lines],
        key=lambda x: x.line_count,
        reverse=True,
    )
    deep_funcs = sorted(
        [f for f in all_functions if f.max_nesting_depth > config.max_nesting_depth],
        key=lambda x: (x.max_nesting_depth, x.cyclomatic_complexity),
        reverse=True,
    )
    many_param_funcs = sorted(
        [f for f in all_functions if f.parameter_count > config.max_parameters],
        key=lambda x: x.parameter_count,
        reverse=True,
    )
    long_files = sorted(
        [fc for fc in file_complexities if fc.is_long_file],
        key=lambda x: x.line_count,
        reverse=True,
    )
    sorted_files = sorted(
        file_complexities,
        key=lambda x: (x.max_complexity, x.function_count, x.line_count),
        reverse=True,
    )

    return ComplexityAnalysis(
        files_analyzed=len(file_complexities),
        total_functions=total_funcs,
        total_classes=total_classes,
        avg_function_complexity=avg_cc,
        max_function_complexity=max_cc,
        avg_function_length=avg_len,
        max_nesting_depth=max_depth,
        distribution=dist,
        high_complexity_functions=high_funcs[: config.ranking_limit * 2],
        large_functions=large_funcs[: config.ranking_limit * 2],
        deep_nesting_functions=deep_funcs[: config.ranking_limit * 2],
        many_param_functions=many_param_funcs[: config.ranking_limit * 2],
        long_files=long_files[: config.ranking_limit * 2],
        files=sorted_files,
    )

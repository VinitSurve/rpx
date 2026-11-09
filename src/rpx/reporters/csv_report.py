"""CSV export system for file, language, dependency, complexity, debt, security, and comparison statistics."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from rpx.exceptions import ExportError
from rpx.models import ComparisonDiff, ScanResult


def export_files_csv(result: ScanResult) -> str:
    """Generate CSV string of all analyzed source files with LOC breakdown."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "File",
            "Language",
            "Total Physical Lines",
            "Code Lines",
            "Comment Lines",
            "Blank Lines",
            "Inline Comments",
        ]
    )

    for floc in result.loc.per_file_loc:
        writer.writerow(
            [
                floc.path,
                floc.language,
                floc.total_physical,
                floc.code,
                floc.comments,
                floc.blank,
                floc.inline_comments,
            ]
        )

    return output.getvalue()


def export_languages_csv(result: ScanResult) -> str:
    """Generate CSV string of language distribution."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Language", "Files", "Code Lines", "Comment Lines", "Blank Lines", "Percentage"]
    )

    for lang in result.languages.languages.values():
        writer.writerow(
            [
                lang.name,
                lang.files,
                lang.code_lines,
                lang.comment_lines,
                lang.blank_lines,
                f"{lang.percentage}%",
            ]
        )

    return output.getvalue()


def export_dependencies_csv(result: ScanResult) -> str:
    """Generate CSV string of declared and locked dependencies."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Package Name", "Constraint", "Resolved Version", "Dependency Type", "Ecosystem"]
    )

    for dep in result.dependencies.declared_dependencies:
        writer.writerow(
            [
                dep.name,
                dep.constraint,
                dep.resolved_version or "",
                dep.dep_type,
                dep.ecosystem,
            ]
        )

    for dep in result.dependencies.locked_dependencies:
        writer.writerow(
            [
                dep.name,
                dep.constraint,
                dep.resolved_version or "",
                "locked",
                dep.ecosystem,
            ]
        )

    return output.getvalue()


def export_complexity_csv(result: ScanResult) -> str:
    """Generate CSV string of function-level complexity metrics."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Function",
            "File",
            "Start Line",
            "End Line",
            "Line Count",
            "Cyclomatic Complexity",
            "Parameters",
            "Max Nesting Depth",
            "Severity",
        ]
    )
    for fc in result.complexity.files:
        for fn in fc.functions:
            writer.writerow(
                [
                    fn.name,
                    fn.file_path,
                    fn.start_line,
                    fn.end_line,
                    fn.line_count,
                    fn.cyclomatic_complexity,
                    fn.parameter_count,
                    fn.max_nesting_depth,
                    fn.severity,
                ]
            )
    return output.getvalue()


def export_debt_csv(result: ScanResult) -> str:
    """Generate CSV string of technical debt findings."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Severity", "Confidence", "Category", "File", "Line", "Message"])
    for item in result.debt.items:
        writer.writerow(
            [
                item.severity,
                item.confidence,
                item.category,
                item.file_path,
                item.line_number or "",
                item.message,
            ]
        )
    return output.getvalue()


def export_security_csv(result: ScanResult) -> str:
    """Generate CSV string of local security findings (redacted)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Rule ID", "Severity", "Category", "File", "Line", "Message", "Redacted Snippet"]
    )
    for sf in result.security.findings:
        writer.writerow(
            [
                sf.rule_id,
                sf.severity,
                sf.category,
                sf.file_path,
                sf.line_number or "",
                sf.message,
                sf.redacted_snippet,
            ]
        )
    return output.getvalue()


def export_comparison_csv(diff: ComparisonDiff) -> str:
    """Generate CSV string of snapshot/project comparison metrics."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", diff.label_a, diff.label_b, "Delta"])
    for k, vals in diff.metrics.items():
        writer.writerow([k, vals.get("before", 0), vals.get("after", 0), vals.get("delta", 0)])
    return output.getvalue()


def save_csv_report(
    result: ScanResult, destination_path: Path, table_type: str = "files", force: bool = False
) -> None:
    """Save selected table (files, languages, deps, complexity, debt, security) as CSV."""
    dest = destination_path.resolve()
    if dest.exists() and not force:
        raise ExportError(f"Destination file already exists: {dest}. Use --force to overwrite.")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if table_type == "languages":
        csv_content = export_languages_csv(result)
    elif table_type == "deps":
        csv_content = export_dependencies_csv(result)
    elif table_type == "complexity":
        csv_content = export_complexity_csv(result)
    elif table_type == "debt":
        csv_content = export_debt_csv(result)
    elif table_type == "security":
        csv_content = export_security_csv(result)
    else:
        csv_content = export_files_csv(result)

    try:
        with open(dest, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)
    except OSError as e:
        raise ExportError(f"Failed to write CSV report to {dest}: {e}") from e

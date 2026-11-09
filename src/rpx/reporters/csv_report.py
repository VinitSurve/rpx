"""CSV export system for file, language, and dependency statistics."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from rpx.exceptions import ExportError
from rpx.models import ScanResult


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


def save_csv_report(
    result: ScanResult, destination_path: Path, table_type: str = "files", force: bool = False
) -> None:
    """Save selected table (files, languages, or deps) as CSV to destination_path."""
    dest = destination_path.resolve()
    if dest.exists() and not force:
        raise ExportError(f"Destination file already exists: {dest}. Use --force to overwrite.")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if table_type == "languages":
        csv_content = export_languages_csv(result)
    elif table_type == "deps":
        csv_content = export_dependencies_csv(result)
    else:
        csv_content = export_files_csv(result)

    try:
        with open(dest, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)
    except OSError as e:
        raise ExportError(f"Failed to write CSV report to {dest}: {e}") from e

"""AI-ready repository context generator (Markdown and JSON) with secret redaction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rpx.analyzers.security import redact_all_secrets_in_text
from rpx.exceptions import ExportError
from rpx.models import ScanResult


def build_context_dict(result: ScanResult) -> dict[str, Any]:
    """Construct a structured, deterministic, secret-free dictionary for coding agents."""
    fp = result.fingerprint
    graph = result.graph
    comp = result.complexity
    debt = result.debt
    health = result.health
    git = result.git

    return {
        "project": {
            "name": result.metadata.name,
            "project_types": result.metadata.project_types,
            "total_files": result.files.total_files,
            "source_files": result.files.source_files,
            "test_files": result.files.test_files,
            "code_lines": result.loc.total_code,
            "health_score": health.score,
        },
        "fingerprint": {
            "languages": fp.primary_languages,
            "frameworks": fp.frameworks,
            "package_managers": fp.package_managers,
            "build_tools": fp.build_tools,
            "test_frameworks": fp.test_frameworks,
            "linters": fp.linters,
            "formatters": fp.formatters,
            "type_checkers": fp.type_checkers,
            "ci_cd": fp.ci_cd_systems,
            "conventions": fp.conventions,
        },
        "architecture": {
            "entry_points": graph.entry_points[:10],
            "central_hub_modules": graph.central_hub_modules[:10],
            "highly_coupled_modules": graph.highly_coupled_modules[:10],
            "inferred_layers": {k: v[:20] for k, v in sorted(graph.inferred_layers.items())},
            "circular_dependencies": graph.cycles[:10],
            "layer_violations": graph.unexpected_layer_dependencies[:10],
        },
        "dependencies": [
            {
                "name": d.name,
                "constraint": d.constraint,
                "type": d.dep_type,
                "ecosystem": d.ecosystem,
            }
            for d in result.dependencies.declared_dependencies[:40]
        ],
        "complexity_hotspots": [
            {
                "function": fn.name,
                "file": fn.file_path,
                "line": fn.start_line,
                "cyclomatic_complexity": fn.cyclomatic_complexity,
                "lines": fn.line_count,
            }
            for fn in comp.high_complexity_functions[:12]
        ],
        "git_hotspots": [
            {
                "file": hs.path,
                "commits": hs.commits,
                "churn_lines": hs.churn_lines,
                "risk_score": hs.risk_score,
            }
            for hs in git.hotspots[:10]
        ],
        "technical_debt_summary": {
            "total_items": debt.total_items,
            "by_severity": debt.by_severity,
            "by_category": debt.by_category,
            "top_items": [
                {
                    "severity": item.severity,
                    "category": item.category,
                    "file": item.file_path,
                    "line": item.line_number,
                    "message": redact_all_secrets_in_text(item.message),
                }
                for item in debt.items[:15]
            ],
        },
        "recommended_investigation_areas": health.recommendations[:10],
    }


def generate_context_json(result: ScanResult) -> str:
    """Return a deterministic, secret-free JSON context string."""
    ctx = build_context_dict(result)
    raw = json.dumps(ctx, indent=2, sort_keys=False)
    return redact_all_secrets_in_text(raw)


def generate_context_markdown(result: ScanResult, max_chars: int = 32000) -> str:
    """Return a concise, high-signal Markdown repository brief for coding agents."""
    ctx = build_context_dict(result)
    proj = ctx["project"]
    fp = ctx["fingerprint"]
    arch = ctx["architecture"]

    lines = [
        f"# Repository Context: {proj['name']}",
        "",
        "## 1. Executive Summary",
        f"- **Project Types**: {', '.join(proj['project_types']) or 'General'}",
        f"- **Files**: {proj['total_files']} total ({proj['source_files']} source, {proj['test_files']} tests)",
        f"- **Lines of Code**: {proj['code_lines']:,}",
        f"- **Health Score**: {proj['health_score']}/100",
        "",
        "## 2. Technology Stack & Tooling",
        f"- **Languages**: {', '.join(fp['languages']) or 'None'}",
        f"- **Frameworks**: {', '.join(fp['frameworks']) or 'None detected'}",
        f"- **Package Managers**: {', '.join(fp['package_managers']) or 'None detected'}",
        f"- **Build Tools**: {', '.join(fp['build_tools']) or 'Standard'}",
        f"- **Test Frameworks**: {', '.join(fp['test_frameworks']) or 'None detected'}",
        f"- **Linters / Formatters**: {', '.join(fp['linters'] + fp['formatters']) or 'None detected'}",
        f"- **Conventions**: {', '.join(fp['conventions']) or 'Standard'}",
        "",
        "## 3. Architecture & Module Structure",
        f"- **Entry Points**: {', '.join(f'`{e}`' for e in arch['entry_points']) or 'None identified'}",
        f"- **Central Hub Modules**: {', '.join(f'`{m}`' for m in arch['central_hub_modules']) or 'None'}",
        f"- **Highly Coupled Modules**: {', '.join(f'`{m}`' for m in arch['highly_coupled_modules']) or 'None'}",
        "",
        "### Architectural Layers",
    ]

    for layer, mods in arch["inferred_layers"].items():
        mod_list = ", ".join(f"`{m}`" for m in mods[:12])
        lines.append(f"- **{layer}**: {mod_list}")

    if arch["circular_dependencies"]:
        lines.append("")
        lines.append("### Circular Dependencies")
        for cyc in arch["circular_dependencies"]:
            lines.append(f"- `{' -> '.join(cyc)}`")

    lines.append("")
    lines.append("## 4. Key Dependencies")
    if ctx["dependencies"]:
        for d in ctx["dependencies"][:25]:
            lines.append(
                f"- `{d['name']}` ({d['constraint'] or '*'}) [{d['type']} / {d['ecosystem']}]"
            )
    else:
        lines.append("- No declared dependencies.")

    lines.append("")
    lines.append("## 5. Complexity & Git Hotspots")
    if ctx["complexity_hotspots"]:
        for fn in ctx["complexity_hotspots"]:
            lines.append(
                f"- `{fn['function']}` in `{fn['file']}:{fn['line']}` "
                f"(CC={fn['cyclomatic_complexity']}, {fn['lines']} lines)"
            )
    else:
        lines.append("- No high-complexity functions above threshold.")

    if ctx["git_hotspots"]:
        lines.append("")
        lines.append("### High-Churn Files")
        for hs in ctx["git_hotspots"][:8]:
            lines.append(
                f"- `{hs['file']}` ({hs['commits']} commits, {hs['churn_lines']} churn lines, risk={hs['risk_score']})"
            )

    lines.append("")
    lines.append("## 6. Technical Debt & Recommended Next Steps")
    td = ctx["technical_debt_summary"]
    lines.append(
        f"- **Total Debt Items**: {td['total_items']} "
        f"(High: {td['by_severity'].get('high', 0)}, "
        f"Medium: {td['by_severity'].get('medium', 0)}, "
        f"Low: {td['by_severity'].get('low', 0)})"
    )
    for item in td["top_items"][:10]:
        loc = f"{item['file']}:{item['line']}" if item["line"] else item["file"]
        lines.append(f"  - [{item['severity'].upper()}] `{loc}`: {item['message']}")

    if ctx["recommended_investigation_areas"]:
        lines.append("")
        lines.append("### Recommended Actions")
        for rec in ctx["recommended_investigation_areas"]:
            lines.append(f"- {rec}")

    full_text = redact_all_secrets_in_text("\n".join(lines) + "\n")
    if len(full_text) > max_chars:
        return full_text[: max_chars - 60] + "\n\n... [Truncated to fit size bound]\n"
    return full_text


def export_context_report(
    result: ScanResult,
    output_path: Path,
    fmt: str = "markdown",
    max_chars: int = 32000,
) -> Path:
    """Write AI context report to disk."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if fmt.lower() == "json":
            content = generate_context_json(result)
        else:
            content = generate_context_markdown(result, max_chars=max_chars)
        output_path.write_text(content, encoding="utf-8")
        return output_path.resolve()
    except OSError as e:
        raise ExportError(f"Failed to export context report to {output_path}: {e}") from e

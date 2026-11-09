"""Self-contained, offline-capable HTML report generator for RPX."""

from __future__ import annotations

import html
from pathlib import Path

from rpx import __version__
from rpx.exceptions import ExportError
from rpx.models import ScanResult
from rpx.utils.formatting import (
    format_bytes,
    format_duration,
    format_number,
    format_percentage,
)


def _esc(val: object) -> str:
    return html.escape(str(val) if val is not None else "")


def generate_html_string(result: ScanResult) -> str:
    """Generate a complete self-contained HTML dashboard string from ScanResult."""
    meta = result.metadata
    fs = result.files
    loc = result.loc
    health = result.health
    comp = result.complexity
    debt = result.debt
    sec = result.security
    git = result.git
    cov = result.coverage
    fp = result.fingerprint

    score_color = (
        "#22c55e" if health.score >= 80 else ("#f59e0b" if health.score >= 55 else "#ef4444")
    )

    # Language rows
    lang_rows = []
    for lg in result.languages.languages.values():
        pct = min(100.0, max(0.0, lg.percentage))
        lang_rows.append(
            f"<tr>"
            f"<td><strong>{_esc(lg.name)}</strong></td>"
            f"<td class='num'>{format_number(lg.files)}</td>"
            f"<td class='num'>{format_number(lg.code_lines)}</td>"
            f"<td class='num'>{format_number(lg.comment_lines)}</td>"
            f"<td class='num'>{format_percentage(lg.percentage)}</td>"
            f"<td><div class='bar-bg'><div class='bar-fill' style='width:{pct:.1f}%'></div></div></td>"
            f"</tr>"
        )
    lang_html = (
        "\n".join(lang_rows) or "<tr><td colspan='6'>No source languages detected.</td></tr>"
    )

    # Health category rows
    health_rows = []
    for cat, val in health.score_breakdown.items():
        max_v = health.category_max_scores.get(cat, 15)
        pct = min(100.0, (val / max(1, max_v)) * 100.0)
        health_rows.append(
            f"<tr>"
            f"<td>{_esc(cat)}</td>"
            f"<td class='num'><strong>{val}</strong> / {max_v}</td>"
            f"<td><div class='bar-bg'><div class='bar-fill health-bar' style='width:{pct:.1f}%'></div></div></td>"
            f"</tr>"
        )
    health_cat_html = "\n".join(health_rows)

    # Deductions & Recommendations
    ded_rows = []
    for d in health.deductions:
        kind = "Missing Evidence" if d.is_missing_evidence else "Defect"
        ded_rows.append(
            f"<tr>"
            f"<td>{_esc(d.category)}</td>"
            f"<td class='num text-danger'>-{d.points_deducted}</td>"
            f"<td><span class='badge'>{_esc(kind)}</span></td>"
            f"<td>{_esc(d.reason)}</td>"
            f"<td>{_esc(d.recommendation)}</td>"
            f"</tr>"
        )
    ded_html = "\n".join(ded_rows) or "<tr><td colspan='5'>No health score deductions!</td></tr>"

    # Complexity hotspots
    comp_rows = []
    for fn in comp.high_complexity_functions[:15]:
        comp_rows.append(
            f"<tr>"
            f"<td><code>{_esc(fn.name)}</code></td>"
            f"<td><code>{_esc(fn.file_path)}:{fn.start_line}</code></td>"
            f"<td class='num'><strong>{fn.cyclomatic_complexity}</strong></td>"
            f"<td class='num'>{fn.line_count}</td>"
            f"<td class='num'>{fn.max_nesting_depth}</td>"
            f"<td><span class='badge sev-{_esc(fn.severity)}'>{_esc(fn.severity.upper())}</span></td>"
            f"</tr>"
        )
    comp_html = (
        "\n".join(comp_rows)
        or "<tr><td colspan='6'>No high-complexity functions detected.</td></tr>"
    )

    # Technical debt items
    debt_rows = []
    for item in debt.items[:25]:
        loc_str = f"{item.file_path}:{item.line_number}" if item.line_number else item.file_path
        debt_rows.append(
            f"<tr>"
            f"<td><span class='badge sev-{_esc(item.severity)}'>{_esc(item.severity.upper())}</span></td>"
            f"<td>{_esc(item.category)}</td>"
            f"<td><code>{_esc(loc_str)}</code></td>"
            f"<td>{_esc(item.message)}</td>"
            f"</tr>"
        )
    debt_html = (
        "\n".join(debt_rows) or "<tr><td colspan='4'>No technical debt items recorded.</td></tr>"
    )

    # Security findings (redacted)
    sec_rows = []
    for sf in sec.findings[:20]:
        loc_str = f"{sf.file_path}:{sf.line_number}" if sf.line_number else sf.file_path
        sec_rows.append(
            f"<tr>"
            f"<td><code>{_esc(sf.rule_id)}</code></td>"
            f"<td><span class='badge sev-{_esc(sf.severity)}'>{_esc(sf.severity.upper())}</span></td>"
            f"<td><code>{_esc(loc_str)}</code></td>"
            f"<td>{_esc(sf.message)}</td>"
            f"<td><code>{_esc(sf.redacted_snippet)}</code></td>"
            f"</tr>"
        )
    sec_html = (
        "\n".join(sec_rows)
        or "<tr><td colspan='5'>No local security risk indicators detected.</td></tr>"
    )

    # Git hotspots
    git_rows = []
    for hs in git.hotspots[:12]:
        git_rows.append(
            f"<tr>"
            f"<td><code>{_esc(hs.path)}</code></td>"
            f"<td class='num'>{hs.commits}</td>"
            f"<td class='num'>{hs.churn_lines}</td>"
            f"<td class='num'>{hs.max_complexity}</td>"
            f"<td class='num'><strong>{hs.risk_score:.1f}</strong></td>"
            f"</tr>"
        )
    git_html = (
        "\n".join(git_rows) or "<tr><td colspan='5'>No Git churn hotspots available.</td></tr>"
    )

    # Dependencies
    dep_rows = []
    for d in result.dependencies.declared_dependencies[:30]:
        dep_rows.append(
            f"<tr>"
            f"<td><strong>{_esc(d.name)}</strong></td>"
            f"<td><code>{_esc(d.constraint or '*')}</code></td>"
            f"<td>{_esc(d.dep_type)}</td>"
            f"<td>{_esc(d.ecosystem)}</td>"
            f"</tr>"
        )
    dep_html = (
        "\n".join(dep_rows) or "<tr><td colspan='4'>No declared dependencies found.</td></tr>"
    )

    fp_badges = []
    for item in (
        fp.frameworks
        + fp.package_managers
        + fp.build_tools
        + fp.test_frameworks
        + fp.linters
        + fp.ci_cd_systems
    ):
        fp_badges.append(f"<span class='chip'>{_esc(item)}</span>")
    fp_html = " ".join(fp_badges) or "<span class='chip'>Standard Project</span>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RPX Report — {_esc(meta.name)}</title>
<style>
  :root {{
    --bg: #0f172a;
    --panel: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --cyan: #00d9ff;
    --purple: #a78bfa;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  .container {{ max-width: 1280px; margin: 0 auto; }}
  header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
  }}
  h1 {{ margin: 0 0 6px 0; font-size: 26px; color: var(--cyan); }}
  h2 {{ margin: 0 0 14px 0; font-size: 18px; color: var(--purple); border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
  .subtitle {{ color: var(--muted); font-size: 14px; }}
  .score-box {{
    text-align: center;
    background: rgba(255,255,255,0.03);
    border: 2px solid {score_color};
    border-radius: 12px;
    padding: 12px 24px;
  }}
  .score-val {{ font-size: 34px; font-weight: 800; color: {score_color}; }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }}
  .kpi {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }}
  .kpi-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
  .kpi-val {{ font-size: 24px; font-weight: 700; margin-top: 4px; color: var(--text); }}
  .grid-2 {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
  }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    overflow-x: auto;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); }}
  th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{
    background: rgba(0, 0, 0, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12.5px;
  }}
  .bar-bg {{ width: 100%; min-width: 90px; height: 8px; background: #0f172a; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: var(--cyan); border-radius: 4px; }}
  .health-bar {{ background: var(--green); }}
  .chip {{
    display: inline-block;
    background: rgba(0, 217, 255, 0.12);
    color: var(--cyan);
    border: 1px solid rgba(0, 217, 255, 0.3);
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 12px;
    margin: 2px;
  }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    background: #334155;
  }}
  .sev-high, .sev-critical {{ background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }}
  .sev-medium {{ background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid #f59e0b; }}
  .sev-low {{ background: rgba(34, 197, 94, 0.2); color: #86efac; border: 1px solid #22c55e; }}
  .text-danger {{ color: var(--red); font-weight: 600; }}
  footer {{ text-align: center; color: var(--muted); font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>RPX — {_esc(meta.name)}</h1>
      <div class="subtitle">Path: <code>{_esc(meta.path)}</code> &bull; Scan Duration: {format_duration(result.duration_seconds)}</div>
      <div style="margin-top: 10px;">{fp_html}</div>
    </div>
    <div class="score-box">
      <div class="kpi-label">Health Score</div>
      <div class="score-val">{health.score}/100</div>
    </div>
  </header>

  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">Total Files</div><div class="kpi-val">{format_number(fs.total_files)}</div></div>
    <div class="kpi"><div class="kpi-label">Source Files</div><div class="kpi-val">{format_number(fs.source_files)}</div></div>
    <div class="kpi"><div class="kpi-label">Lines of Code</div><div class="kpi-val">{format_number(loc.total_code)}</div></div>
    <div class="kpi"><div class="kpi-label">Functions / Classes</div><div class="kpi-val">{format_number(comp.total_functions)} / {format_number(comp.total_classes)}</div></div>
    <div class="kpi"><div class="kpi-label">Avg Complexity</div><div class="kpi-val">{comp.avg_function_complexity:.2f}</div></div>
    <div class="kpi"><div class="kpi-label">Technical Debt</div><div class="kpi-val">{format_number(debt.total_items)}</div></div>
    <div class="kpi"><div class="kpi-label">Dependencies</div><div class="kpi-val">{format_number(len(result.dependencies.declared_dependencies))}</div></div>
    <div class="kpi"><div class="kpi-label">Project Size</div><div class="kpi-val">{format_bytes(result.storage.total_project_size_bytes)}</div></div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2>Language Distribution</h2>
      <table>
        <thead><tr><th>Language</th><th class="num">Files</th><th class="num">Code</th><th class="num">Comments</th><th class="num">Share</th><th>Distribution</th></tr></thead>
        <tbody>{lang_html}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Project Health Breakdown (9 Categories)</h2>
      <table>
        <thead><tr><th>Category</th><th class="num">Score</th><th>Progress</th></tr></thead>
        <tbody>{health_cat_html}</tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h2>Health Score Deductions &amp; Actionable Recommendations</h2>
    <table>
      <thead><tr><th>Category</th><th class="num">Deduction</th><th>Type</th><th>Finding</th><th>Recommendation</th></tr></thead>
      <tbody>{ded_html}</tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Code Complexity Hotspots</h2>
    <table>
      <thead><tr><th>Function</th><th>Location</th><th class="num">Cyclomatic</th><th class="num">Lines</th><th class="num">Nesting</th><th>Severity</th></tr></thead>
      <tbody>{comp_html}</tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Technical Debt Findings</h2>
    <table>
      <thead><tr><th>Severity</th><th>Category</th><th>Location</th><th>Description</th></tr></thead>
      <tbody>{debt_html}</tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Local Security Hygiene Indicators (Redacted)</h2>
    <p class="subtitle">Note: Local heuristic indicators only; secrets are automatically redacted.</p>
    <table>
      <thead><tr><th>Rule</th><th>Severity</th><th>Location</th><th>Finding</th><th>Redacted Match</th></tr></thead>
      <tbody>{sec_html}</tbody>
    </table>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2>Git Churn &amp; Change Hotspots</h2>
      <table>
        <thead><tr><th>File</th><th class="num">Commits</th><th class="num">Churn Lines</th><th class="num">Max CC</th><th class="num">Risk Score</th></tr></thead>
        <tbody>{git_html}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Declared Dependencies</h2>
      <table>
        <thead><tr><th>Package</th><th>Constraint</th><th>Type</th><th>Ecosystem</th></tr></thead>
        <tbody>{dep_html}</tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h2>Analysis Coverage Summary</h2>
    <p class="subtitle">
      Discovered: <strong>{cov.files_discovered}</strong> &bull;
      Source Analyzed: <strong>{cov.files_analyzed}</strong> &bull;
      Ignored: <strong>{cov.files_ignored}</strong> &bull;
      Binary Skipped: <strong>{cov.files_skipped_binary}</strong> &bull;
      Non-Code/Other: <strong>{cov.unsupported_file_types}</strong> &bull;
      Parse Failures: <strong>{cov.parsing_failures}</strong>
    </p>
  </div>

  <footer>
    Generated offline by <strong>RPX (Repository Project Explorer) v{__version__}</strong>
  </footer>
</div>
</body>
</html>
"""


def export_html_report(result: ScanResult, output_path: Path) -> Path:
    """Write a self-contained HTML report to output_path."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = generate_html_string(result)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path.resolve()
    except OSError as e:
        raise ExportError(f"Failed to export HTML report to {output_path}: {e}") from e

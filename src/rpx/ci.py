"""Non-interactive CI quality gate evaluation for RPX."""

from __future__ import annotations

import json
from typing import Any

from rpx.models import ScanResult


def evaluate_ci_gates(
    result: ScanResult,
    min_health_score: int = 50,
    max_high_security: int = 0,
    max_high_debt: int | None = None,
    max_complexity: int | None = None,
    fail_on_cycles: bool = False,
) -> dict[str, Any]:
    """Evaluate repository metrics against CI thresholds and return structured gate results."""
    checks: list[dict[str, Any]] = []
    passed = True

    # 1. Health score check
    actual_health = result.health.score
    health_ok = actual_health >= min_health_score
    if not health_ok:
        passed = False
    checks.append(
        {
            "gate": "min_health_score",
            "passed": health_ok,
            "threshold": f">= {min_health_score}",
            "actual": actual_health,
            "message": f"Health score is {actual_health}/100 (required >= {min_health_score})",
        }
    )

    # 2. High-severity security findings check
    actual_high_sec = result.security.by_severity.get("high", 0)
    sec_ok = actual_high_sec <= max_high_security
    if not sec_ok:
        passed = False
    checks.append(
        {
            "gate": "max_high_security",
            "passed": sec_ok,
            "threshold": f"<= {max_high_security}",
            "actual": actual_high_sec,
            "message": f"High-severity security indicators: {actual_high_sec} (allowed <= {max_high_security})",
        }
    )

    # 3. Optional high-severity debt check
    if max_high_debt is not None:
        actual_high_debt = result.debt.by_severity.get("high", 0)
        debt_ok = actual_high_debt <= max_high_debt
        if not debt_ok:
            passed = False
        checks.append(
            {
                "gate": "max_high_debt",
                "passed": debt_ok,
                "threshold": f"<= {max_high_debt}",
                "actual": actual_high_debt,
                "message": f"High-severity debt items: {actual_high_debt} (allowed <= {max_high_debt})",
            }
        )

    # 4. Optional max cyclomatic complexity check
    if max_complexity is not None:
        actual_max_cc = result.complexity.max_function_complexity
        cc_ok = actual_max_cc <= max_complexity
        if not cc_ok:
            passed = False
        checks.append(
            {
                "gate": "max_complexity",
                "passed": cc_ok,
                "threshold": f"<= {max_complexity}",
                "actual": actual_max_cc,
                "message": f"Max function cyclomatic complexity: {actual_max_cc} (allowed <= {max_complexity})",
            }
        )

    # 5. Optional circular dependency check
    if fail_on_cycles:
        actual_cycles = len(result.graph.cycles)
        cyc_ok = actual_cycles == 0
        if not cyc_ok:
            passed = False
        checks.append(
            {
                "gate": "no_circular_dependencies",
                "passed": cyc_ok,
                "threshold": "== 0",
                "actual": actual_cycles,
                "message": f"Circular module dependency cycles: {actual_cycles} (allowed == 0)",
            }
        )

    return {
        "passed": passed,
        "exit_code": 0 if passed else 1,
        "project": result.metadata.name,
        "summary": {
            "files": result.files.total_files,
            "code_lines": result.loc.total_code,
            "health_score": result.health.score,
            "avg_complexity": result.complexity.avg_function_complexity,
            "max_complexity": result.complexity.max_function_complexity,
            "debt_total": result.debt.total_items,
            "security_total": result.security.total_findings,
        },
        "checks": checks,
    }


def format_ci_report(ci_data: dict[str, Any], fmt: str = "text") -> str:
    """Format CI evaluation results as plain ANSI-free text or JSON."""
    if fmt.lower() == "json":
        return json.dumps(ci_data, indent=2)

    status_label = "PASSED" if ci_data["passed"] else "FAILED"
    s = ci_data["summary"]
    lines = [
        f"RPX CI Quality Gate Report — {ci_data['project']} [{status_label}]",
        "=" * 64,
        (
            f"Metrics: Files={s['files']} | Code LOC={s['code_lines']} | "
            f"Health={s['health_score']}/100 | Max CC={s['max_complexity']} | "
            f"Debt={s['debt_total']} | Security={s['security_total']}"
        ),
        "-" * 64,
    ]
    for chk in ci_data["checks"]:
        mark = "[PASS]" if chk["passed"] else "[FAIL]"
        lines.append(f"{mark} {chk['gate']}: {chk['message']}")
    lines.append("-" * 64)
    lines.append(f"Result: {status_label} (exit code {ci_data['exit_code']})")
    return "\n".join(lines)

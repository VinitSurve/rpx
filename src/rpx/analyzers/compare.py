"""Snapshot and repository comparison engine."""

from __future__ import annotations

from typing import Any

from rpx.models import ComparisonDiff, ScanResult
from rpx.snapshots import extract_snapshot_summary


def compare_snapshot_dicts(
    snap_a: dict[str, Any],
    snap_b: dict[str, Any],
) -> ComparisonDiff:
    """Compare two normalized snapshot dictionaries (A = baseline/before, B = target/after)."""
    label_a = f"{snap_a.get('project_name', 'A')} ({snap_a.get('snapshot_id', 'baseline')})"
    label_b = f"{snap_b.get('project_name', 'B')} ({snap_b.get('snapshot_id', 'current')})"

    ts_a = str(snap_a.get("created_at", ""))
    ts_b = str(snap_b.get("created_at", ""))

    ma = snap_a.get("metrics", {})
    mb = snap_b.get("metrics", {})

    metric_keys = [
        "total_files",
        "source_files",
        "test_files",
        "total_directories",
        "total_lines",
        "code_lines",
        "comment_lines",
        "blank_lines",
        "total_size_bytes",
        "dependency_count",
        "health_score",
        "avg_complexity",
        "max_complexity",
        "debt_total",
        "security_total",
    ]
    metrics_diff: dict[str, dict[str, int | float]] = {}
    for k in metric_keys:
        va = ma.get(k, 0)
        vb = mb.get(k, 0)
        delta = round(vb - va, 2) if isinstance(va, float) or isinstance(vb, float) else (vb - va)
        metrics_diff[k] = {"before": va, "after": vb, "delta": delta}

    # Language deltas
    langs_a = snap_a.get("languages", {})
    langs_b = snap_b.get("languages", {})
    all_langs = sorted(set(langs_a.keys()) | set(langs_b.keys()))
    lang_deltas: dict[str, dict[str, int | float]] = {}
    for lg in all_langs:
        la = langs_a.get(lg, {})
        lb = langs_b.get(lg, {})
        ca = int(la.get("code_lines", 0))
        cb = int(lb.get("code_lines", 0))
        fa = int(la.get("files", 0))
        fb = int(lb.get("files", 0))
        lang_deltas[lg] = {
            "before_files": fa,
            "after_files": fb,
            "delta_files": fb - fa,
            "before_code": ca,
            "after_code": cb,
            "delta_code": cb - ca,
        }

    # Dependencies added & removed
    deps_a = set(snap_a.get("dependencies", []))
    deps_b = set(snap_b.get("dependencies", []))
    deps_added = sorted(deps_b - deps_a)
    deps_removed = sorted(deps_a - deps_b)

    # Directory growth
    dirs_a = snap_a.get("directories", {})
    dirs_b = snap_b.get("directories", {})
    all_dirs = sorted(set(dirs_a.keys()) | set(dirs_b.keys()))
    dir_growth: list[dict[str, str | int]] = []
    for dpath in all_dirs:
        da = dirs_a.get(dpath, {})
        db = dirs_b.get(dpath, {})
        fa = int(da.get("files", 0))
        fb = int(db.get("files", 0))
        sa = int(da.get("size_bytes", 0))
        sb = int(db.get("size_bytes", 0))
        if fb != fa or sb != sa:
            dir_growth.append(
                {
                    "path": dpath,
                    "before_files": fa,
                    "after_files": fb,
                    "delta_files": fb - fa,
                    "before_bytes": sa,
                    "after_bytes": sb,
                    "delta_bytes": sb - sa,
                }
            )
    dir_growth.sort(key=lambda x: abs(int(x["delta_bytes"])), reverse=True)

    # Debt deltas
    debt_a = snap_a.get("debt_by_category", {})
    debt_b = snap_b.get("debt_by_category", {})
    all_debt_cats = sorted(set(debt_a.keys()) | set(debt_b.keys()))
    debt_deltas: dict[str, int] = {}
    for cat in all_debt_cats:
        debt_deltas[cat] = int(debt_b.get(cat, 0)) - int(debt_a.get(cat, 0))

    return ComparisonDiff(
        label_a=label_a,
        label_b=label_b,
        timestamp_a=ts_a,
        timestamp_b=ts_b,
        metrics=metrics_diff,
        language_deltas=lang_deltas,
        dependencies_added=deps_added,
        dependencies_removed=deps_removed,
        directory_growth=dir_growth[:15],
        debt_deltas=debt_deltas,
    )


def compare_scan_results(
    res_a: ScanResult,
    res_b: ScanResult,
    label_a: str = "Project A",
    label_b: str = "Project B",
) -> ComparisonDiff:
    """Compare two ScanResult instances directly."""
    snap_a = extract_snapshot_summary(res_a, label=label_a)
    snap_b = extract_snapshot_summary(res_b, label=label_b)
    diff = compare_snapshot_dicts(snap_a, snap_b)
    diff.label_a = f"{res_a.metadata.name} ({label_a})"
    diff.label_b = f"{res_b.metadata.name} ({label_b})"
    return diff

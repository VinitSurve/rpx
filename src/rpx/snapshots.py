"""Local repository snapshot storage and historical evolution tracking."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rpx.config import get_data_dir
from rpx.exceptions import SnapshotError
from rpx.models import ScanResult


def _project_snapshot_dir(project_root: Path) -> Path:
    resolved = str(project_root.resolve())
    h = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_root.name)
    d = get_data_dir() / "snapshots" / f"{safe_name}_{h}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_snapshot_summary(result: ScanResult, label: str = "scan") -> dict[str, Any]:
    """Extract a normalized snapshot dictionary from a ScanResult."""
    now = datetime.now(timezone.utc)
    short_hash = (
        result.git.commit_hash
        or hashlib.sha256(f"{result.metadata.name}:{now.isoformat()}".encode("utf-8")).hexdigest()[
            :7
        ]
    )
    snap_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{short_hash}"

    lang_items = (
        result.languages.languages.values()
        if hasattr(result.languages, "languages")
        else result.languages
    )
    languages_map = {
        lang.name: {
            "files": lang.files,
            "code_lines": lang.code_lines,
            "percentage": lang.percentage,
        }
        for lang in lang_items
    }
    deps_list = sorted({d.name for d in result.dependencies.dependencies})
    dir_map = {
        d.path: {
            "files": d.file_count,
            "size_bytes": d.total_size_bytes,
        }
        for d in result.directory_stats
    }

    avg_cc = result.complexity.avg_function_complexity if result.complexity else 0.0
    max_cc = result.complexity.max_function_complexity if result.complexity else 0
    debt_total = (
        result.debt.total_items
        if result.debt
        else (
            result.health.todo_count
            + result.health.fixme_count
            + result.health.hack_count
            + result.health.xxx_count
        )
    )
    debt_by_cat = result.debt.by_category if result.debt else {}
    sec_total = result.security.total_findings if result.security else 0

    return {
        "snapshot_id": snap_id,
        "label": label,
        "created_at": now.isoformat(),
        "project_name": result.metadata.name,
        "project_path": result.metadata.absolute_path,
        "git_branch": result.git.branch,
        "git_commit": result.git.commit_hash,
        "metrics": {
            "total_files": result.file_stats.total_files,
            "source_files": result.file_stats.source_files,
            "test_files": result.file_stats.test_files,
            "total_directories": result.file_stats.total_directories,
            "total_lines": result.loc_stats.total_physical_lines,
            "code_lines": result.loc_stats.code_lines,
            "comment_lines": result.loc_stats.comment_lines,
            "blank_lines": result.loc_stats.blank_lines,
            "total_size_bytes": result.storage.total_project_size_bytes,
            "dependency_count": len(deps_list),
            "health_score": result.health.score,
            "avg_complexity": avg_cc,
            "max_complexity": max_cc,
            "debt_total": debt_total,
            "security_total": sec_total,
        },
        "languages": languages_map,
        "dependencies": deps_list,
        "directories": dir_map,
        "debt_by_category": debt_by_cat,
    }


def save_snapshot(
    result: ScanResult,
    label: str = "manual",
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Save a snapshot of the ScanResult to local snapshot storage."""
    root = project_root or Path(result.metadata.absolute_path)
    snap_dir = _project_snapshot_dir(root)
    summary = extract_snapshot_summary(result, label=label)
    snap_file = snap_dir / f"{summary['snapshot_id']}.json"
    try:
        snap_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError as e:
        raise SnapshotError(f"Failed to write snapshot {snap_file}: {e}") from e
    summary["snapshot_file"] = str(snap_file)
    return summary


def list_snapshots(project_root: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """List saved snapshots for project_root in reverse chronological order (newest first)."""
    snap_dir = _project_snapshot_dir(project_root)
    snapshots: list[dict[str, Any]] = []
    for f in sorted(snap_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["snapshot_file"] = str(f)
            snapshots.append(data)
        except Exception:
            continue
    if limit is not None and limit > 0:
        return snapshots[:limit]
    return snapshots


def get_snapshot(project_root: Path, identifier: str) -> dict[str, Any]:
    """Retrieve a snapshot by ID, label, 'latest', 'previous', or JSON file path."""
    # Check if identifier is a path to an exported JSON file
    cand_path = Path(identifier)
    if cand_path.is_file():
        try:
            raw = json.loads(cand_path.read_text(encoding="utf-8"))
            if "metrics" in raw and "snapshot_id" in raw:
                return raw
            # Support comparing against a full `rpx report --format json` file
            if "metadata" in raw and ("files" in raw or "file_stats" in raw):
                return _normalize_exported_json_report(raw, cand_path.stem)
        except Exception as e:
            raise SnapshotError(f"Could not load snapshot from file {cand_path}: {e}") from e

    snaps = list_snapshots(project_root)
    if not snaps:
        raise SnapshotError(
            f"No snapshots found for {project_root.name}. Run `rpx snapshot` to create one."
        )

    if identifier in ("latest", "last", "0"):
        return snaps[0]
    if identifier in ("previous", "prev", "1"):
        return snaps[1] if len(snaps) > 1 else snaps[0]

    for s in snaps:
        if (
            s.get("snapshot_id") == identifier
            or s.get("label") == identifier
            or str(s.get("snapshot_id", "")).startswith(identifier)
            or s.get("git_commit") == identifier
        ):
            return s

    raise SnapshotError(f"Snapshot '{identifier}' not found for {project_root.name}.")


def clean_snapshots(project_root: Path, keep_last: int = 0) -> int:
    """Remove saved snapshots for project_root, optionally keeping the newest `keep_last`."""
    snap_dir = _project_snapshot_dir(project_root)
    files = sorted(snap_dir.glob("*.json"), reverse=True)
    to_remove = files[keep_last:] if keep_last > 0 else files
    removed = 0
    for f in to_remove:
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def _normalize_exported_json_report(raw: dict[str, Any], label: str) -> dict[str, Any]:
    """Convert an exported RPX JSON report into snapshot summary format."""
    meta = raw.get("metadata", {})
    fs = raw.get("files", raw.get("file_stats", {}))
    loc = raw.get("loc", raw.get("loc_stats", {}))
    storage = raw.get("storage", {})
    health = raw.get("health", {})
    comp = raw.get("complexity") or {}
    debt = raw.get("debt") or {}
    sec = raw.get("security") or {}
    deps_sec = raw.get("dependencies", {})
    deps_list = sorted(
        {
            d.get("name", "")
            for d in deps_sec.get("declared_dependencies", deps_sec.get("dependencies", []))
            if d.get("name")
        }
    )

    raw_langs = raw.get("languages", {})
    if isinstance(raw_langs, dict) and "languages" in raw_langs:
        lang_iter = raw_langs["languages"].values()
    elif isinstance(raw_langs, list):
        lang_iter = raw_langs
    else:
        lang_iter = []

    langs = {
        lg.get("name", "Unknown"): {
            "files": lg.get("files", 0),
            "code_lines": lg.get("code_lines", 0),
            "percentage": lg.get("percentage", 0.0),
        }
        for lg in lang_iter
    }

    raw_dirs = raw.get("directories", {})
    if isinstance(raw_dirs, dict) and "largest_directories" in raw_dirs:
        dir_iter = raw_dirs["largest_directories"]
    elif isinstance(raw_dirs, list):
        dir_iter = raw_dirs
    else:
        dir_iter = raw.get("directory_stats", [])

    dirs = {
        d.get("path", "."): {
            "files": d.get("file_count", 0),
            "size_bytes": d.get("total_size_bytes", 0),
        }
        for d in dir_iter
    }

    total_phys = loc.get("total_physical_lines", loc.get("total_physical", 0))
    code_ln = loc.get("code_lines", loc.get("total_code", 0))
    comment_ln = loc.get("comment_lines", loc.get("total_comment", 0))
    blank_ln = loc.get("blank_lines", loc.get("total_blank", 0))

    return {
        "snapshot_id": label,
        "label": label,
        "created_at": meta.get("scan_timestamp", ""),
        "project_name": meta.get("name", label),
        "project_path": meta.get("absolute_path", meta.get("path", "")),
        "git_branch": raw.get("git", {}).get("branch"),
        "git_commit": raw.get("git", {}).get("commit_hash"),
        "metrics": {
            "total_files": fs.get("total_files", 0),
            "source_files": fs.get("source_files", 0),
            "test_files": fs.get("test_files", 0),
            "total_directories": fs.get("total_directories", 0),
            "total_lines": total_phys,
            "code_lines": code_ln,
            "comment_lines": comment_ln,
            "blank_lines": blank_ln,
            "total_size_bytes": storage.get("total_project_size_bytes", 0),
            "dependency_count": len(deps_list),
            "health_score": health.get("score", 0),
            "avg_complexity": comp.get("avg_function_complexity", 0.0),
            "max_complexity": comp.get("max_function_complexity", 0),
            "debt_total": debt.get("total_items", 0),
            "security_total": sec.get("total_findings", 0),
        },
        "languages": langs,
        "dependencies": deps_list,
        "directories": dirs,
        "debt_by_category": debt.get("by_category", {}),
    }

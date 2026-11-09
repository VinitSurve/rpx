"""Incremental repository scan cache manager."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rpx.config import RPXConfig, get_data_dir
from rpx.models import ClassComplexity, FileComplexity, FunctionComplexity

CACHE_SCHEMA_VERSION = "1.0.0"


def _project_cache_key(project_root: Path) -> str:
    resolved = str(project_root.resolve())
    h = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_root.name)
    return f"{safe_name}_{h}"


def get_cache_dir(config: RPXConfig | None = None) -> Path:
    if config and config.cache_dir:
        d = Path(config.cache_dir).expanduser().resolve()
    else:
        d = get_data_dir() / "scan_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def serialize_file_complexity(fc: FileComplexity | None) -> dict[str, Any] | None:
    if fc is None:
        return None
    return asdict(fc)


def deserialize_file_complexity(data: dict[str, Any] | None) -> FileComplexity | None:
    if not data or not isinstance(data, dict):
        return None
    try:
        funcs = [
            FunctionComplexity(**fn_dict)
            for fn_dict in data.get("functions", [])
            if isinstance(fn_dict, dict)
        ]
        classes = [
            ClassComplexity(**cls_dict)
            for cls_dict in data.get("classes", [])
            if isinstance(cls_dict, dict)
        ]
        return FileComplexity(
            path=str(data.get("path", "")),
            language=str(data.get("language", "")),
            line_count=int(data.get("line_count", 0)),
            function_count=int(data.get("function_count", len(funcs))),
            class_count=int(data.get("class_count", len(classes))),
            avg_complexity=float(data.get("avg_complexity", 1.0)),
            max_complexity=int(data.get("max_complexity", 1)),
            max_nesting_depth=int(data.get("max_nesting_depth", 0)),
            functions=funcs,
            classes=classes,
            is_long_file=bool(data.get("is_long_file", False)),
        )
    except Exception:
        return None


class ScanCacheManager:
    """Manages incremental file analysis cache for a repository."""

    def __init__(
        self,
        project_root: Path,
        config: RPXConfig,
        ignore_signature: str,
        enabled: bool = True,
        force_full: bool = False,
    ):
        self.project_root = project_root.resolve()
        self.config = config
        self.ignore_signature = ignore_signature
        self.enabled = enabled and config.use_cache
        self.force_full = force_full
        self.cache_dir = get_cache_dir(config)
        self.cache_file = self.cache_dir / f"{_project_cache_key(self.project_root)}.json"

        self.previous_files: dict[str, dict[str, Any]] = {}
        self.invalidated_reason: str | None = None
        self._new_files: dict[str, dict[str, Any]] = {}

        if self.enabled:
            self._load()

    def _load(self) -> None:
        if self.force_full:
            self.invalidated_reason = "Explicit --full scan requested"
            return

        if not self.cache_file.is_file():
            self.invalidated_reason = "No previous cache found (cold scan)"
            return

        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            self.invalidated_reason = "Cache file corrupted; falling back to full scan"
            return

        if raw.get("schema_version") != CACHE_SCHEMA_VERSION:
            self.invalidated_reason = "Cache schema version updated"
            return

        if raw.get("config_signature") != self.config.signature:
            self.invalidated_reason = "Analysis configuration settings changed"
            return

        if raw.get("ignore_signature") != self.ignore_signature:
            self.invalidated_reason = "Ignore rules (.gitignore/.rpxignore/CLI) changed"
            return

        files_dict = raw.get("files")
        if isinstance(files_dict, dict):
            self.previous_files = files_dict

    def get_cached_entry(
        self, rel_path: str, mtime_ns: int, size_bytes: int
    ) -> dict[str, Any] | None:
        """Return cached file analysis entry if mtime_ns and size_bytes match."""
        if not self.enabled or self.force_full:
            return None
        entry = self.previous_files.get(rel_path)
        if not entry:
            return None
        if entry.get("mtime_ns") == mtime_ns and entry.get("size_bytes") == size_bytes:
            return entry
        return None

    def record_entry(self, rel_path: str, entry: dict[str, Any]) -> None:
        """Record updated file analysis entry for saving at the end of scan."""
        self._new_files[rel_path] = entry

    def compute_diff_stats(
        self,
        current_hashes: dict[str, str],
        cache_hits: int,
        cache_misses: int,
    ) -> tuple[int, int, int, int]:
        """Compute (added_files, modified_files, deleted_files, renamed_files) compared to previous cache."""
        if not self.previous_files:
            return len(self._new_files), 0, 0, 0

        prev_paths = set(self.previous_files.keys())
        curr_paths = set(self._new_files.keys())

        added_candidates = curr_paths - prev_paths
        deleted_candidates = prev_paths - curr_paths
        common_paths = curr_paths & prev_paths

        modified_count = sum(
            1
            for p in common_paths
            if (
                self._new_files[p].get("mtime_ns") != self.previous_files[p].get("mtime_ns")
                or self._new_files[p].get("size_bytes") != self.previous_files[p].get("size_bytes")
            )
        )

        # Detect renames by matching SHA-256 of deleted files to added files
        deleted_hashes: dict[str, list[str]] = {}
        for dp in deleted_candidates:
            h = self.previous_files[dp].get("sha256")
            if h:
                deleted_hashes.setdefault(str(h), []).append(dp)

        renamed_count = 0
        for ap in list(added_candidates):
            h = current_hashes.get(ap) or self._new_files[ap].get("sha256")
            if h and h in deleted_hashes and deleted_hashes[h]:
                deleted_hashes[h].pop()
                renamed_count += 1

        true_added = max(0, len(added_candidates) - renamed_count)
        true_deleted = max(0, len(deleted_candidates) - renamed_count)
        return true_added, modified_count, true_deleted, renamed_count

    def save(self) -> None:
        """Persist the updated cache to disk."""
        if not self.enabled:
            return
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "project_path": str(self.project_root),
            "project_name": self.project_root.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "config_signature": self.config.signature,
            "ignore_signature": self.ignore_signature,
            "file_count": len(self._new_files),
            "files": self._new_files,
        }
        try:
            self.cache_file.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass


def clear_cache(project_root: Path | None = None, config: RPXConfig | None = None) -> int:
    """Clear incremental scan cache for a specific project or all cached projects."""
    cache_dir = get_cache_dir(config)
    removed = 0
    if project_root is not None:
        target = cache_dir / f"{_project_cache_key(project_root)}.json"
        if target.is_file():
            try:
                target.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    for f in cache_dir.glob("*.json"):
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def get_cache_status(
    project_root: Path | None = None, config: RPXConfig | None = None
) -> dict[str, Any]:
    """Return status information about the incremental scan cache."""
    cache_dir = get_cache_dir(config)
    entries: list[dict[str, Any]] = []
    total_bytes = 0

    for f in sorted(cache_dir.glob("*.json")):
        try:
            sz = f.stat().st_size
            total_bytes += sz
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append(
                {
                    "cache_file": f.name,
                    "project_name": data.get("project_name", "unknown"),
                    "project_path": data.get("project_path", ""),
                    "updated_at": data.get("updated_at", ""),
                    "cached_files": data.get("file_count", 0),
                    "size_bytes": sz,
                }
            )
        except Exception:
            continue

    current_project_cached = False
    if project_root is not None:
        key_file = f"{_project_cache_key(project_root)}.json"
        current_project_cached = any(e["cache_file"] == key_file for e in entries)

    return {
        "cache_dir": str(cache_dir),
        "total_cache_files": len(entries),
        "total_size_bytes": total_bytes,
        "current_project_cached": current_project_cached,
        "entries": entries,
    }

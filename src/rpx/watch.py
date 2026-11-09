"""Debounced filesystem watch mode for live repository re-analysis."""

from __future__ import annotations

import os
import time
from pathlib import Path

from rpx.constants import (
    COLOR_ACCENT,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
)
from rpx.reporters.terminal import TerminalReporter
from rpx.scanner import ProjectScanner
from rpx.utils.ignore import IgnoreManager


def collect_workspace_state(
    project_root: Path,
    ignore_manager: IgnoreManager,
) -> dict[str, tuple[int, int]]:
    """Collect a lightweight (mtime_ns, size_bytes) fingerprint of non-ignored workspace files."""
    state: dict[str, tuple[int, int]] = {}
    for root, dirs, files in os.walk(project_root, topdown=True, followlinks=False):
        root_path = Path(root)
        if root_path != project_root and ignore_manager.is_ignored(root_path, is_dir=True):
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if not ignore_manager.is_ignored(root_path / d, is_dir=True)]
        for fname in files:
            fpath = root_path / fname
            if ignore_manager.is_ignored(fpath, is_dir=False) or fpath.is_symlink():
                continue
            try:
                st = fpath.stat()
                rel = str(fpath.relative_to(project_root)).replace("\\", "/")
                mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
                state[rel] = (mtime_ns, st.st_size)
            except OSError:
                continue
    return state


def detect_workspace_changes(
    prev_state: dict[str, tuple[int, int]],
    curr_state: dict[str, tuple[int, int]],
) -> list[str]:
    """Return list of changed, added, or deleted relative file paths."""
    changed: list[str] = []
    all_keys = set(prev_state.keys()) | set(curr_state.keys())
    for k in sorted(all_keys):
        if prev_state.get(k) != curr_state.get(k):
            changed.append(k)
    return changed


def run_watch_mode(
    target_path: Path,
    reporter: TerminalReporter,
    interval_seconds: float = 1.5,
    debounce_seconds: float = 0.5,
    max_cycles: int | None = None,
) -> None:
    """Monitor target_path for file changes with debouncing and trigger incremental scans."""
    scanner = ProjectScanner(target_path, use_cache=True)
    result = scanner.scan()
    reporter.render_summary(result)

    prev_state = collect_workspace_state(scanner.project_root, scanner.ignore_manager)
    reporter.console.print(
        f"[bold {COLOR_ACCENT}]Watching[/] [{COLOR_PRIMARY}]{scanner.project_root}[/] "
        f"[dim {COLOR_MUTED}](interval={interval_seconds}s, press Ctrl+C to stop)[/]"
    )

    cycles = 0
    try:
        while True:
            if max_cycles is not None and cycles >= max_cycles:
                break
            cycles += 1
            time.sleep(interval_seconds)

            curr_state = collect_workspace_state(scanner.project_root, scanner.ignore_manager)
            changes = detect_workspace_changes(prev_state, curr_state)
            if changes:
                if debounce_seconds > 0:
                    time.sleep(debounce_seconds)
                    curr_state = collect_workspace_state(
                        scanner.project_root, scanner.ignore_manager
                    )
                    changes = detect_workspace_changes(prev_state, curr_state)

                prev_state = curr_state
                sample = ", ".join(changes[:3])
                if len(changes) > 3:
                    sample += f" (+{len(changes) - 3} more)"
                reporter.console.print(
                    f"\n[{COLOR_WARNING}]↻ Detected {len(changes)} file change(s) ({sample}). Re-analyzing incrementally...[/]"
                )
                result = scanner.scan()
                reporter.render_summary(result)
                reporter.console.print(
                    f"[{COLOR_SUCCESS}]✔ Incremental scan complete (Cache hits: {result.cache_stats.hits}). Watching for changes...[/]"
                )
    except KeyboardInterrupt:
        reporter.console.print(f"\n[dim {COLOR_MUTED}]Stopped RPX watch mode.[/]")

"""Project scanner orchestrator and recursive filesystem traversal engine."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Sequence

from rpx.analyzers.dependencies import analyze_dependencies
from rpx.analyzers.files import summarize_directories, summarize_files
from rpx.analyzers.git import analyze_git
from rpx.analyzers.health import analyze_health
from rpx.analyzers.languages import (
    calculate_language_distribution,
    detect_file_language,
)
from rpx.analyzers.loc import analyze_file_loc
from rpx.analyzers.metadata import build_metadata, detect_project_root
from rpx.analyzers.storage import analyze_storage
from rpx.exceptions import PathNotFoundError
from rpx.models import (
    DependencyAnalysis,
    DirectoryInfo,
    FileInfo,
    FileLOC,
    GitAnalytics,
    LOCStats,
    ScanResult,
)
from rpx.utils.filesystem import (
    compute_file_hash,
    get_modification_time,
    get_safe_stat,
    is_binary_file,
)
from rpx.utils.ignore import IgnoreManager


class ProjectScanner:
    """Orchestrates filesystem scanning and analytical engines for a software repository."""

    def __init__(
        self,
        target_path: Path | str,
        ranking_limit: int = 10,
        max_depth: int = 3,
        cli_exclusions: Sequence[str] | None = None,
        include_ignored: bool = False,
        enable_git: bool = True,
        enable_deps: bool = True,
        progress_callback: Callable[[str, int], None] | None = None,
    ):
        raw_path = Path(target_path)
        if not raw_path.exists():
            raise PathNotFoundError(f"Target path does not exist: {raw_path}")

        self.project_root = detect_project_root(raw_path)
        self.ranking_limit = ranking_limit
        self.max_depth = max_depth
        self.cli_exclusions = cli_exclusions or []
        self.include_ignored = include_ignored
        self.enable_git = enable_git
        self.enable_deps = enable_deps
        self.progress_callback = progress_callback
        self.ignore_manager = IgnoreManager(
            self.project_root,
            cli_exclusions=self.cli_exclusions,
            include_ignored=self.include_ignored,
        )

    def scan(self) -> ScanResult:
        """Perform the complete scan and return a comprehensive ScanResult."""
        start_time = time.perf_counter()

        file_infos: list[FileInfo] = []
        file_locs: list[FileLOC] = []
        empty_files: list[str] = []
        dir_infos: list[DirectoryInfo] = []
        file_hashes: dict[str, str] = {}
        warnings: list[str] = []

        symlinks_count = 0
        unreadable_count = 0
        skipped_count = 0

        aggregated_indicators = {
            "todo": 0,
            "fixme": 0,
            "hack": 0,
            "xxx": 0,
            "debug": 0,
        }

        # 1. Walk the filesystem
        for root, dirs, files in os.walk(self.project_root, topdown=True, followlinks=False):
            root_path = Path(root)

            # Check if root itself is ignored (except project_root)
            if root_path != self.project_root and self.ignore_manager.is_ignored(
                root_path, is_dir=True
            ):
                dirs.clear()  # Do not descend into ignored directory!
                continue

            # Filter subdirectories in-place so ignored directories are never entered
            dirs[:] = [
                d for d in dirs if not self.ignore_manager.is_ignored(root_path / d, is_dir=True)
            ]

            # Directory metrics
            try:
                rel_dir = root_path.relative_to(self.project_root)
                depth = len(rel_dir.parts)
            except ValueError:
                depth = 0

            dir_size = 0
            dir_file_count = 0

            for filename in files:
                file_path = root_path / filename

                # Check ignore
                if self.ignore_manager.is_ignored(file_path, is_dir=False):
                    skipped_count += 1
                    continue

                # Symlink check
                if file_path.is_symlink():
                    symlinks_count += 1
                    # Do not follow symlinks by default
                    continue

                stat_res = get_safe_stat(file_path)
                if stat_res is None:
                    unreadable_count += 1
                    continue

                size = stat_res.st_size
                mtime_str = get_modification_time(stat_res) or "Unknown"
                dir_size += size
                dir_file_count += 1

                try:
                    rel_file = str(file_path.relative_to(self.project_root))
                except ValueError:
                    rel_file = str(file_path)

                if size == 0:
                    empty_files.append(rel_file)

                # Check binary
                is_bin = is_binary_file(file_path)

                # File Info
                fi = FileInfo(
                    path=rel_file,
                    size_bytes=size,
                    modified_time=mtime_str,
                    is_source=False,
                    is_test="test" in rel_file.lower(),
                )

                # Language detection and LOC analysis
                lang = detect_file_language(file_path)
                if lang and not is_bin:
                    fi.is_source = True
                    floc, ind = analyze_file_loc(file_path, lang)
                    if floc is not None:
                        # Use relative path in FileLOC
                        floc.path = rel_file
                        file_locs.append(floc)
                        fi.lines_of_code = floc.code
                        for k, v in ind.items():
                            aggregated_indicators[k] += v

                file_infos.append(fi)

                # Compute hash for duplicate checking on smaller non-empty files
                if 0 < size <= 2 * 1024 * 1024 and not is_bin:
                    f_hash = compute_file_hash(file_path)
                    if f_hash:
                        file_hashes[rel_file] = f_hash

            dir_infos.append(
                DirectoryInfo(
                    path=str(rel_dir) if str(rel_dir) != "." else "[root]",
                    file_count=dir_file_count,
                    total_size_bytes=dir_size,
                    depth=depth,
                )
            )

        # 2. File & Directory Summaries
        file_stats = summarize_files(
            file_infos=file_infos,
            file_locs=file_locs,
            empty_files=empty_files,
            symlinks_count=symlinks_count,
            unreadable_count=unreadable_count,
            skipped_count=skipped_count,
            total_directories=len(dir_infos),
            ranking_limit=self.ranking_limit,
        )
        dir_stats = summarize_directories(dir_infos, ranking_limit=self.ranking_limit)

        # 3. LOC Statistics aggregation
        loc_stats = self._build_loc_stats(file_locs)

        # 4. Language Distribution
        lang_dist = calculate_language_distribution(file_locs)

        # 5. Dependency Analysis
        if self.enable_deps:
            deps = analyze_dependencies(self.project_root)
        else:
            deps = DependencyAnalysis()

        # 6. Git Analytics
        if self.enable_git:
            git_stats = analyze_git(self.project_root)
        else:
            git_stats = GitAnalytics()

        # 7. Health Analysis
        health = analyze_health(
            project_root=self.project_root,
            file_infos=file_infos,
            file_locs=file_locs,
            dependencies=deps,
            git=git_stats,
            indicators=aggregated_indicators,
            file_hashes=file_hashes,
        )

        # 8. Storage Analysis
        storage = analyze_storage(file_infos, dir_infos, ranking_limit=self.ranking_limit)

        # 9. Project Metadata
        scan_duration = time.perf_counter() - start_time
        meta = build_metadata(
            project_root=self.project_root,
            file_infos=file_infos,
            detected_ecosystems=deps.ecosystems,
            first_commit_date=git_stats.first_commit_date,
            last_commit_date=git_stats.latest_commit_date,
            scan_duration=scan_duration,
        )

        # Collect any warnings
        warnings.extend(health.warnings)
        if unreadable_count > 0:
            warnings.append(
                f"{unreadable_count} file(s) could not be read due to permission or I/O errors."
            )

        return ScanResult(
            metadata=meta,
            files=file_stats,
            directories=dir_stats,
            loc=loc_stats,
            languages=lang_dist,
            dependencies=deps,
            git=git_stats,
            health=health,
            storage=storage,
            warnings=warnings,
            duration_seconds=scan_duration,
        )

    def _build_loc_stats(self, file_locs: list[FileLOC]) -> LOCStats:
        """Aggregate global LOC statistics and compute reconciliations."""
        total_p = sum(floc.total_physical for floc in file_locs)
        total_c = sum(floc.code for floc in file_locs)
        total_m = sum(floc.comments for floc in file_locs)
        total_b = sum(floc.blank for floc in file_locs)
        total_in = sum(floc.inline_comments for floc in file_locs)
        count = len(file_locs)

        avg_code = round(total_c / count, 1) if count > 0 else 0.0
        avg_phys = round(total_p / count, 1) if count > 0 else 0.0

        largest_file = None
        if file_locs:
            max_loc_file = max(file_locs, key=lambda floc: floc.code)
            largest_file = (max_loc_file.path, max_loc_file.code)

        highest_ratio_file = None
        if file_locs:
            # files with at least 10 lines of code to avoid divide-by-zero or trivial skew
            valid_ratio_files = [floc for floc in file_locs if floc.code >= 10]
            if valid_ratio_files:
                max_ratio_file = max(valid_ratio_files, key=lambda floc: floc.comments / floc.code)
                ratio = round(max_ratio_file.comments / max_ratio_file.code, 2)
                highest_ratio_file = (max_ratio_file.path, ratio)

        return LOCStats(
            total_physical=total_p,
            total_code=total_c,
            total_comment=total_m,
            total_blank=total_b,
            total_inline_comments=total_in,
            analyzed_files_count=count,
            avg_code_lines_per_file=avg_code,
            avg_physical_lines_per_file=avg_phys,
            largest_file_by_loc=largest_file,
            highest_comment_ratio_file=highest_ratio_file,
            per_file_loc=file_locs,
        )

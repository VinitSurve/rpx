"""Project scanner orchestrator, incremental cache engine, and code intelligence coordinator."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Sequence

from rpx.analyzers.complexity import (
    aggregate_complexity,
    analyze_single_file_complexity,
)
from rpx.analyzers.debt import analyze_technical_debt
from rpx.analyzers.dependencies import analyze_dependencies
from rpx.analyzers.files import summarize_directories, summarize_files
from rpx.analyzers.fingerprint import analyze_project_fingerprint
from rpx.analyzers.git import analyze_git
from rpx.analyzers.graph import analyze_dependency_graph
from rpx.analyzers.health import analyze_health
from rpx.analyzers.languages import (
    calculate_language_distribution,
    detect_file_language,
)
from rpx.analyzers.loc import analyze_file_loc
from rpx.analyzers.metadata import build_metadata, detect_project_root
from rpx.analyzers.monorepo import analyze_monorepo
from rpx.analyzers.security import analyze_security
from rpx.analyzers.storage import analyze_storage
from rpx.cache import (
    ScanCacheManager,
    deserialize_file_complexity,
    serialize_file_complexity,
)
from rpx.config import RPXConfig, load_config
from rpx.constants import MAX_LOC_FILE_SIZE_BYTES
from rpx.exceptions import PathNotFoundError
from rpx.models import (
    CacheStats,
    CoverageReport,
    DependencyAnalysis,
    DirectoryInfo,
    FileComplexity,
    FileInfo,
    FileLOC,
    FileRecord,
    GitAnalytics,
    IgnoredItem,
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
    """Orchestrates filesystem scanning, incremental caching, and analytical engines."""

    def __init__(
        self,
        target_path: Path | str,
        ranking_limit: int = 10,
        max_depth: int = 3,
        cli_exclusions: Sequence[str] | None = None,
        include_ignored: bool = False,
        enable_git: bool = True,
        enable_deps: bool = True,
        use_cache: bool = True,
        force_full: bool = False,
        explain_ignored: bool = False,
        package_filter: str | None = None,
        config: RPXConfig | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ):
        raw_path = Path(target_path)
        if not raw_path.exists():
            raise PathNotFoundError(f"Target path does not exist: {raw_path}")

        self.project_root = detect_project_root(raw_path)
        self.config = config or load_config(self.project_root)
        self.ranking_limit = ranking_limit or self.config.ranking_limit
        self.max_depth = max_depth or self.config.max_depth

        combined_exclusions = list(self.config.exclude)
        if cli_exclusions:
            combined_exclusions.extend(cli_exclusions)
        self.cli_exclusions = combined_exclusions

        self.include_ignored = include_ignored or self.config.include_ignored
        self.enable_git = enable_git and not self.config.no_git
        self.enable_deps = enable_deps and not self.config.no_deps
        self.use_cache = use_cache and self.config.use_cache
        self.force_full = force_full
        self.explain_ignored = explain_ignored
        self.package_filter = package_filter
        self.progress_callback = progress_callback

        self.ignore_manager = IgnoreManager(
            self.project_root,
            cli_exclusions=self.cli_exclusions,
            include_ignored=self.include_ignored,
        )

    def scan(self) -> ScanResult:
        """Perform the complete scan and return a comprehensive ScanResult."""
        start_time = time.perf_counter()

        cache_mgr = ScanCacheManager(
            project_root=self.project_root,
            config=self.config,
            ignore_signature=self.ignore_manager.signature,
            enabled=self.use_cache,
            force_full=self.force_full,
        )

        file_infos: list[FileInfo] = []
        file_records: list[FileRecord] = []
        file_locs: list[FileLOC] = []
        file_complexities: list[FileComplexity] = []
        empty_files: list[str] = []
        dir_infos: list[DirectoryInfo] = []
        file_hashes: dict[str, str] = {}
        warnings: list[str] = []
        ignored_items: list[IgnoredItem] = []

        symlinks_count = 0
        unreadable_count = 0
        skipped_count = 0
        files_discovered = 0
        binary_skipped = 0
        unsupported_types = 0
        parsing_failures = 0
        exceeding_limits = 0
        omission_reasons: dict[str, int] = {}
        omitted_sample: list[tuple[str, str]] = []

        cache_hits = 0
        cache_misses = 0

        aggregated_indicators = {
            "todo": 0,
            "fixme": 0,
            "hack": 0,
            "xxx": 0,
            "debug": 0,
        }

        def _record_omission(rel_p: str, reason_key: str, detail: str) -> None:
            omission_reasons[reason_key] = omission_reasons.get(reason_key, 0) + 1
            if len(omitted_sample) < 30:
                omitted_sample.append((rel_p, detail))

        # 1. Walk the filesystem
        for root, dirs, files in os.walk(self.project_root, topdown=True, followlinks=False):
            root_path = Path(root)

            # Check if root itself is ignored (except project_root)
            if root_path != self.project_root and self.ignore_manager.is_ignored(
                root_path, is_dir=True
            ):
                if self.explain_ignored:
                    exp = self.ignore_manager.explain_ignored(root_path, is_dir=True)
                    if exp:
                        ignored_items.append(exp)
                dirs.clear()
                continue

            # Filter subdirectories in-place so ignored directories are never entered
            kept_dirs: list[str] = []
            for d in dirs:
                d_path = root_path / d
                if self.ignore_manager.is_ignored(d_path, is_dir=True):
                    if self.explain_ignored:
                        exp = self.ignore_manager.explain_ignored(d_path, is_dir=True)
                        if exp:
                            ignored_items.append(exp)
                    _record_omission(d, "ignored_directory", "Excluded by ignore rules")
                else:
                    kept_dirs.append(d)
            dirs[:] = kept_dirs

            try:
                rel_dir = root_path.relative_to(self.project_root)
                depth = len(rel_dir.parts)
            except ValueError:
                rel_dir = Path(".")
                depth = 0

            dir_size = 0
            dir_file_count = 0

            for filename in files:
                files_discovered += 1
                file_path = root_path / filename

                try:
                    rel_file = str(file_path.relative_to(self.project_root)).replace("\\", "/")
                except ValueError:
                    rel_file = str(file_path)

                # Check ignore
                if self.ignore_manager.is_ignored(file_path, is_dir=False):
                    skipped_count += 1
                    if self.explain_ignored:
                        exp = self.ignore_manager.explain_ignored(file_path, is_dir=False)
                        if exp:
                            ignored_items.append(exp)
                    _record_omission(rel_file, "ignored_file", "Matched ignore pattern")
                    continue

                # Symlink check
                if file_path.is_symlink():
                    symlinks_count += 1
                    _record_omission(rel_file, "symlink", "Symbolic link skipped by default")
                    continue

                stat_res = get_safe_stat(file_path)
                if stat_res is None:
                    unreadable_count += 1
                    _record_omission(rel_file, "unreadable", "Permission or stat error")
                    continue

                size = stat_res.st_size
                mtime_ns = getattr(stat_res, "st_mtime_ns", int(stat_res.st_mtime * 1e9))
                mtime_str = get_modification_time(stat_res) or "Unknown"
                dir_size += size
                dir_file_count += 1

                if size == 0:
                    empty_files.append(rel_file)

                # Check incremental cache first
                cached = cache_mgr.get_cached_entry(rel_file, mtime_ns, size)
                if cached is not None:
                    cache_hits += 1
                    is_bin = bool(cached.get("is_binary", False))
                    is_src = bool(cached.get("is_source", False))
                    is_tst = bool(cached.get("is_test", False))
                    lang = cached.get("language")
                    c_lines = int(cached.get("code_lines", 0))
                    p_lines = int(cached.get("total_lines", 0))
                    m_lines = int(cached.get("comment_lines", 0))
                    b_lines = int(cached.get("blank_lines", 0))
                    inl_lines = int(cached.get("inline_comments", 0))
                    f_hash = cached.get("sha256")
                    ind = cached.get("indicators", {})
                    fc_obj = deserialize_file_complexity(cached.get("complexity"))

                    if is_bin:
                        binary_skipped += 1
                        _record_omission(
                            rel_file, "binary_file", "Binary file skipped from LOC/AST"
                        )
                    elif not lang:
                        unsupported_types += 1
                        _record_omission(
                            rel_file, "unsupported_type", "Unrecognized source extension"
                        )

                    if f_hash:
                        file_hashes[rel_file] = str(f_hash)

                    fi = FileInfo(
                        path=rel_file,
                        size_bytes=size,
                        modified_time=mtime_str,
                        is_source=is_src,
                        is_test=is_tst,
                        lines_of_code=c_lines,
                    )
                    file_infos.append(fi)

                    frec = FileRecord(
                        relative_path=rel_file,
                        name=filename,
                        extension=file_path.suffix.lower(),
                        size_bytes=size,
                        mtime=mtime_str,
                        is_source=is_src,
                        is_binary=is_bin,
                        is_test=is_tst,
                        language=lang,
                        total_lines=p_lines,
                        code_lines=c_lines,
                        comment_lines=m_lines,
                        blank_lines=b_lines,
                    )
                    file_records.append(frec)

                    if is_src and lang:
                        file_locs.append(
                            FileLOC(
                                path=rel_file,
                                language=lang,
                                total_physical=p_lines,
                                code=c_lines,
                                comments=m_lines,
                                blank=b_lines,
                                inline_comments=inl_lines,
                            )
                        )
                        for k in aggregated_indicators:
                            aggregated_indicators[k] += int(ind.get(k, 0))
                        if fc_obj is not None:
                            file_complexities.append(fc_obj)

                    cache_mgr.record_entry(rel_file, cached)
                    continue

                # Cache miss: analyze file fresh
                cache_misses += 1
                is_bin = is_binary_file(file_path)
                is_tst = "test" in rel_file.lower()

                fi = FileInfo(
                    path=rel_file,
                    size_bytes=size,
                    modified_time=mtime_str,
                    is_source=False,
                    is_test=is_tst,
                )

                lang = detect_file_language(file_path)
                p_lines = 0
                c_lines = 0
                m_lines = 0
                b_lines = 0
                inl_lines = 0
                ind_map = {"todo": 0, "fixme": 0, "hack": 0, "xxx": 0, "debug": 0}
                fc_obj = None

                if is_bin:
                    binary_skipped += 1
                    _record_omission(rel_file, "binary_file", "Binary file skipped from LOC/AST")
                elif size > MAX_LOC_FILE_SIZE_BYTES:
                    exceeding_limits += 1
                    _record_omission(
                        rel_file,
                        "exceeded_size_limit",
                        f"File size ({size} B) exceeds LOC analysis limit",
                    )
                elif lang:
                    fi.is_source = True
                    floc, ind = analyze_file_loc(file_path, lang)
                    if floc is not None:
                        floc.path = rel_file
                        file_locs.append(floc)
                        p_lines = floc.total_physical
                        c_lines = floc.code
                        m_lines = floc.comments
                        b_lines = floc.blank
                        inl_lines = floc.inline_comments
                        fi.lines_of_code = c_lines
                        ind_map = dict(ind)
                        for k, v in ind.items():
                            aggregated_indicators[k] += v
                    else:
                        parsing_failures += 1
                        _record_omission(rel_file, "read_failure", "Could not read source lines")
                else:
                    unsupported_types += 1
                    _record_omission(
                        rel_file, "unsupported_type", "Non-code or unrecognized file type"
                    )

                file_infos.append(fi)

                frec = FileRecord(
                    relative_path=rel_file,
                    name=filename,
                    extension=file_path.suffix.lower(),
                    size_bytes=size,
                    mtime=mtime_str,
                    is_source=fi.is_source,
                    is_binary=is_bin,
                    is_test=is_tst,
                    language=lang if fi.is_source else None,
                    total_lines=p_lines,
                    code_lines=c_lines,
                    comment_lines=m_lines,
                    blank_lines=b_lines,
                )
                file_records.append(frec)

                if frec.is_source and frec.language:
                    fc_obj, parse_ok = analyze_single_file_complexity(
                        self.project_root, frec, self.config
                    )
                    if not parse_ok:
                        parsing_failures += 1
                        _record_omission(
                            rel_file, "ast_parse_error", "Syntax error during AST parsing"
                        )
                    if fc_obj is not None:
                        file_complexities.append(fc_obj)

                f_hash = None
                if 0 < size <= 2 * 1024 * 1024 and not is_bin:
                    f_hash = compute_file_hash(file_path)
                    if f_hash:
                        file_hashes[rel_file] = f_hash

                cache_mgr.record_entry(
                    rel_file,
                    {
                        "mtime_ns": mtime_ns,
                        "size_bytes": size,
                        "sha256": f_hash,
                        "language": lang if fi.is_source else None,
                        "is_source": fi.is_source,
                        "is_binary": is_bin,
                        "is_test": is_tst,
                        "total_lines": p_lines,
                        "code_lines": c_lines,
                        "comment_lines": m_lines,
                        "blank_lines": b_lines,
                        "inline_comments": inl_lines,
                        "indicators": ind_map,
                        "complexity": serialize_file_complexity(fc_obj),
                    },
                )

            dir_infos.append(
                DirectoryInfo(
                    path=str(rel_dir).replace("\\", "/") if str(rel_dir) != "." else "[root]",
                    file_count=dir_file_count,
                    total_size_bytes=dir_size,
                    depth=depth,
                )
            )

        # Save incremental cache & compute diff stats
        added_cnt, mod_cnt, del_cnt, ren_cnt = cache_mgr.compute_diff_stats(
            file_hashes, cache_hits, cache_misses
        )
        cache_mgr.save()

        cache_stats = CacheStats(
            enabled=cache_mgr.enabled,
            is_incremental=bool(
                cache_mgr.enabled and cache_mgr.previous_files and not self.force_full
            ),
            hits=cache_hits,
            misses=cache_misses,
            added=added_cnt,
            modified=mod_cnt,
            deleted=del_cnt,
            renamed=ren_cnt,
            invalidated_reason=cache_mgr.invalidated_reason,
            cache_path=str(cache_mgr.cache_file) if cache_mgr.enabled else "",
        )

        # Monorepo detection (before optional package filter so workspace packages are known)
        monorepo_analysis = analyze_monorepo(self.project_root, file_records)

        # Optional package filter (--package <name>)
        if self.package_filter:
            matched_pkg = next(
                (
                    p
                    for p in monorepo_analysis.packages
                    if p.name == self.package_filter or p.path == self.package_filter
                ),
                None,
            )
            prefix = (matched_pkg.path if matched_pkg else self.package_filter).strip("/") + "/"
            file_infos = [f for f in file_infos if f.path.startswith(prefix)]
            file_records = [f for f in file_records if f.relative_path.startswith(prefix)]
            file_locs = [f for f in file_locs if f.path.startswith(prefix)]
            file_complexities = [f for f in file_complexities if f.path.startswith(prefix)]
            empty_files = [p for p in empty_files if p.startswith(prefix)]
            dir_infos = [
                d
                for d in dir_infos
                if (matched_pkg and d.path == matched_pkg.path) or d.path.startswith(prefix)
            ]

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

        # 6. Code Complexity Aggregation
        complexity_analysis = aggregate_complexity(file_complexities, self.config)

        # 7. Internal Dependency Graph & Architecture Layers
        dep_graph = analyze_dependency_graph(self.project_root, file_records)

        # 8. Technical Debt & Dead-Code Heuristics
        debt_analysis = analyze_technical_debt(
            project_root=self.project_root,
            files=file_records,
            complexity=complexity_analysis,
            dep_graph=dep_graph,
            dep_analysis=deps,
            config=self.config,
        )

        # 9. Security Hygiene Analysis
        security_analysis = analyze_security(
            project_root=self.project_root,
            files=file_records,
            dep_analysis=deps,
            config=self.config,
        )

        # 10. Project Fingerprinting
        fingerprint = analyze_project_fingerprint(
            project_root=self.project_root,
            files=file_records,
            languages=list(lang_dist.languages.values()),
            dep_analysis=deps,
        )

        # 11. Git Analytics (including churn, hotspots, branches)
        if self.enable_git:
            git_stats = analyze_git(self.project_root, complexity=complexity_analysis)
        else:
            git_stats = GitAnalytics()

        # 12. Health Analysis (9 categories + explainable deductions + recommendations)
        health = analyze_health(
            project_root=self.project_root,
            file_infos=file_infos,
            file_locs=file_locs,
            dependencies=deps,
            git=git_stats,
            indicators=aggregated_indicators,
            file_hashes=file_hashes,
            complexity=complexity_analysis,
            debt=debt_analysis,
            security=security_analysis,
            dep_graph=dep_graph,
            config=self.config,
        )

        # 13. Storage Analysis
        storage = analyze_storage(file_infos, dir_infos, ranking_limit=self.ranking_limit)

        # 14. Coverage Report
        coverage = CoverageReport(
            files_discovered=files_discovered,
            files_analyzed=len(file_locs),
            files_skipped_binary=binary_skipped,
            files_ignored=skipped_count,
            unsupported_file_types=unsupported_types,
            parsing_failures=parsing_failures,
            files_exceeding_limits=exceeding_limits,
            symlinks_skipped=symlinks_count,
            unreadable_files=unreadable_count,
            omission_reasons=omission_reasons,
            omitted_files_sample=omitted_sample,
        )

        # 15. Project Metadata
        scan_duration = time.perf_counter() - start_time
        meta = build_metadata(
            project_root=self.project_root,
            file_infos=file_infos,
            detected_ecosystems=deps.ecosystems,
            first_commit_date=git_stats.first_commit_date,
            last_commit_date=git_stats.latest_commit_date,
            scan_duration=scan_duration,
        )

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
            coverage=coverage,
            cache_stats=cache_stats,
            complexity=complexity_analysis,
            graph=dep_graph,
            debt=debt_analysis,
            security=security_analysis,
            fingerprint=fingerprint,
            monorepo=monorepo_analysis,
            ignored_items=ignored_items,
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

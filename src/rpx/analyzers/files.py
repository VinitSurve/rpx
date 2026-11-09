"""Filesystem statistics, extension aggregation, and file ranking analyzer."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from rpx.constants import (
    ASSET_EXTENSIONS,
    BINARY_EXTENSIONS,
    CONFIG_EXTENSIONS,
    DOC_EXTENSIONS,
    SOURCE_CODE_EXTENSIONS,
    TEST_INDICATORS,
)
from rpx.models import (
    DirectoryInfo,
    DirectoryStats,
    ExtensionInfo,
    FileInfo,
    FileLOC,
    FileStats,
)


def categorize_file(path: Path, is_binary: bool = False) -> str:
    """Categorize file into source, config, doc, test, asset, or binary."""
    name_lower = path.name.lower()
    suffix = path.suffix.lower()

    # Test file heuristic
    if any(ind in str(path).lower() for ind in TEST_INDICATORS):
        return "test"

    if is_binary or suffix in BINARY_EXTENSIONS:
        return "binary"

    if suffix in SOURCE_CODE_EXTENSIONS:
        return "source"

    if suffix in CONFIG_EXTENSIONS or name_lower.startswith(".env"):
        return "config"

    if suffix in DOC_EXTENSIONS or name_lower in (
        "readme",
        "license",
        "licence",
        "copying",
        "changelog",
    ):
        return "doc"

    if suffix in ASSET_EXTENSIONS:
        return "asset"

    return "other"


def summarize_files(
    file_infos: Sequence[FileInfo],
    file_locs: Sequence[FileLOC],
    empty_files: Sequence[str],
    symlinks_count: int,
    unreadable_count: int,
    skipped_count: int,
    total_directories: int,
    ranking_limit: int = 10,
) -> FileStats:
    """Aggregate file statistics, extension tables, and top file rankings."""
    stats = FileStats()
    stats.total_files = len(file_infos)
    stats.total_directories = total_directories
    stats.symlinks = symlinks_count
    stats.unreadable_files = unreadable_count
    stats.skipped_files = skipped_count
    stats.empty_files = len(empty_files)
    stats.empty_file_list = list(empty_files)[:ranking_limit]

    extensions_map: dict[str, ExtensionInfo] = {}

    for fi in file_infos:
        p = Path(fi.path)
        ext = p.suffix.lower() if p.suffix else "[no ext]"

        # Aggregate extension
        if ext not in extensions_map:
            extensions_map[ext] = ExtensionInfo(extension=ext)
        extensions_map[ext].count += 1
        extensions_map[ext].total_size_bytes += fi.size_bytes

        # Hidden file
        if p.name.startswith("."):
            stats.hidden_files += 1

        # File classification
        cat = categorize_file(p)
        if cat == "source":
            stats.source_files += 1
        elif cat == "test":
            stats.test_files += 1
            stats.source_files += 1  # tests are also source
        elif cat == "config":
            stats.config_files += 1
        elif cat == "doc":
            stats.doc_files += 1
        elif cat == "asset":
            stats.asset_files += 1
        elif cat == "binary":
            stats.binary_files += 1

        # Unusually large source files (> 500 KB)
        if cat in ("source", "test") and fi.size_bytes > 500 * 1024:
            stats.unusually_large_source_files.append(fi)

    stats.extensions = dict(
        sorted(
            extensions_map.items(),
            key=lambda item: item[1].total_size_bytes,
            reverse=True,
        )
    )

    # Top largest files
    stats.top_largest_files = sorted(file_infos, key=lambda f: f.size_bytes, reverse=True)[
        :ranking_limit
    ]

    # Top longest source files (by LOC)
    stats.top_longest_files = sorted(file_locs, key=lambda loc: loc.code, reverse=True)[
        :ranking_limit
    ]

    # Top recent files
    stats.top_recent_files = sorted(file_infos, key=lambda f: f.modified_time, reverse=True)[
        :ranking_limit
    ]

    return stats


def summarize_directories(
    dir_info_list: Sequence[DirectoryInfo],
    ranking_limit: int = 10,
) -> DirectoryStats:
    """Compute directory hierarchy metrics, nesting depth, and largest directories."""
    stats = DirectoryStats()
    if not dir_info_list:
        return stats

    deepest = max(dir_info_list, key=lambda d: d.depth)
    stats.deepest_directory = deepest.path
    stats.max_depth = deepest.depth

    stats.largest_directories = sorted(
        dir_info_list, key=lambda d: d.total_size_bytes, reverse=True
    )[:ranking_limit]

    return stats

"""Storage usage breakdown by file categories and largest storage consumers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from rpx.analyzers.files import categorize_file
from rpx.models import DirectoryInfo, FileInfo, StorageAnalytics


def analyze_storage(
    file_infos: Sequence[FileInfo],
    dir_infos: Sequence[DirectoryInfo],
    ranking_limit: int = 10,
) -> StorageAnalytics:
    """Analyze storage consumption across file categories and identify largest consumers."""
    storage = StorageAnalytics()

    for fi in file_infos:
        p = Path(fi.path)
        cat = categorize_file(p)
        storage.total_project_size_bytes += fi.size_bytes

        if cat in ("source", "test"):
            storage.source_size_bytes += fi.size_bytes
        elif cat == "doc":
            storage.docs_size_bytes += fi.size_bytes
        elif cat == "config":
            storage.config_size_bytes += fi.size_bytes
        elif cat == "asset":
            storage.assets_size_bytes += fi.size_bytes

    # Largest files
    sorted_files = sorted(file_infos, key=lambda f: f.size_bytes, reverse=True)
    storage.largest_files = [(f.path, f.size_bytes) for f in sorted_files[:ranking_limit]]

    # Largest directories
    sorted_dirs = sorted(dir_infos, key=lambda d: d.total_size_bytes, reverse=True)
    storage.largest_directories = [
        (d.path, d.total_size_bytes) for d in sorted_dirs[:ranking_limit]
    ]

    return storage

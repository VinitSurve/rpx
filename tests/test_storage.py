"""Tests for storage analytics and human-readable formatters."""

from rpx.analyzers.storage import analyze_storage
from rpx.models import DirectoryInfo, FileInfo
from rpx.utils.formatting import (
    format_bytes,
    format_number,
    format_percentage,
    render_horizontal_bar,
)


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024 * 5.5) == "5.5 MB"
    assert format_bytes(1024 * 1024 * 1024 * 2) == "2.0 GB"


def test_format_number_and_percentage():
    assert format_number(1234567) == "1,234,567"
    assert format_percentage(45.678) == "45.7%"


def test_render_horizontal_bar():
    empty_bar = render_horizontal_bar(0, width=10)
    assert empty_bar == "░" * 10
    full_bar = render_horizontal_bar(100, width=10)
    assert full_bar == "█" * 10
    half_bar = render_horizontal_bar(50, width=10)
    assert half_bar.startswith("█████")


def test_analyze_storage():
    file_infos = [
        FileInfo(path="src/app.py", size_bytes=2000, modified_time="now", is_source=True),
        FileInfo(path="README.md", size_bytes=500, modified_time="now"),
        FileInfo(path="config.json", size_bytes=300, modified_time="now"),
        FileInfo(path="icon.png", size_bytes=10000, modified_time="now"),
    ]
    dir_infos = [
        DirectoryInfo(path="src", file_count=1, total_size_bytes=2000, depth=1),
        DirectoryInfo(path="[root]", file_count=3, total_size_bytes=10800, depth=0),
    ]

    storage = analyze_storage(file_infos, dir_infos, ranking_limit=5)
    assert storage.total_project_size_bytes == 12800
    assert storage.source_size_bytes == 2000
    assert storage.docs_size_bytes == 500
    assert storage.config_size_bytes == 300
    assert storage.assets_size_bytes == 10000
    assert len(storage.largest_files) == 4
    assert storage.largest_files[0][0] == "icon.png"

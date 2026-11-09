"""Tests for filesystem inspection, categorization, and rankings."""

from pathlib import Path

from rpx.analyzers.files import categorize_file, summarize_files
from rpx.models import FileInfo, FileLOC
from rpx.utils.filesystem import compute_file_hash, is_binary_file


def test_categorize_file():
    assert categorize_file(Path("main.py")) == "source"
    assert categorize_file(Path("test_app.py")) == "test"
    assert categorize_file(Path("config.json")) == "config"
    assert categorize_file(Path("README.md")) == "doc"
    assert categorize_file(Path("logo.png")) == "asset"
    assert categorize_file(Path("lib.so")) == "binary"


def test_binary_detection(tmp_path: Path):
    text_file = tmp_path / "hello.txt"
    text_file.write_text("Hello plain text\n", encoding="utf-8")
    assert is_binary_file(text_file) is False

    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff")
    assert is_binary_file(bin_file) is True


def test_compute_file_hash(tmp_path: Path):
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    content = "identical content for hashing"
    f1.write_text(content, encoding="utf-8")
    f2.write_text(content, encoding="utf-8")

    h1 = compute_file_hash(f1)
    h2 = compute_file_hash(f2)
    assert h1 is not None
    assert h1 == h2


def test_summarize_files():
    file_infos = [
        FileInfo(
            path="a.py", size_bytes=1000, modified_time="2026-01-01 10:00:00 UTC", is_source=True
        ),
        FileInfo(
            path="b.ts", size_bytes=5000, modified_time="2026-01-02 10:00:00 UTC", is_source=True
        ),
        FileInfo(
            path="test_a.py", size_bytes=800, modified_time="2026-01-01 12:00:00 UTC", is_test=True
        ),
    ]
    file_locs = [
        FileLOC(path="a.py", language="Python", total_physical=50, code=40, comments=5, blank=5),
        FileLOC(
            path="b.ts", language="TypeScript", total_physical=200, code=180, comments=10, blank=10
        ),
    ]

    stats = summarize_files(
        file_infos=file_infos,
        file_locs=file_locs,
        empty_files=["empty.txt"],
        symlinks_count=1,
        unreadable_count=0,
        skipped_count=2,
        total_directories=3,
        ranking_limit=5,
    )

    assert stats.total_files == 3
    assert stats.empty_files == 1
    assert stats.top_largest_files[0].path == "b.ts"
    assert stats.top_longest_files[0].path == "b.ts"
    assert stats.top_recent_files[0].path == "b.ts"
    assert ".ts" in stats.extensions
    assert stats.extensions[".ts"].count == 1

"""Tests for language identification and distribution calculations."""

from pathlib import Path

from rpx.analyzers.languages import calculate_language_distribution, detect_file_language
from rpx.models import FileLOC


def test_detect_file_language():
    assert detect_file_language(Path("main.py")) == "Python"
    assert detect_file_language(Path("app.tsx")) == "TSX"
    assert detect_file_language(Path("service.go")) == "Go"
    assert detect_file_language(Path("lib.rs")) == "Rust"
    assert detect_file_language(Path("Dockerfile")) == "Dockerfile"
    assert detect_file_language(Path("Makefile")) == "Makefile"
    assert detect_file_language(Path("Gemfile")) == "Ruby"
    assert detect_file_language(Path("unknown.xyz123")) is None


def test_calculate_language_distribution():
    file_locs = [
        FileLOC(
            path="a.ts", language="TypeScript", total_physical=100, code=80, comments=10, blank=10
        ),
        FileLOC(path="b.py", language="Python", total_physical=30, code=20, comments=5, blank=5),
        FileLOC(path="c.json", language="JSON", total_physical=50, code=50, comments=0, blank=0),
    ]

    dist = calculate_language_distribution(file_locs)

    # TypeScript (80) + Python (20) = 100 programming code lines
    # TS share = 80%, Py share = 20%
    assert dist.most_used_language == "TypeScript"
    assert dist.total_detected_languages == 3
    assert dist.total_source_files == 2  # programming language source files

    ts_stat = dist.languages["TypeScript"]
    assert ts_stat.code_lines == 80
    assert ts_stat.percentage == 80.0

    py_stat = dist.languages["Python"]
    assert py_stat.code_lines == 20
    assert py_stat.percentage == 20.0

    # JSON should be marked as markup_or_data
    json_stat = dist.languages["JSON"]
    assert json_stat.is_markup_or_data is True

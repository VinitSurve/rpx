"""Tests for ProjectScanner and ignore rules."""

from pathlib import Path

import pytest

from rpx.exceptions import PathNotFoundError
from rpx.scanner import ProjectScanner


def test_scanner_on_sample_project(temp_project: Path):
    scanner = ProjectScanner(temp_project)
    result = scanner.scan()

    assert result.metadata.name in ("sample_project", "sample-project")
    assert result.files.total_files >= 5
    assert result.loc.total_physical > 0
    # Reconciliation guarantee check
    assert (
        result.loc.total_physical
        == result.loc.total_code + result.loc.total_comment + result.loc.total_blank
    )
    assert result.languages.total_detected_languages >= 2
    assert result.health.score > 0
    assert result.duration_seconds > 0


def test_scanner_ignore_rules(temp_project: Path):
    # Add a node_modules directory with dummy files
    nm = temp_project / "node_modules" / "some_pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("console.log('ignored');\n", encoding="utf-8")

    # Add custom .rpxignore
    (temp_project / ".rpxignore").write_text("custom_ignore/\n", encoding="utf-8")
    ci = temp_project / "custom_ignore"
    ci.mkdir()
    (ci / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")

    scanner = ProjectScanner(temp_project)
    result = scanner.scan()

    # Neither node_modules/some_pkg/index.js nor custom_ignore/ignored.py should be in scanned files
    scanned_paths = [f.path for f in result.files.top_largest_files]
    assert not any("node_modules" in p for p in scanned_paths)
    assert not any("custom_ignore" in p for p in scanned_paths)


def test_scanner_empty_project(tmp_path: Path):
    empty_dir = tmp_path / "empty_proj"
    empty_dir.mkdir()

    scanner = ProjectScanner(empty_dir)
    result = scanner.scan()

    assert result.files.total_files == 0
    assert result.loc.total_physical == 0
    assert result.languages.total_detected_languages == 0


def test_scanner_invalid_path():
    with pytest.raises(PathNotFoundError):
        ProjectScanner(Path("/non/existent/path/xyz_123"))

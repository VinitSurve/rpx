"""Tests for project health analyzer and completeness scoring."""

from pathlib import Path

from rpx.analyzers.health import analyze_health
from rpx.models import DependencyAnalysis, FileInfo, FileLOC, GitAnalytics


def test_health_analysis_complete_project(temp_git_project: Path):
    file_infos = [
        FileInfo(path="src/main.py", size_bytes=100, modified_time="now", is_source=True),
        FileInfo(path="tests/test_main.py", size_bytes=100, modified_time="now", is_test=True),
    ]
    file_locs = [
        FileLOC(
            path="src/main.py", language="Python", total_physical=20, code=15, comments=3, blank=2
        ),
    ]
    deps = DependencyAnalysis(manifest_files=["pyproject.toml"], lock_files=["poetry.lock"])
    git = GitAnalytics(is_git_repo=True, uncommitted_changes=False)
    indicators = {"todo": 2, "fixme": 1, "hack": 0, "xxx": 0, "debug": 1}
    hashes = {"file1.txt": "abc123hash", "file2.txt": "abc123hash"}

    findings = analyze_health(
        project_root=temp_git_project,
        file_infos=file_infos,
        file_locs=file_locs,
        dependencies=deps,
        git=git,
        indicators=indicators,
        file_hashes=hashes,
    )

    assert findings.has_readme is True
    assert findings.has_license is True
    assert findings.has_gitignore is True
    assert findings.has_tests is True
    assert findings.todo_count == 2
    assert findings.fixme_count == 1
    assert findings.potential_debug_statements_count == 1
    assert len(findings.duplicate_files) == 1
    assert findings.score >= 50
    assert "Documentation" in findings.score_breakdown
    assert "Testing" in findings.score_breakdown

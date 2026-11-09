"""Tests for directory structure tree building and terminal reporter rendering."""

from pathlib import Path

from rich.console import Console

from rpx.analyzers.structure import build_structure_tree
from rpx.models import (
    CommitInfo,
    DependencyAnalysis,
    DirectoryStats,
    FileStats,
    GitAnalytics,
    HealthFindings,
    LanguageDistribution,
    LanguageStats,
    LOCStats,
    ProjectMetadata,
    ScanResult,
    StorageAnalytics,
)
from rpx.reporters.terminal import TerminalReporter
from rpx.utils.ignore import IgnoreManager


def test_build_structure_tree(temp_project: Path):
    ignore_mgr = IgnoreManager(temp_project)
    tree = build_structure_tree(
        temp_project, ignore_manager=ignore_mgr, max_depth=2, show_sizes=True
    )
    assert tree is not None
    assert temp_project.name in str(tree.label)


def test_terminal_reporter_methods():
    console = Console(record=True, width=100)
    reporter = TerminalReporter(console=console, no_color=True)

    meta = ProjectMetadata(
        name="test-proj",
        path="/test/path",
        project_types=["Python", "TypeScript"],
        created_at="2026-01-01 00:00:00 UTC",
        last_modified="2026-01-02 00:00:00 UTC",
        total_size_bytes=10240,
        scan_duration_seconds=0.05,
        os_info="macOS Test",
        python_version="3.11.0",
        git_available=True,
        is_git_repo=True,
    )
    files = FileStats(
        total_files=5,
        total_directories=2,
        source_files=3,
        config_files=1,
        doc_files=1,
    )
    loc = LOCStats(
        total_physical=100,
        total_code=80,
        total_comment=15,
        total_blank=5,
        analyzed_files_count=3,
        avg_code_lines_per_file=26.7,
        avg_physical_lines_per_file=33.3,
        largest_file_by_loc=("main.py", 50),
        highest_comment_ratio_file=("main.py", 0.5),
    )
    lang_dist = LanguageDistribution(
        languages={
            "Python": LanguageStats(name="Python", files=2, code_lines=60, percentage=75.0),
            "TypeScript": LanguageStats(name="TypeScript", files=1, code_lines=20, percentage=25.0),
            "JSON": LanguageStats(
                name="JSON", files=1, code_lines=10, percentage=12.5, is_markup_or_data=True
            ),
        },
        most_used_language="Python",
        total_detected_languages=3,
        total_source_files=3,
        total_source_code_lines=80,
    )
    deps = DependencyAnalysis(
        ecosystems=["Python"],
        manifest_files=["pyproject.toml"],
        lock_files=["poetry.lock"],
        direct_dependencies_count=2,
        dev_dependencies_count=1,
        completeness_status="Complete & Resolved",
    )
    git = GitAnalytics(
        git_available=True,
        is_git_repo=True,
        branch="main",
        commit_hash="abc1234",
        total_commits=10,
        contributors_count=1,
        uncommitted_changes=True,
        modified_files=["app.py"],
        recent_commits=[
            CommitInfo(hash="abc1234", author="Dev", date="2026-01-01", message="Initial")
        ],
    )
    health = HealthFindings(
        has_readme=True,
        has_license=True,
        has_tests=True,
        score=90,
        score_breakdown={"Documentation": 15, "Testing": 20},
        warnings=["Test warning"],
    )
    storage = StorageAnalytics(
        total_project_size_bytes=10240,
        source_size_bytes=8000,
        largest_files=[("main.py", 5000)],
    )

    result = ScanResult(
        metadata=meta,
        files=files,
        directories=DirectoryStats(),
        loc=loc,
        languages=lang_dist,
        dependencies=deps,
        git=git,
        health=health,
        storage=storage,
        warnings=["Test warning"],
        duration_seconds=0.05,
    )

    # Render dashboard
    reporter.render_dashboard(result, ranking_limit=5, tree_depth=2, show_structure=False)
    output = console.export_text()

    assert "PROJECT METADATA" in output
    assert "LINES OF CODE (LOC) ANALYTICS" in output
    assert "PROGRAMMING LANGUAGE DISTRIBUTION" in output
    assert "DEPENDENCY & PACKAGE ANALYSIS" in output
    assert "GIT REPOSITORY ANALYTICS" in output
    assert "PROJECT HEALTH & CODE QUALITY" in output
    assert "STORAGE ANALYTICS" in output
    assert "Scan Warnings" in output

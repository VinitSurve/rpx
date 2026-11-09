"""Tests for Git repository analytics engine."""

from pathlib import Path

from rpx.analyzers.git import analyze_git


def test_git_analytics_on_repo(temp_git_project: Path):
    analytics = analyze_git(temp_git_project)
    assert analytics.git_available is True
    assert analytics.is_git_repo is True
    assert analytics.branch in ("main", "master")
    assert analytics.commit_hash is not None
    assert analytics.total_commits == 2
    assert analytics.contributors_count >= 1
    assert analytics.contributors[0][0] == "Test User"
    assert analytics.tags_count == 1
    assert len(analytics.recent_commits) == 2
    assert analytics.uncommitted_changes is False
    assert analytics.commit_activity_7d == 2


def test_git_analytics_non_git_dir(tmp_path: Path):
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()
    analytics = analyze_git(non_git)
    assert analytics.is_git_repo is False
    assert analytics.branch is None
    assert analytics.total_commits == 0

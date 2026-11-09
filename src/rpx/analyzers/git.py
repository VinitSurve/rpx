"""Git repository metrics and historical analytics engine."""

from __future__ import annotations

import os
from pathlib import Path

from rpx.models import CommitInfo, GitAnalytics
from rpx.utils.git_utils import is_git_available, is_git_repository, run_git


def analyze_git(project_root: Path) -> GitAnalytics:
    """Analyze Git repository status, history, contributors, and activity metrics."""
    analytics = GitAnalytics()
    analytics.git_available = is_git_available()

    if not analytics.git_available:
        return analytics

    analytics.is_git_repo = is_git_repository(project_root)
    if not analytics.is_git_repo:
        return analytics

    # 1. Current branch
    code, stdout, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.branch = stdout.strip()

    # 2. Current commit hash
    code, stdout, _ = run_git(["rev-parse", "--short", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.commit_hash = stdout.strip()
    else:
        # Repository may have 0 commits
        analytics.total_commits = 0
        return analytics

    # 3. Total commits count
    code, stdout, _ = run_git(["rev-list", "--count", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip().isdigit():
        analytics.total_commits = int(stdout.strip())

    # 4. First and Latest commit dates
    code, stdout, _ = run_git(
        ["log", "--reverse", "--format=%cd", "--date=iso-strict", "-1"], cwd=project_root
    )
    if code == 0 and stdout.strip():
        analytics.first_commit_date = stdout.strip().split("T")[0]

    code, stdout, _ = run_git(["log", "--format=%cd", "--date=iso-strict", "-1"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.latest_commit_date = stdout.strip().split("T")[0]

    # 5. Contributors and commit counts
    code, stdout, _ = run_git(["shortlog", "-sn", "--no-merges", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip():
        contributors = []
        for line in stdout.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2 and parts[0].isdigit():
                contributors.append((parts[1], int(parts[0])))
        analytics.contributors = contributors
        analytics.contributors_count = len(contributors)

    # 6. Status & Uncommitted changes
    code, stdout, _ = run_git(["status", "--porcelain"], cwd=project_root)
    if code == 0 and stdout:
        lines = [line for line in stdout.splitlines() if line.strip()]
        if lines:
            analytics.uncommitted_changes = True
            for line in lines:
                if len(line) < 3:
                    continue
                index_status = line[0]
                worktree_status = line[1]
                filepath = line[2:].strip()

                if index_status in ("M", "A", "D", "R"):
                    analytics.staged_files.append(filepath)

                if worktree_status == "M" or index_status == "M":
                    if filepath not in analytics.modified_files:
                        analytics.modified_files.append(filepath)
                elif worktree_status == "D" or index_status == "D":
                    analytics.deleted_files.append(filepath)
                elif worktree_status == "?" or index_status == "?":
                    analytics.untracked_files.append(filepath)
                elif index_status == "A":
                    analytics.added_files.append(filepath)

    # 7. Total branches and tags
    code, stdout, _ = run_git(["branch", "-a"], cwd=project_root)
    if code == 0 and stdout:
        analytics.total_branches = len(stdout.splitlines())

    code, stdout, _ = run_git(["tag"], cwd=project_root)
    if code == 0:
        analytics.tags_count = len(stdout.splitlines()) if stdout else 0

    # 8. Recent 5 commits
    code, stdout, _ = run_git(
        ["log", "-5", "--format=%h|%an|%ad|%s", "--date=short"], cwd=project_root
    )
    if code == 0 and stdout:
        commits = []
        for line in stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append(
                    CommitInfo(
                        hash=parts[0],
                        author=parts[1],
                        date=parts[2],
                        message=parts[3],
                    )
                )
        analytics.recent_commits = commits

    # 9. Commit activity timelines (7d, 30d, 90d)
    for days, attr in [
        (7, "commit_activity_7d"),
        (30, "commit_activity_30d"),
        (90, "commit_activity_90d"),
    ]:
        c, out, _ = run_git(
            ["rev-list", "--count", f"--since={days} days ago", "HEAD"], cwd=project_root
        )
        if c == 0 and out.strip().isdigit():
            setattr(analytics, attr, int(out.strip()))

    # 10. Repository .git directory size
    git_dir = project_root / ".git"
    if git_dir.is_dir():
        total_git_size = 0
        try:
            for root, _, files in os.walk(git_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_git_size += os.path.getsize(fp)
                    except (OSError, PermissionError):
                        pass
            analytics.repository_size_bytes = total_git_size
        except (OSError, PermissionError):
            pass

    return analytics

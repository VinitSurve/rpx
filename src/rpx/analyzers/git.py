"""Git repository metrics, file churn, hotspots, branch staleness, and historical analytics engine."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from rpx.models import (
    BranchInfo,
    CommitInfo,
    ComplexityAnalysis,
    FileChurnInfo,
    GitAnalytics,
    GitHotspot,
)
from rpx.utils.git_utils import is_git_available, is_git_repository, run_git


def _parse_iso_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def analyze_git(
    project_root: Path,
    complexity: ComplexityAnalysis | None = None,
) -> GitAnalytics:
    """Analyze Git repository status, history, contributors, churn, hotspots, and branch activity."""
    analytics = GitAnalytics()
    analytics.git_available = is_git_available()

    if not analytics.git_available:
        return analytics

    analytics.is_git_repo = is_git_repository(project_root)
    if not analytics.is_git_repo:
        return analytics

    # Check if repository is shallow
    code, stdout, _ = run_git(["rev-parse", "--is-shallow-repository"], cwd=project_root)
    if code == 0 and stdout.strip().lower() == "true":
        analytics.is_shallow = True

    # 1. Current branch
    code, stdout, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.branch = stdout.strip()

    # 2. Current commit hash
    code, stdout, _ = run_git(["rev-parse", "--short", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.commit_hash = stdout.strip()
    else:
        analytics.total_commits = 0
        return analytics

    # 3. Total commits count
    code, stdout, _ = run_git(["rev-list", "--count", "HEAD"], cwd=project_root)
    if code == 0 and stdout.strip().isdigit():
        analytics.total_commits = int(stdout.strip())

    # 4. First and Latest commit dates & commit frequency per week
    code, stdout, _ = run_git(
        ["log", "--reverse", "--format=%cd", "--date=iso-strict", "-1"], cwd=project_root
    )
    if code == 0 and stdout.strip():
        analytics.first_commit_date = stdout.strip().split("T")[0]

    code, stdout, _ = run_git(["log", "--format=%cd", "--date=iso-strict", "-1"], cwd=project_root)
    if code == 0 and stdout.strip():
        analytics.latest_commit_date = stdout.strip().split("T")[0]

    d_first = _parse_iso_date(analytics.first_commit_date)
    d_latest = _parse_iso_date(analytics.latest_commit_date)
    if d_first and d_latest and analytics.total_commits > 0:
        days_span = max(7, (d_latest - d_first).days)
        weeks_span = max(1.0, days_span / 7.0)
        analytics.commit_frequency_per_week = round(analytics.total_commits / weeks_span, 2)

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

    # 7. Total branches, branch details (staleness), and tags
    code, stdout, _ = run_git(["branch", "-a"], cwd=project_root)
    if code == 0 and stdout:
        analytics.total_branches = len([ln for ln in stdout.splitlines() if ln.strip()])

    today = date.today()
    code, stdout, _ = run_git(
        [
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short)|%(committerdate:short)|%(objectname:short)",
            "refs/heads/",
        ],
        cwd=project_root,
    )
    if code == 0 and stdout.strip():
        branch_list: list[BranchInfo] = []
        for line in stdout.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 3:
                b_name, b_date_str, b_hash = parts
                b_date = _parse_iso_date(b_date_str)
                days_since = max(0, (today - b_date).days) if b_date else 0
                is_curr = b_name == analytics.branch
                branch_list.append(
                    BranchInfo(
                        name=b_name,
                        last_commit_date=b_date_str,
                        last_commit_hash=b_hash,
                        is_current=is_curr,
                        is_stale=(days_since > 90 and not is_curr),
                        days_since_commit=days_since,
                    )
                )
        analytics.branches = branch_list

    code, stdout, _ = run_git(["tag"], cwd=project_root)
    if code == 0:
        analytics.tags_count = (
            len([ln for ln in stdout.splitlines() if ln.strip()]) if stdout else 0
        )

    # 8. Recent 10 commits
    code, stdout, _ = run_git(
        ["log", "-10", "--format=%h|%an|%ad|%s", "--date=short"], cwd=project_root
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

    # 10. Activity by month (last 200 commits)
    code, stdout, _ = run_git(
        ["log", "-n", "500", "--format=%ad", "--date=format:%Y-%m"], cwd=project_root
    )
    if code == 0 and stdout.strip():
        month_counts: dict[str, int] = {}
        for ln in stdout.splitlines():
            ym = ln.strip()
            if ym:
                month_counts[ym] = month_counts.get(ym, 0) + 1
        analytics.activity_by_month = dict(sorted(month_counts.items())[-12:])

    # 11. File modification frequency, churn (insertions + deletions), and directory change distribution
    code, stdout, _ = run_git(
        ["log", "-n", "200", "--numstat", "--format=COMMIT:%H"], cwd=project_root
    )
    if code == 0 and stdout.strip():
        file_stats: dict[str, list[int]] = {}  # path -> [commits, insertions, deletions]
        dir_changes: dict[str, int] = {}

        for ln in stdout.splitlines():
            stripped = ln.strip()
            if not stripped or stripped.startswith("COMMIT:"):
                continue
            parts = stripped.split("\t")
            if len(parts) == 3:
                ins_s, del_s, fpath = parts
                ins = int(ins_s) if ins_s.isdigit() else 0
                dels = int(del_s) if del_s.isdigit() else 0
                entry = file_stats.setdefault(fpath, [0, 0, 0])
                entry[0] += 1
                entry[1] += ins
                entry[2] += dels

                top_dir = fpath.split("/")[0] if "/" in fpath else "(root)"
                dir_changes[top_dir] = dir_changes.get(top_dir, 0) + 1

        churn_list: list[FileChurnInfo] = []
        for fpath, (c_cnt, ins_cnt, del_cnt) in file_stats.items():
            # Churn score combines commit count with log-scaled line modifications
            churn_score = c_cnt * 10 + min(500, ins_cnt + del_cnt)
            churn_list.append(
                FileChurnInfo(
                    path=fpath,
                    commits=c_cnt,
                    insertions=ins_cnt,
                    deletions=del_cnt,
                    churn_score=churn_score,
                )
            )
        churn_list.sort(key=lambda x: (x.commits, x.insertions + x.deletions), reverse=True)
        analytics.file_churn = churn_list[:25]
        analytics.change_distribution = dict(
            sorted(dir_changes.items(), key=lambda kv: kv[1], reverse=True)[:15]
        )

        # 12. Compute hotspots (high churn + complexity)
        comp_lookup: dict[str, tuple[int, int]] = {}
        if complexity:
            for fc in complexity.files:
                comp_lookup[fc.path] = (fc.max_complexity, fc.line_count)

        hotspots: list[GitHotspot] = []
        for ch in churn_list[:30]:
            max_cc, loc = comp_lookup.get(ch.path, (1, 0))
            risk = round(
                ch.commits * (1.0 + (max_cc / 5.0)) + ((ch.insertions + ch.deletions) / 50.0),
                2,
            )
            hotspots.append(
                GitHotspot(
                    path=ch.path,
                    commits=ch.commits,
                    churn_lines=ch.insertions + ch.deletions,
                    max_complexity=max_cc,
                    line_count=loc,
                    risk_score=risk,
                )
            )
        hotspots.sort(key=lambda x: x.risk_score, reverse=True)
        analytics.hotspots = hotspots[:15]

    # 13. Repository .git directory size
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

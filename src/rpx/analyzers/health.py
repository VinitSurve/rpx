"""Project health analyzer, code hygiene metrics, and completeness scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from rpx.models import DependencyAnalysis, FileInfo, FileLOC, GitAnalytics, HealthFindings


def analyze_health(
    project_root: Path,
    file_infos: Sequence[FileInfo],
    file_locs: Sequence[FileLOC],
    dependencies: DependencyAnalysis,
    git: GitAnalytics,
    indicators: dict[str, int],
    file_hashes: dict[str, str],
) -> HealthFindings:
    """Evaluate repository hygiene, presence of essential tooling, and calculate score."""
    findings = HealthFindings()

    # 1. Essential files detection
    readme_candidates = ["readme.md", "readme.rst", "readme.txt", "readme"]
    license_candidates = ["license", "licence", "copying", "license.md", "license.txt"]
    env_candidates = [".env.example", ".env.sample", ".env.template", "env.example"]

    root_files_lower = {f.name.lower(): f for f in project_root.iterdir() if f.is_file()}

    findings.has_readme = any(c in root_files_lower for c in readme_candidates)
    findings.has_license = any(c in root_files_lower for c in license_candidates)
    findings.has_gitignore = (project_root / ".gitignore").is_file()
    findings.has_env_example = any(c in root_files_lower for c in env_candidates)

    # 2. Test directory and test files
    test_dirs = ["tests", "test", "spec", "__tests__"]
    has_test_dir = any((project_root / td).is_dir() for td in test_dirs)
    test_files = [f for f in file_infos if f.is_test]
    findings.test_files_count = len(test_files)
    findings.has_tests = has_test_dir or len(test_files) > 0

    # 3. Documentation directory
    doc_dirs = ["docs", "doc", "documentation"]
    findings.has_docs = any((project_root / dd).is_dir() for dd in doc_dirs)

    # 4. CI/CD Workflows
    has_github_ci = (project_root / ".github" / "workflows").is_dir()
    has_gitlab_ci = (project_root / ".gitlab-ci.yml").is_file()
    has_jenkins = (project_root / "Jenkinsfile").is_file()
    has_circleci = (project_root / ".circleci").is_dir()
    findings.has_ci = has_github_ci or has_gitlab_ci or has_jenkins or has_circleci

    # 5. Docker
    has_dockerfile = any(c in root_files_lower for c in ["dockerfile", "containerfile"])
    has_compose = any(
        c in root_files_lower
        for c in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    )
    findings.has_docker = has_dockerfile or has_compose

    # 6. Tooling configurations (lint, format, typecheck)
    lint_configs = [
        "ruff.toml",
        ".ruff.toml",
        ".eslintrc",
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.yml",
        ".flake8",
        ".pylintrc",
        ".golangci.yml",
        ".golangci.yaml",
        "clippy.toml",
    ]
    findings.has_lint_config = any(c in root_files_lower for c in lint_configs) or (
        (project_root / "pyproject.toml").is_file()
        and "[tool.ruff" in _read_safely(project_root / "pyproject.toml")
    )

    format_configs = [
        ".prettierrc",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".editorconfig",
        "rustfmt.toml",
        ".clang-format",
    ]
    findings.has_format_config = any(c in root_files_lower for c in format_configs)

    type_configs = ["tsconfig.json", "mypy.ini", "pyrightconfig.json", "phpstan.neon"]
    findings.has_typecheck_config = any(c in root_files_lower for c in type_configs) or (
        (project_root / "pyproject.toml").is_file()
        and "[tool.mypy" in _read_safely(project_root / "pyproject.toml")
    )

    # 7. Code Indicators from LOC analysis
    findings.todo_count = indicators.get("todo", 0)
    findings.fixme_count = indicators.get("fixme", 0)
    findings.hack_count = indicators.get("hack", 0)
    findings.xxx_count = indicators.get("xxx", 0)
    findings.potential_debug_statements_count = indicators.get("debug", 0)

    # 8. Unusually long source files (> 1000 LOC) and empty source files
    for loc in file_locs:
        if loc.code > 1000:
            findings.unusually_long_files.append((loc.path, loc.code))
        if loc.total_physical == 0 or (loc.code == 0 and loc.comments == 0):
            findings.empty_source_files.append(loc.path)

    # 9. Potential duplicate files
    hash_to_path: dict[str, str] = {}
    for path_str, file_hash in file_hashes.items():
        if file_hash in hash_to_path:
            findings.duplicate_files.append((hash_to_path[file_hash], path_str))
        else:
            hash_to_path[file_hash] = path_str

    # 10. Scoring Methodology (0 - 100)
    # Documentation: up to 15
    doc_score = 0
    if findings.has_readme:
        doc_score += 10
    if findings.has_license:
        doc_score += 5

    # Testing: up to 20
    test_score = 0
    if findings.has_tests:
        test_score += 12
    if findings.test_files_count >= 3:
        test_score += 8
    elif findings.test_files_count > 0:
        test_score += 4

    # Dependency Management: up to 15
    dep_score = 0
    if dependencies.manifest_files:
        dep_score += 10
    if dependencies.lock_files:
        dep_score += 5

    # Version Control: up to 15
    vc_score = 0
    if git.is_git_repo:
        vc_score += 5
    if findings.has_gitignore:
        vc_score += 5
    if git.is_git_repo and not git.uncommitted_changes:
        vc_score += 5

    # CI/CD & Automation: up to 15
    ci_score = 15 if findings.has_ci else 0

    # Code Quality Tooling: up to 10
    tool_score = 0
    if findings.has_lint_config:
        tool_score += 4
    if findings.has_format_config:
        tool_score += 3
    if findings.has_typecheck_config:
        tool_score += 3

    # Environment & Deployment: up to 10
    env_score = 0
    if findings.has_docker:
        env_score += 5
    if findings.has_env_example or findings.has_docs:
        env_score += 5

    breakdown = {
        "Documentation": doc_score,
        "Testing": test_score,
        "Dependencies": dep_score,
        "Version Control": vc_score,
        "CI/CD": ci_score,
        "Quality Tooling": tool_score,
        "Env & Config": env_score,
    }

    findings.score = sum(breakdown.values())
    findings.score_breakdown = breakdown

    # Warnings collection
    if not findings.has_readme:
        findings.warnings.append("Missing README file.")
    if not findings.has_license:
        findings.warnings.append("Missing LICENSE file.")
    if not findings.has_tests:
        findings.warnings.append("No test suite or test files identified.")
    if dependencies.manifest_files and not dependencies.lock_files:
        findings.warnings.append("Dependency manifest found without corresponding lockfile.")
    if git.uncommitted_changes:
        findings.warnings.append("Working tree has uncommitted modifications.")
    if findings.unusually_long_files:
        findings.warnings.append(
            f"{len(findings.unusually_long_files)} source files exceed 1,000 lines of code."
        )

    return findings


def _read_safely(path: Path) -> str:
    """Safely read short text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""

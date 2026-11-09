"""Project health analyzer, 9-category explainable scoring, and actionable recommendations."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from rpx.config import DEFAULT_HEALTH_WEIGHTS, RPXConfig
from rpx.models import (
    ComplexityAnalysis,
    DebtAnalysis,
    DependencyAnalysis,
    DependencyGraph,
    FileInfo,
    FileLOC,
    GitAnalytics,
    HealthDeduction,
    HealthFindings,
    SecurityAnalysis,
)


def analyze_health(
    project_root: Path,
    file_infos: Sequence[FileInfo],
    file_locs: Sequence[FileLOC],
    dependencies: DependencyAnalysis,
    git: GitAnalytics,
    indicators: dict[str, int],
    file_hashes: dict[str, str],
    complexity: ComplexityAnalysis | None = None,
    debt: DebtAnalysis | None = None,
    security: SecurityAnalysis | None = None,
    dep_graph: DependencyGraph | None = None,
    config: RPXConfig | None = None,
) -> HealthFindings:
    """Evaluate repository quality across 9 weighted categories with explainable deductions."""
    findings = HealthFindings()
    weights = dict(config.health_weights) if config else dict(DEFAULT_HEALTH_WEIGHTS)

    # 1. Essential files detection
    readme_candidates = ["readme.md", "readme.rst", "readme.txt", "readme"]
    license_candidates = ["license", "licence", "copying", "license.md", "license.txt"]
    env_candidates = [".env.example", ".env.sample", ".env.template", "env.example"]

    try:
        root_files_lower = {f.name.lower(): f for f in project_root.iterdir() if f.is_file()}
    except OSError:
        root_files_lower = {}

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
    findings.has_docs = any((project_root / dd).is_dir() for dd in doc_dirs) or any(
        c in root_files_lower for c in ("architecture.md", "contributing.md", "changelog.md")
    )

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
    pyproject_text = (
        _read_safely(project_root / "pyproject.toml")
        if (project_root / "pyproject.toml").is_file()
        else ""
    )
    lint_configs = [
        "ruff.toml",
        ".ruff.toml",
        ".eslintrc",
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.yml",
        "eslint.config.js",
        "biome.json",
        ".flake8",
        ".pylintrc",
        ".golangci.yml",
        ".golangci.yaml",
        "clippy.toml",
    ]
    findings.has_lint_config = (
        any(c in root_files_lower for c in lint_configs) or "[tool.ruff" in pyproject_text
    )

    format_configs = [
        ".prettierrc",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".editorconfig",
        "rustfmt.toml",
        ".clang-format",
        "biome.json",
    ]
    findings.has_format_config = (
        any(c in root_files_lower for c in format_configs)
        or "[tool.ruff" in pyproject_text
        or "[tool.black" in pyproject_text
    )

    type_configs = ["tsconfig.json", "mypy.ini", "pyrightconfig.json", "phpstan.neon"]
    findings.has_typecheck_config = (
        any(c in root_files_lower for c in type_configs)
        or "[tool.mypy" in pyproject_text
        or "[tool.pyright" in pyproject_text
        or any(f.path.endswith(".py") for f in file_infos if f.is_source)
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
            hash_to_path[path_str] = file_hash
            hash_to_path[file_hash] = path_str

    # 10. 9-Category Explainable Scoring System
    deductions: list[HealthDeduction] = []
    recommendations: list[str] = []

    def _deduct(
        category: str,
        pts: int,
        reason: str,
        missing_evidence: bool,
        rec: str,
    ) -> int:
        if pts <= 0:
            return 0
        deductions.append(
            HealthDeduction(
                category=category,
                points_deducted=pts,
                reason=reason,
                is_missing_evidence=missing_evidence,
                recommendation=rec,
            )
        )
        if rec and rec not in recommendations:
            recommendations.append(rec)
        return pts

    # Category 1: Maintainability (default max 12)
    w_maint = weights.get("Maintainability", 12)
    s_maint = w_maint
    marker_total = findings.fixme_count + findings.hack_count
    if marker_total > 5:
        s_maint -= _deduct(
            "Maintainability",
            min(w_maint // 2, 4),
            f"{marker_total} FIXME/HACK debt markers present in source code (defect)",
            False,
            "Resolve high-priority FIXME and HACK markers in source files.",
        )
    if findings.potential_debug_statements_count > 0:
        s_maint -= _deduct(
            "Maintainability",
            min(3, s_maint),
            f"{findings.potential_debug_statements_count} leftover debug statements found (defect)",
            False,
            "Remove leftover debug/breakpoint statements before committing.",
        )
    if findings.unusually_long_files:
        s_maint -= _deduct(
            "Maintainability",
            min(4, s_maint),
            f"{len(findings.unusually_long_files)} source files exceed 1,000 lines of code (defect)",
            False,
            "Split source files exceeding 1,000 LOC into smaller, focused modules.",
        )

    # Category 2: Testing (default max 15)
    w_test = weights.get("Testing", 15)
    s_test = w_test
    if not findings.has_tests:
        s_test -= _deduct(
            "Testing",
            w_test,
            "No automated test directory or test files detected (missing evidence)",
            True,
            "Add a dedicated tests/ suite (e.g. pytest, vitest, or cargo test).",
        )
    elif findings.test_files_count < 3:
        s_test -= _deduct(
            "Testing",
            min(5, w_test // 3),
            f"Only {findings.test_files_count} test file(s) found (missing evidence)",
            True,
            "Expand unit and integration test coverage across core modules.",
        )

    # Category 3: Documentation (default max 12)
    w_doc = weights.get("Documentation", 12)
    s_doc = w_doc
    if not findings.has_readme:
        s_doc -= _deduct(
            "Documentation",
            min(7, w_doc),
            "Missing root README file (missing evidence)",
            True,
            "Create a comprehensive README.md describing installation and usage.",
        )
    if not findings.has_license:
        s_doc -= _deduct(
            "Documentation",
            min(3, max(0, s_doc)),
            "Missing LICENSE file (missing evidence)",
            True,
            "Add a LICENSE file to clarify repository usage rights.",
        )
    if not findings.has_docs:
        s_doc -= _deduct(
            "Documentation",
            min(2, max(0, s_doc)),
            "No docs/ directory or architecture/changelog docs detected (missing evidence)",
            True,
            "Add ARCHITECTURE.md, CONTRIBUTING.md, or a docs/ directory.",
        )

    # Category 4: Dependency Management (default max 10)
    w_dep = weights.get("Dependency Management", 10)
    s_dep = w_dep
    if not dependencies.manifest_files:
        s_dep -= _deduct(
            "Dependency Management",
            min(6, w_dep),
            "No dependency manifest (pyproject.toml, package.json, Cargo.toml, etc.) found (missing evidence)",
            True,
            "Declare project dependencies in a standard manifest file.",
        )
    elif not dependencies.lock_files and len(dependencies.dependencies) > 10:
        s_dep -= _deduct(
            "Dependency Management",
            min(3, s_dep),
            "Manifest found without a committed lockfile for deterministic builds (missing evidence)",
            True,
            "Commit a lockfile (e.g. uv.lock, poetry.lock, package-lock.json) for reproducible installs.",
        )

    # Category 5: Configuration (default max 10)
    w_cfg = weights.get("Configuration", 10)
    s_cfg = w_cfg
    if not findings.has_lint_config:
        s_cfg -= _deduct(
            "Configuration",
            min(4, s_cfg),
            "No linter configuration detected (missing evidence)",
            True,
            "Configure a linter (e.g. Ruff, ESLint, Clippy) in project configuration.",
        )
    if not findings.has_format_config:
        s_cfg -= _deduct(
            "Configuration",
            min(3, max(0, s_cfg)),
            "No code formatter or .editorconfig detected (missing evidence)",
            True,
            "Configure a code formatter (e.g. Ruff Format, Prettier, Black).",
        )

    # Category 6: Code Complexity (default max 12)
    w_comp = weights.get("Code Complexity", 12)
    s_comp = w_comp
    if complexity:
        crit_count = complexity.distribution.get("critical", 0)
        high_count = complexity.distribution.get("high", 0)
        if crit_count > 0:
            s_comp -= _deduct(
                "Code Complexity",
                min(6, s_comp),
                f"{crit_count} function(s) have critical cyclomatic complexity (defect)",
                False,
                "Refactor functions with critical cyclomatic complexity (>20) into smaller helpers.",
            )
        elif high_count > 3:
            s_comp -= _deduct(
                "Code Complexity",
                min(3, s_comp),
                f"{high_count} functions have high cyclomatic complexity (defect)",
                False,
                "Simplify high-complexity functions by extracting early returns or helper functions.",
            )

    # Category 7: Project Structure (default max 9)
    w_struct = weights.get("Project Structure", 9)
    s_struct = w_struct
    if dep_graph and dep_graph.cycles:
        s_struct -= _deduct(
            "Project Structure",
            min(5, s_struct),
            f"{len(dep_graph.cycles)} circular module dependency cycle(s) detected (defect)",
            False,
            "Break circular module imports by extracting shared types/interfaces into a base module.",
        )
    if dep_graph and dep_graph.unexpected_layer_dependencies:
        s_struct -= _deduct(
            "Project Structure",
            min(3, max(0, s_struct)),
            f"{len(dep_graph.unexpected_layer_dependencies)} architectural layer violation(s) detected (defect)",
            False,
            "Ensure lower-level modules (models/utils) do not import higher-level CLI or UI modules.",
        )

    # Category 8: CI/CD Readiness (default max 10)
    w_ci = weights.get("CI/CD Readiness", 10)
    s_ci = w_ci
    if not findings.has_ci:
        s_ci -= _deduct(
            "CI/CD Readiness",
            min(6, w_ci),
            "No CI/CD workflow configuration (.github/workflows, .gitlab-ci.yml) found (missing evidence)",
            True,
            "Add a CI workflow (e.g. GitHub Actions) to run tests and `rpx ci` on every push.",
        )

    # Category 9: Repository Hygiene (default max 10)
    w_hyg = weights.get("Repository Hygiene", 10)
    s_hyg = w_hyg
    if not git.is_git_repo:
        s_hyg -= _deduct(
            "Repository Hygiene",
            min(4, s_hyg),
            "Directory is not initialized as a Git repository (missing evidence)",
            True,
            "Initialize Git version control (`git init`).",
        )
    if not findings.has_gitignore:
        s_hyg -= _deduct(
            "Repository Hygiene",
            min(3, max(0, s_hyg)),
            "Missing .gitignore file (missing evidence)",
            True,
            "Add a .gitignore file to exclude build artifacts, caches, and virtual environments.",
        )
    if git.is_git_repo and git.uncommitted_changes:
        s_hyg -= _deduct(
            "Repository Hygiene",
            min(2, max(0, s_hyg)),
            "Working tree has uncommitted changes (defect)",
            False,
            "Commit or stash working tree modifications for a clean repository state.",
        )
    if security and security.by_severity.get("high", 0) > 0:
        s_hyg -= _deduct(
            "Repository Hygiene",
            min(5, max(0, s_hyg)),
            f"{security.by_severity['high']} high-severity security indicator(s) found (defect)",
            False,
            "Review `rpx security` findings and remove any committed .env files or hardcoded credentials.",
        )

    breakdown = {
        "Maintainability": max(0, s_maint),
        "Testing": max(0, s_test),
        "Documentation": max(0, s_doc),
        "Dependency Management": max(0, s_dep),
        "Configuration": max(0, s_cfg),
        "Code Complexity": max(0, s_comp),
        "Project Structure": max(0, s_struct),
        "CI/CD Readiness": max(0, s_ci),
        "Repository Hygiene": max(0, s_hyg),
    }

    max_scores = {
        "Maintainability": w_maint,
        "Testing": w_test,
        "Documentation": w_doc,
        "Dependency Management": w_dep,
        "Configuration": w_cfg,
        "Code Complexity": w_comp,
        "Project Structure": w_struct,
        "CI/CD Readiness": w_ci,
        "Repository Hygiene": w_hyg,
    }

    total_max = max(1, sum(max_scores.values()))
    raw_earned = sum(breakdown.values())
    findings.score = min(100, max(0, round((raw_earned / total_max) * 100)))
    findings.score_breakdown = breakdown
    findings.category_max_scores = max_scores
    findings.deductions = deductions
    findings.recommendations = recommendations

    # Legacy warnings list for backward compatibility
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

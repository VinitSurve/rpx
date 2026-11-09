# Changelog

All notable changes to the **RPX (Repository Project Explorer)** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Cross-Platform Compatibility**:
  - Enhanced creation-time resolution in `src/rpx/utils/filesystem.py` supporting Windows `st_ctime` alongside macOS/BSD `st_birthtime`.
  - Added explicit UTF-8 encoding and error replacement to Git subprocess invocations in `src/rpx/utils/git_utils.py` for Windows terminal compatibility.
- **Continuous Integration (CI)**:
  - Cross-platform multi-version matrix workflow (`.github/workflows/ci.yml`) testing Python 3.11, 3.12, and 3.13 on Ubuntu, macOS, and Windows.
  - Automated static checks: compilation check (`compileall`), Ruff lint, and Ruff format verification.
  - Test suite automation with Pytest, XML/term coverage reporting, and coverage threshold enforcement.
  - Package validation stage: clean-room wheel install, console entry point verification, and smoke tests.
- **Release Automation & PyPI Trusted Publishing**:
  - Version-tag triggered release workflow (`.github/workflows/release.yml`) with strict tag-to-metadata consistency checks.
  - Automated distribution builds (sdist and wheel), Twine metadata validation, and SHA-256 checksum generation.
  - Automated GitHub Releases with changelog-extracted release notes and attached distribution assets.
  - PyPI Trusted Publishing via GitHub OIDC (`id-token: write`).
- **Security & Vulnerability Management**:
  - CodeQL automated semantic analysis workflow (`.github/workflows/codeql.yml`).
  - Automated dependency vulnerability auditing with `pip-audit`.
  - Formal Security Policy (`SECURITY.md`) with GitHub Private Vulnerability Reporting instructions.
- **Open-Source Governance & Community**:
  - Contributor Covenant v2.1 Code of Conduct (`CODE_OF_CONDUCT.md`).
  - Getting Support guide (`SUPPORT.md`).
  - Comprehensive contributor documentation (`CONTRIBUTING.md`).
  - Standardized Pull Request template (`.github/PULL_REQUEST_TEMPLATE.md`).
  - Structured GitHub Issue Forms (`.github/ISSUE_TEMPLATE/` for bugs, features, documentation, and compatibility).
  - Repository label hierarchy (`.github/labels.yml`).
  - Branch protection and repository security guidelines (`docs/BRANCH_PROTECTION.md`).
- **Distribution Channels**:
  - Minimal multi-stage container image (`Dockerfile`, `.dockerignore`) with non-root execution and read-only volume mounts.
  - Dedicated Homebrew formula template and tap instructions (`packaging/homebrew/`).

## [1.0.0] - 2026-11-09

### Added
- **Feature Group A (Core Analysis Reliability)**:
  - Incremental scanning and local caching (`src/rpx/cache.py`, `ScanCacheManager`) keyed by project hash, config signature, and ignore signature.
  - Automatic cache invalidation when settings or ignore rules change, plus `--full` and `--no-cache` scan flags.
  - Repository snapshot store (`src/rpx/snapshots.py`) supporting `rpx snapshot [create|list|clean]`.
  - Repository comparison engine (`src/rpx/analyzers/compare.py`) supporting snapshot-to-snapshot (`rpx compare --against <id>`) and project-to-project comparisons (`rpx compare dirA dirB`).
  - Monorepo & workspace detection (`src/rpx/analyzers/monorepo.py`) across npm/pnpm/yarn workspaces, Turborepo, Nx, Lerna, Go workspaces (`go.work`), Python uv/poetry workspaces, Cargo workspaces, and Maven/Gradle multi-projects.
  - Granular package scoping with `rpx scan --package <name>`.
  - Explainable ignore engine (`src/rpx/utils/ignore.py`) supporting `.gitignore`, `.dockerignore`, `.rpxignore`, default rules, and CLI exclusions via `rpx scan --explain-ignored`.
  - Analysis coverage report (`CoverageReport`) tracking files discovered, source analyzed, skipped, ignored, unsupported, and parse failures.

- **Feature Group B (Code Intelligence)**:
  - Language-aware cyclomatic complexity analyzer (`src/rpx/analyzers/complexity.py`) using AST parsing for Python and brace/branch tracking for JS/TS/Go/Rust/Java/C/C++/C#/PHP/Kotlin/Swift/Dart.
  - Internal module dependency graph and architectural layer analysis (`src/rpx/analyzers/graph.py`) with cycle detection (canonical DFS) and layer dependency rules.
  - Consolidated technical debt analysis (`src/rpx/analyzers/debt.py`) with line-accurate marker collection (`TODO`, `FIXME`, `HACK`, `XXX`), leftover debug statements, and oversized functions.
  - Non-destructive dead-code heuristics (`DeadCodeIndicator`) identifying unused Python imports, unreferenced private functions, unreferenced internal modules, and unused declared dependencies.

- **Feature Group C (Git Intelligence)**:
  - Deep Git analytics: velocity per week, monthly commit distribution, shallow clone detection, branch staleness (>90 days), file churn (insertions + deletions), and churn × complexity engineering hotspots (`src/rpx/analyzers/git.py`).
  - Specialized Git subcommands: `rpx git contributors`, `rpx git churn`, `rpx git hotspots`, `rpx git branches`.

- **Feature Group D (Project Health & Architecture)**:
  - Project technology fingerprinting (`src/rpx/analyzers/fingerprint.py`) with evidence tracking for languages, frameworks, build tools, test runners, linters, formatters, type checkers, CI/CD, Docker, and repository conventions.
  - 9-category explainable health scoring system (`src/rpx/analyzers/health.py`) distinguishing missing evidence from defects with linked actionable recommendations.

- **Feature Group E (Security Indicators)**:
  - Local security hygiene scanner (`src/rpx/analyzers/security.py`) detecting committed `.env` files, sensitive credential files, hardcoded API keys (AWS, GitHub, OpenAI, Google, Slack, Stripe, private keys), suspicious configs (`verify=False`, `0.0.0.0`), and security anti-patterns (`eval`, `exec`, `shell=True`).
  - Mandatory secret redaction invariant: raw secret values are never printed, stored, or exported.

- **Feature Group F (Reporting & Terminal Experience)**:
  - Self-contained offline HTML reports (`src/rpx/reporters/html_report.py`) with executive dashboards, KPI tiles, and health breakdowns.
  - Mermaid flowchart exporter (`src/rpx/reporters/mermaid_report.py`) for module and workspace dependency graphs.
  - Interactive terminal explorer (`rpx explore`) for keyboard navigation across repository views.
  - Debounced watch mode (`rpx watch`) for real-time incremental re-analysis.

- **Feature Group G & H (AI-Assisted Intelligence & AI Context)**:
  - Pluggable AI provider architecture (`src/rpx/ai.py`) supporting Groq and Google Gemini with secret-redacted prompts.
  - Pluggable `CredentialProvider` interface with support for environment variables and future `keypool` CLI integration.
  - Deterministic offline architectural advisory fallback when no API keys are present.
  - AI-ready deterministic repository context exporter (`rpx context --format markdown|json`).

- **Feature Group I (CI Quality Gates)**:
  - Non-interactive CI quality gate runner (`rpx ci`) with configurable thresholds (`--min-health`, `--max-high-security`, `--max-complexity`, `--fail-on-cycles`) and deterministic exit codes.

- **Configuration & Management**:
  - Global (`~/.config/rpx/config.toml`) and per-project (`.rpx.toml`, `pyproject.toml`) configuration merging.
  - Configuration inspection, initialization, validation, and path resolution (`rpx config [show|init|check|path]`).
  - Incremental cache inspection and clearing (`rpx cache [status|clear]`).

### Changed
- Refactored `ScanResult` to house all v1.0.0 data models (`complexity`, `graph`, `debt`, `security`, `fingerprint`, `monorepo`, `coverage`, `cache_stats`) while maintaining 100% backward compatibility.
- Upgraded `src/rpx/cli.py` to route all 23 CLI commands seamlessly.
- Re-architected project health scoring from 7 to 9 weighted categories with explainable deduction breakdowns.

## [0.1.0] - 2026-11-09

### Added
- Initial release of RPX (Repository Project Explorer).
- Filesystem scanner, language-aware LOC counter, and multi-ecosystem dependency parser.
- Local Git analytics, hygiene checklist, storage analytics, and Rich terminal dashboard.
- JSON and CSV structured exports.
- Global installation via `pipx`.

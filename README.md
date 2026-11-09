# RPX | Repository Project Explorer

[![CI](https://github.com/VinitSurve/rpx/actions/workflows/ci.yml/badge.svg)](https://github.com/VinitSurve/rpx/actions/workflows/ci.yml)
[![CodeQL](https://github.com/VinitSurve/rpx/actions/workflows/codeql.yml/badge.svg)](https://github.com/VinitSurve/rpx/actions/workflows/codeql.yml)
[![GitHub Release](https://img.shields.io/github/v/release/VinitSurve/rpx?color=00D9FF&label=Release)](https://github.com/VinitSurve/rpx/releases)
[![PyPI](https://img.shields.io/pypi/v/rpx.svg?color=60A5FA)](https://pypi.org/project/rpx/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform Support](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/VinitSurve/rpx)
[![License: MIT](https://img.shields.io/badge/License-MIT-A78BFA.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Test Suite: Pytest](https://img.shields.io/badge/tests-72%20passed-success.svg)](tests/)

**RPX (Repository Project Explorer)** is a local-first, developer-centric repository intelligence CLI application. It provides deep repository insights: code composition, AST/cyclomatic complexity, internal module dependency graphs, architectural layers, technical debt, dead-code heuristics, Git velocity/churn hotspots, 9-category project health scoring, and local security hygiene with mandatory secret redaction.

RPX works entirely locally without cloud dependencies, mandatory API keys, or background telemetry.

---

## Table of Contents

- [Core Capabilities](#core-capabilities)
- [Installation Channels](#installation-channels)
  - [pipx (Recommended)](#1-pipx-recommended)
  - [uv tool](#2-uv-tool)
  - [pip](#3-pip)
  - [Docker (Optional Containerized Usage)](#4-docker-optional-containerized-usage)
  - [From Source](#5-from-source)
  - [Homebrew (Future Tap)](#6-homebrew-future-tap)
- [Quick Start & Command Reference](#quick-start--command-reference)
  - [All 23 CLI Commands](#all-23-cli-commands)
- [Feature Highlights](#feature-highlights)
  - [1. Incremental Scanning & Cache (`rpx scan`, `rpx cache`)](#1-incremental-scanning--cache-rpx-scan-rpx-cache)
  - [2. Code Complexity Analysis (`rpx complexity`)](#2-code-complexity-analysis-rpx-complexity)
  - [3. Internal Dependency Graph & Architecture (`rpx graph`)](#3-internal-dependency-graph--architecture-rpx-graph)
  - [4. Technical Debt & Dead-Code Heuristics (`rpx debt`)](#4-technical-debt--dead-code-heuristics-rpx-debt)
  - [5. Local Security Hygiene & Secret Redaction (`rpx security`)](#5-local-security-hygiene--secret-redaction-rpx-security)
  - [6. Deep Git Analytics & Engineering Hotspots (`rpx git`)](#6-deep-git-analytics--engineering-hotspots-rpx-git)
  - [7. 9-Category Explainable Project Health (`rpx health`)](#7-9-category-explainable-project-health-rpx-health)
  - [8. Monorepo & Multi-Package Workspaces (`rpx monorepo`)](#8-monorepo--multi-package-workspaces-rpx-monorepo)
  - [9. Repository Snapshots & Comparisons (`rpx snapshot`, `rpx history`, `rpx compare`)](#9-repository-snapshots--comparisons-rpx-snapshot-rpx-history-rpx-compare)
  - [10. Standalone HTML & Mermaid Reporting (`rpx report`)](#10-standalone-html--mermaid-reporting-rpx-report)
  - [11. Interactive Explorer & Live Watch Mode (`rpx explore`, `rpx watch`)](#11-interactive-explorer--live-watch-mode-rpx-explore-rpx-watch)
  - [12. AI-Ready Context & Optional LLM Advisory (`rpx context`, `rpx ai`)](#12-ai-ready-context--optional-llm-advisory-rpx-context-rpx-ai)
  - [13. CI/CD Quality Gates (`rpx ci`)](#13-cicd-quality-gates-rpx-ci)
- [Configuration (.rpx.toml)](#configuration-rpxtoml)
- [Architecture & Design](#architecture--design)
- [Local Development & Testing](#local-development--testing)
- [Community & Governance](#community--governance)
- [Privacy, Telemetry & Security](#privacy-telemetry--security)
- [License](#license)

---

## Core Capabilities

- ⚡ **Incremental Cache**: Fast sub-second re-analysis on large codebases using file-level mtime/size checks and SHA-256 digests.
- 📐 **Language-Aware AST & Cyclomatic Complexity**: Evaluates function length, nesting depth, and parameter counts for Python, TypeScript, Go, Rust, Java, C/C++, and more.
- 🕸️ **Module Dependency Graph**: Maps internal imports, computes fan-in/fan-out coupling, detects circular dependencies via DFS, and identifies architectural layer violations.
- 🧹 **Consolidated Technical Debt**: Aggregates `TODO`/`FIXME`/`HACK` comments, leftover debug statements, oversized functions, and dead-code heuristics.
- 🔒 **Security Hygiene with Mandatory Redaction**: Detects committed `.env` files, sensitive keys, and credentials without ever printing raw secret strings.
- 🌿 **Git Analytics & Hotspots**: Combines file churn (insertions/deletions) with complexity to highlight engineering risk hotspots.
- 📊 **9-Category Health Scorer**: Evaluates Maintainability, Testing, Documentation, Dependencies, Configuration, Complexity, Structure, CI/CD, and Hygiene with explainable deductions.
- 🏢 **Monorepo Detection**: Analyzes Turborepo, Nx, Lerna, npm/pnpm/yarn workspaces, Cargo, uv/poetry, and Go workspaces without double-counting.
- 📄 **Multi-Format Exports**: JSON, CSV, standalone offline HTML dashboards, and Mermaid flowcharts.
- 🤖 **AI-Ready Context & Optional Synthesis**: Generates deterministic, sanitized context for coding agents, with optional LLM advisory via Groq or Google Gemini.

---

## Installation Channels

### 1. pipx (Recommended)
`pipx` installs RPX into an isolated environment while exposing the `rpx` executable globally:

```bash
pipx install rpx
```

### 2. uv tool
For ultra-fast installation using Astral's `uv`:

```bash
uv tool install rpx
```

### 3. pip
Standard installation into your active Python environment:

```bash
pip install rpx
```

### 4. Docker (Optional Containerized Usage)
For isolated container execution without a local Python runtime:

```bash
# Build the minimal container image
docker build -t rpx:latest .

# Run read-only scan against the current project
docker run --rm -v "$PWD:/workspace:ro" rpx:latest scan
```

> **Note**: Native installation via `pipx` is recommended for optimal terminal dashboard rendering and direct filesystem access.

### 5. From Source

```bash
git clone https://github.com/VinitSurve/rpx.git
cd rpx
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 6. Homebrew (Future Tap)
To install from the dedicated Homebrew tap once configured:

```bash
brew tap VinitSurve/tap
brew install rpx
```

*(See [packaging/homebrew/README.md](packaging/homebrew/README.md) for tap maintainer instructions.)*

---

## Quick Start & Command Reference

Run `rpx` inside any repository for the comprehensive visual terminal dashboard:

```bash
rpx
```

### All 23 CLI Commands

| Command | Purpose | Common Flags |
|---|---|---|
| `rpx` / `rpx scan` | Full repository scan & visual dashboard | `--full`, `--no-cache`, `--package <name>`, `--explain-ignored` |
| `rpx summary` | Concise executive summary | `--json` |
| `rpx tree` | Render directory structure tree | `--depth <n>` |
| `rpx languages` | Language distribution & lines of code | `--json`, `--csv` |
| `rpx dependencies` | Declared, locked, and installed dependencies | `--json`, `--csv` |
| `rpx complexity` | AST & cyclomatic complexity analysis | `--threshold [medium\|high\|critical]`, `--file <path>` |
| `rpx graph` | Module import graph & architectural layers | `--format [terminal\|json\|mermaid]`, `--output <path>` |
| `rpx debt` | Technical debt & dead-code heuristics | `--severity [high\|medium]`, `--category <cat>`, `--export json` |
| `rpx security` | Local security hygiene & redacted secrets | `--severity high`, `--csv` |
| `rpx git` | Local Git status, velocity & recent commits | `--json` |
| `rpx git contributors` | Contributor rankings & commit volume | — |
| `rpx git churn` | File modification frequency & line churn | — |
| `rpx git hotspots` | Engineering hotspots (churn × complexity) | — |
| `rpx git branches` | Branch details & staleness indicator (>90d) | — |
| `rpx health` | 9-category explainable health score & tips | `--json` |
| `rpx monorepo` | Multi-package workspace analysis & boundaries | `--json` |
| `rpx snapshot` | Create, list, or clean repository snapshots | `create [--label]`, `list [--limit]`, `clean [--keep]` |
| `rpx history` | View repository metric evolution over time | `--limit <n>`, `--json` |
| `rpx compare` | Compare snapshots or two project directories | `--against <id>`, `rpx compare dirA dirB`, `--format csv` |
| `rpx report` | Export standalone reports | `--format [html\|json\|csv\|mermaid]`, `--output <path>` |
| `rpx explore` | Interactive keyboard terminal explorer | `--non-interactive` |
| `rpx watch` | Debounced incremental file watcher | `--interval <sec>`, `--debounce <sec>` |
| `rpx context` | Deterministic, secret-free AI agent context | `--format [markdown\|json]`, `--max-chars <n>` |
| `rpx ci` | Non-interactive CI quality gates | `--min-health <n>`, `--max-high-security <n>`, `--fail-on-cycles` |
| `rpx cache` | Incremental scan cache management | `status`, `clear [--all]` |
| `rpx config` | Inspect, validate, and initialize TOML config | `show`, `init`, `check`, `path` |
| `rpx ai` | Optional AI architectural advisory (Groq/Gemini) | `--provider [auto\|groq\|gemini]`, `--focus architecture`, `--offline` |

---

## Feature Highlights

### 1. Incremental Scanning & Cache (`rpx scan`, `rpx cache`)
RPX stores a lightweight scan cache under `~/.cache/rpx/scan_cache/`. Unmodified files reuse previous line counts and AST complexity metrics. The cache is automatically invalidated when `.rpx.toml`, ignore rules, or analysis settings change.
- Force a complete scan: `rpx scan --full`
- Disable caching: `rpx scan --no-cache`
- Inspect cache status: `rpx cache status`
- Clear cache: `rpx cache clear`

### 2. Code Complexity Analysis (`rpx complexity`)
Uses Python's native `ast` module to count decision points (`If`, `For`, `While`, `ExceptHandler`, `With`, `Assert`, `Match`, comprehensions, `BoolOp`) and lexical brace/branch analysis for non-Python languages:
```bash
rpx complexity --threshold high
rpx complexity --file src/rpx/scanner.py
```

### 3. Internal Dependency Graph & Architecture (`rpx graph`)
Inspects internal module dependencies, infers architectural layers (`tests`, `cli`, `presentation`, `core`, `analyzers`, `models`, `utils`), checks for illegal cross-layer imports, and finds circular imports:
```bash
rpx graph --format mermaid --output graph.mmd
```

### 4. Technical Debt & Dead-Code Heuristics (`rpx debt`)
Tracks debt markers (`TODO`, `FIXME`, `HACK`, `XXX`), leftover debug statements (`pdb.set_trace()`, `debugger`), and non-destructive dead-code heuristics (unused Python imports, unreferenced private helpers, unreferenced internal modules, unused declared dependencies):
```bash
rpx debt --severity high --export json
```

### 5. Local Security Hygiene & Secret Redaction (`rpx security`)
Scans for committed `.env` files, sensitive private keys, dangerous patterns (`eval()`, `exec()`, `shell=True`), and hardcoded secrets (AWS, GitHub, OpenAI, Google, Slack, Stripe).
- **Mandatory Redaction**: Raw secret text is **never** printed to the console or written to export files. Matches are displayed as `sk-proj...***REDACTED***...d1`.

### 6. Deep Git Analytics & Engineering Hotspots (`rpx git`)
- Velocity: commits per week and monthly breakdown.
- File Churn: insertions + deletions per file.
- Engineering Hotspots: identifies files with high modification churn AND high cyclomatic complexity.
- Stale Branches: flags branches with no commits in >90 days.

### 7. 9-Category Explainable Project Health (`rpx health`)
Evaluates: Maintainability, Testing, Documentation, Dependency Management, Configuration, Code Complexity, Project Structure, CI/CD Readiness, and Repository Hygiene.
- Deductions distinguish **Missing Evidence** (e.g. no tests found) from **Defects** (e.g. circular dependency cycle detected).

### 8. Monorepo & Multi-Package Workspaces (`rpx monorepo`)
Detects workspace configurations across npm/pnpm/yarn, Turborepo, Nx, Lerna, Go workspaces (`go.work`), Python uv/poetry workspaces, Cargo workspaces, and Gradle/Maven multi-projects.
- Scope scan to one package: `rpx scan --package @acme/ui`

### 9. Repository Snapshots & Comparisons (`rpx snapshot`, `rpx history`, `rpx compare`)
Save snapshots locally to track how code and debt evolve over time:
```bash
rpx snapshot create --label v1.0.0
rpx history
rpx compare --against v1.0.0
rpx compare ./project-a ./project-b --format csv
```

### 10. Standalone HTML & Mermaid Reporting (`rpx report`)
Generate zero-dependency, self-contained HTML dashboards with KPI cards, health bars, and complexity tables:
```bash
rpx report --format html --output report.html
```

### 11. Interactive Explorer & Live Watch Mode (`rpx explore`, `rpx watch`)
- Keyboard navigation across all repository dimensions: `rpx explore`
- Real-time debounced file monitoring with automatic re-analysis: `rpx watch`

### 12. AI-Ready Context & Optional LLM Advisory (`rpx context`, `rpx ai`)
- Generate size-bounded, secret-sanitized repository briefs for coding agents:
  ```bash
  rpx context --format markdown > context.md
  rpx context --format json
  ```
- Optional LLM advisory using Groq or Google Gemini:
  ```bash
  export GROQ_API_KEY="gsk_..."
  rpx ai --provider groq --focus architecture
  # Fully offline deterministic fallback:
  rpx ai --offline
  ```

### 13. CI/CD Quality Gates (`rpx ci`)
Non-interactive quality gate evaluation with deterministic exit codes:
```bash
rpx ci --min-health 80 --max-high-security 0 --fail-on-cycles
```

---

## Configuration (.rpx.toml)

Initialize a configuration file with `rpx config init`. You can also configure RPX globally at `~/.config/rpx/config.toml` or in `pyproject.toml` under `[tool.rpx]`:

```toml
[rpx]
ranking_limit = 10
max_depth = 3
exclude = ["vendor", "docs/_build", "*.log"]
include_ignored = false
no_git = false
no_deps = false
no_color = false
use_cache = true
security_enabled = true
ai_provider = "auto"

[rpx.complexity]
low_max = 5
medium_max = 10
high_max = 20
max_function_lines = 60
max_nesting_depth = 4

[rpx.health_weights]
"Maintainability" = 12
"Testing" = 15
"Documentation" = 12
"Dependency Management" = 10
"Configuration" = 10
"Code Complexity" = 12
"Project Structure" = 9
"CI/CD Readiness" = 10
"Repository Hygiene" = 10
```

Validate your configuration anytime with `rpx config check`.

---

## Architecture & Design

See [ARCHITECTURE.md](ARCHITECTURE.md) for the layered design, internal data models, cache protocol, and analyzer pipelines.

---

## Local Development & Testing

```bash
# Clone the repository
git clone https://github.com/VinitSurve/rpx.git
cd rpx

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests and coverage
pytest --cov=rpx --cov-report=term-missing

# Lint & format
ruff check .
ruff format --check .

# Build distributions
python -m build
```

---

## Community & Governance

- [Contributing Guidelines](CONTRIBUTING.md) — Environment setup, code style, and pull request workflows.
- [Code of Conduct](CODE_OF_CONDUCT.md) — Community standards adapted from Contributor Covenant v2.1.
- [Security Policy](SECURITY.md) — Vulnerability reporting and responsible disclosure.
- [Getting Support](SUPPORT.md) — How to report bugs and propose features.
- [Changelog](CHANGELOG.md) — Version release history and updates.

---

## Privacy, Telemetry & Security

- **100% Local**: All analysis runs locally on your machine.
- **Zero Telemetry**: No tracking, phone-home requests, or analytics.
- **No Code Execution**: RPX inspects source code statically via AST and tokens; it never executes project code or dependencies.
- **Mandatory Secret Redaction**: Detected keys and passwords are redacted immediately. Raw secrets are never stored, printed, or sent over any connection.
- **Safe Read-Only Operations**: RPX never modifies files in analyzed repositories.

---

## License

RPX is licensed under the [MIT License](LICENSE).

# RPX | Repository Project Explorer

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**RPX (Repository Project Explorer)** is a comprehensive, local-first developer utility for software project analytics. It analyzes any codebase—from small single-file scripts to multi-language enterprise monorepos—and generates a visually stunning, information-dense terminal dashboard and exportable reports.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Global Installation via pipx (Recommended)](#global-installation-via-pipx-recommended)
  - [Development Installation](#development-installation)
- [Quick Start & Usage](#quick-start--usage)
- [CLI Options & Flags](#cli-options--flags)
- [Terminal Dashboard Overview](#terminal-dashboard-overview)
- [Supported Programming Languages](#supported-programming-languages)
- [Supported Dependency Ecosystems](#supported-dependency-ecosystems)
- [Analytical Methodologies](#analytical-methodologies)
  - [Language-Aware LOC Counting](#language-aware-loc-counting)
  - [Dependencies: Declared vs Locked vs Installed](#dependencies-declared-vs-locked-vs-installed)
  - [Project Health & Completeness Scoring](#project-health--completeness-scoring)
  - [Ignore Rules & Scanning Safety](#ignore-rules--scanning-safety)
- [Configuration (.rpx.toml)](#configuration-rpxtoml)
- [Export System (JSON & CSV)](#export-system-json--csv)
- [Architecture Overview](#architecture-overview)
- [Development & Testing](#development--testing)
- [Privacy, Telemetry & Security](#privacy-telemetry--security)
- [Troubleshooting & Known Limitations](#troubleshooting--known-limitations)

---

## Features

- ⚡ **Blazing Fast Scanning**: Traverses projects using optimized directory pruning, avoiding scanning deep vendor directories like `node_modules` and `.venv`.
- 📊 **Accurate LOC Analysis**: Language-aware state-machine tokenization for 40+ languages. Enforces mathematical reconciliation (`Total Physical = Code + Comments + Blank`).
- 🎨 **Rich Terminal Dashboard**: Built with Rich panels, tables, and horizontal block progress bars adhering to a consistent cyan/purple/blue/green theme.
- 📦 **Multi-Ecosystem Dependencies**: Detects declared, locked, installed, and missing dependencies across JavaScript/TypeScript, Python, Rust, Go, Java, PHP, Ruby, .NET, Dart, and Swift.
- 🌿 **Local Git Analytics**: Extracts branch, commit hash, commit volume, contributor rankings, dirty worktree status, recent commits, and 7/30/90-day velocity without network requests.
- 🛡️ **Project Health & Hygiene**: Detects missing README, LICENSE, `.gitignore`, tests, CI/CD, Dockerfiles, and code indicators (TODO, FIXME, HACK, XXX, stray debug statements) with transparent scoring (0–100).
- 🌳 **Project Structure Explorer**: Generates nested directory trees with file-size annotations and customizable depth.
- 💾 **Storage Analytics**: Breaks down disk consumption into Source, Documentation, Configuration, and Assets, while spotting unusually large files.
- 📤 **Structured Exports**: Exports complete schema-versioned JSON reports and tabular CSVs for file-level or language statistics.
- 🔒 **Zero Telemetry & Safe**: 100% local analysis. Never executes project code, never reads environment secrets, and never makes network calls.

---

## Requirements

- **Operating System**: macOS (Apple Silicon or Intel), Linux, or Windows.
- **Python**: Version 3.11 or higher.
- **Git** (optional): Installed and available on `PATH` for Git repository analytics.

---

## Installation

### Global Installation via pipx (Recommended)

`pipx` installs CLI tools in isolated environments while making their binaries accessible globally:

```bash
# 1. Install pipx if not already installed (e.g. via Homebrew on macOS)
brew install pipx
pipx ensurepath

# 2. Install RPX from the repository directory
cd /path/to/RPX
pipx install .

# 3. Verify installation
rpx --version
which rpx
```

### Development Installation

To install in editable mode for development:

```bash
git clone https://github.com/vinit/rpx.git
cd rpx
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

RPX can also be invoked as a module without global installation:

```bash
python3 -m rpx --help
```

---

## Quick Start & Usage

Run `rpx` inside any project folder:

```bash
# Scan current directory and display full visual dashboard
rpx

# Scan an explicit directory path
rpx /Users/username/Projects/my-app

# Inspect only specific sections
rpx --loc
rpx --languages
rpx --deps
rpx --git
rpx --health
rpx --tree --depth 2
rpx --storage

# Export structured reports
rpx --json > report.json
rpx --csv --save
rpx --output audit.json
```

---

## CLI Options & Flags

```text
Usage: rpx [OPTIONS] [PROJECT_PATH]
       rpx config [show|init] [PROJECT_PATH]

Arguments:
  [PROJECT_PATH]                  Path to project directory (default: current directory).

Display Options:
  --files                         Show only file & directory statistics.
  --loc                           Show only lines of code analytics.
  --languages                     Show only programming language distribution.
  --deps                          Show only dependency analytics.
  --git                           Show only Git analytics.
  --health                        Show only project health and quality findings.
  --tree                          Show directory structure tree.
  --storage                       Show storage analytics.

Export Options:
  --json                          Export structured report as JSON to stdout or file.
  --csv                           Export statistics as CSV.
  --save                          Save report to default file (rpx-report.json or rpx-report.csv).
  --output, -o PATH               Save report to specified file path.
  --force, -f                     Overwrite existing output file without confirmation.

Filtering & Tuning:
  --top INTEGER                   Number of items to show in rankings (default: 10).
  --depth, -d INTEGER             Maximum directory tree depth (default: 3).
  --exclude, -e PATTERN           Additional patterns to exclude (can be repeated).
  --include-ignored               Include normally ignored directories (increases scan time).
  --no-git                        Skip Git analytics even if Git is available.
  --no-deps                       Skip dependency manifest parsing.
  --no-color                      Disable colored terminal output (also respects NO_COLOR=1).
  --quiet, -q                     Suppress visual dashboard and print minimal output.
  --verbose, -v                   Verbose error logging and tracebacks.
  --version, -V                   Show RPX version and exit.
  --help, -h                      Show help message and exit.

Utility Commands:
  config show [PATH]              Display active configuration settings for project.
  config init [PATH]              Create a default .rpx.toml configuration file.
```

---

## Terminal Dashboard Overview

When invoked without filtering flags, RPX renders a comprehensive terminal interface divided into visually distinct panels:

1. **ASCII Header & Metadata**: Displays project name, absolute location, detected ecosystem, birth time, modification date, OS, Python runtime, and scan duration.
2. **Key Metric Cards**: 8 high-density summary tiles (Total Files, Source Files, Directories, Total Lines, Code Lines, Languages, Declared Dependencies, Project Size).
3. **Lines of Code (LOC) Analytics**: Precise count of physical lines, executable code, comments/docs, blank lines, and inline comments, alongside average lines per file and verification status.
4. **Programming Language Distribution**: Horizontal progress bar charts with percentage of code lines (distinguishing programming code from markup/data).
5. **File & Directory Statistics**: Category breakdowns (source, config, doc, test, asset, binary, empty, hidden) and Top Extension table.
6. **Dependency & Package Analysis**: Declared direct and dev dependencies, locked transitive count, verified installed packages, and missing dependencies list.
7. **Git Repository Analytics**: Current branch, HEAD commit hash, commit count, contributor rankings, working tree status (staged/modified/untracked), 7/30/90-day velocity, and the 5 most recent commits.
8. **Project Health & Code Quality**: Checklist of essential project files, counts of code indicators (TODO, FIXME, HACK, XXX, potential debug statements), duplicate file detection, and a transparent completeness score (0–100).
9. **Storage Analytics**: Space consumption by file category and a table of the top largest files on disk.

---

## Supported Programming Languages

RPX includes built-in lexical rules for 40+ programming, markup, and configuration languages:

| Language | Extensions / Markers | Single Comments | Multi-line Delimiters |
|---|---|---|---|
| **Python** | `.py`, `.pyw` | `#` | `"""..."""`, `'''...'''` |
| **JavaScript / TypeScript** | `.js`, `.mjs`, `.cjs`, `.ts`, `.mts`, `.cts` | `//` | `/*...*/` |
| **JSX / TSX** | `.jsx`, `.tsx` | `//` | `/*...*/`, `{/*...*/}` |
| **Rust** | `.rs` | `//`, `///`, `//!` | `/*...*/` |
| **Go** | `.go` | `//` | `/*...*/` |
| **C / C++** | `.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.cxx` | `//` | `/*...*/` |
| **Java / Kotlin** | `.java`, `.kt`, `.kts` | `//` | `/*...*/` |
| **C#** | `.cs` | `//` | `/*...*/` |
| **Swift / Objective-C** | `.swift`, `.m`, `.mm` | `//` | `/*...*/` |
| **PHP** | `.php` | `//`, `#` | `/*...*/` |
| **Ruby** | `.rb`, `Gemfile`, `Rakefile` | `#` | `=begin...=end` |
| **Dart** | `.dart` | `//` | `/*...*/` |
| **Scala** | `.scala`, `.sc` | `//` | `/*...*/` |
| **R** | `.r` | `#` | — |
| **SQL** | `.sql` | `--` | `/*...*/` |
| **Shell / Bash / Zsh** | `.sh`, `.bash`, `.zsh`, `.fish` | `#` | — |
| **PowerShell** | `.ps1`, `.psm1` | `#` | `<#...#>` |
| **HTML / XML** | `.html`, `.htm`, `.xml` | — | `<!--...-->` |
| **CSS / SCSS / Less** | `.css`, `.scss`, `.less` | `//` (SCSS/Less) | `/*...*/` |
| **Vue / Svelte** | `.vue`, `.svelte` | `//` | `<!--...-->`, `/*...*/` |
| **Lua** | `.lua` | `--` | `--[[...]]` |
| **Perl** | `.pl`, `.pm` | `#` | `=pod...=cut` |
| **Elixir / Erlang** | `.ex`, `.exs`, `.erl`, `.hrl` | `#` / `%` | `"""..."""` |
| **Haskell** | `.hs`, `.lhs` | `--` | `{-...-}` |
| **Clojure / Lisp** | `.clj`, `.cljs`, `.cljc`, `.edn` | `;` | — |
| **Assembly** | `.asm`, `.s` | `;`, `#` | — |
| **Dockerfile / Makefile** | `Dockerfile`, `Makefile` | `#` | — |
| **YAML / TOML / JSON** | `.yaml`, `.yml`, `.toml`, `.json` | `#` (YAML/TOML) | — |
| **GraphQL** | `.graphql`, `.gql` | `#` | `"""..."""` |

---

## Supported Dependency Ecosystems

RPX inspects package manifests and lockfiles across modern language ecosystems:

- **JavaScript / TypeScript (npm, Yarn, pnpm, Bun)**:
  - Manifests: `package.json` (direct, dev, peer, optional).
  - Lockfiles: `package-lock.json` (v1/v2/v3), `yarn.lock`, `pnpm-lock.yaml`, `bun.lock`, `bun.lockb`.
  - Installed packages: Local `node_modules/` verification.
- **Python (PyPI)**:
  - Manifests: `pyproject.toml` (PEP 621, Poetry, Flit), `requirements.txt`, `requirements-dev.txt`, `Pipfile`.
  - Lockfiles: `poetry.lock`, `uv.lock`, `Pipfile.lock`.
  - Installed packages: Local `.venv`, `venv`, or `env` directory inspection.
- **Rust (Cargo)**:
  - Manifests: `Cargo.toml`.
  - Lockfiles: `Cargo.lock`.
- **Go (Modules)**:
  - Manifests: `go.mod`.
  - Lockfiles: `go.sum`.
- **PHP (Composer)**:
  - Manifests: `composer.json`.
  - Lockfiles: `composer.lock`.
  - Installed packages: Local `vendor/` inspection.
- **Ruby (RubyGems / Bundler)**:
  - Manifests: `Gemfile`.
  - Lockfiles: `Gemfile.lock`.
- **Java / Kotlin (Maven / Gradle)**:
  - Manifests: `pom.xml`, `build.gradle`, `build.gradle.kts`.
- **.NET (NuGet)**:
  - Manifests: `*.csproj`.
- **Dart / Flutter (Pub)**:
  - Manifests: `pubspec.yaml`, `pubspec.lock`.
- **Swift (SwiftPM)**:
  - Manifests: `Package.swift`, `Package.resolved`.

---

## Analytical Methodologies

### Language-Aware LOC Counting

Rather than naive keyword matching, RPX uses state-machine scanning on every line:
1. **Physical Line**: Every line ending with `\n` or the EOF terminal line.
2. **Blank Line**: A line containing only whitespace.
3. **Comment Line**: A line containing only a single-line comment, a multi-line comment segment, a docstring, or a shebang (`#!`).
4. **Code Line**: A line containing executable syntax or non-comment statements.
5. **Inline Comment**: Tracked when executable code and comments appear on the same physical line (counted as a Code line for reconciliation).

**Mathematical Reconciliation**:
$$\text{Total Physical Lines} = \text{Code Lines} + \text{Comment Lines} + \text{Blank Lines}$$

### Dependencies: Declared vs Locked vs Installed

RPX explicitly distinguishes between three independent states:
- **Declared Dependencies**: What the developer requested in manifest files (e.g. `fastapi>=0.100.0` or `express: ^4.18.2`).
- **Locked Dependencies**: Pinned transitive versions captured in a lockfile (e.g. `poetry.lock` or `package-lock.json`).
- **Installed Dependencies**: Packages physically present in a local project environment (`node_modules/` or `.venv/`).
- **Missing Dependencies**: Declared packages that cannot be verified in either lockfiles or local installations.

### Project Health & Completeness Scoring

RPX computes a transparent heuristic Completeness Score from **0 to 100**:
- **Documentation (15 pts)**: README (10 pts), License (5 pts).
- **Testing (20 pts)**: Test suite present (12 pts), Multiple test files (up to 8 pts).
- **Dependencies (15 pts)**: Manifest present (10 pts), Lockfile pinned (5 pts).
- **Version Control (15 pts)**: Git repository (5 pts), `.gitignore` present (5 pts), Clean worktree (5 pts).
- **CI/CD Automation (15 pts)**: Workflows found (`.github/workflows`, `.gitlab-ci.yml`, etc.) (15 pts).
- **Quality Tooling (10 pts)**: Linter configuration (4 pts), Formatter (3 pts), Type-checker (3 pts).
- **Config & Deploy (10 pts)**: Docker config (5 pts), `.env.example` or documentation (5 pts).

> **Disclaimer**: The health score is a heuristic completeness metric reflecting repository tooling and hygiene. It does not measure runtime correctness or vulnerability-free security.

### Ignore Rules & Scanning Safety

By default, RPX ignores common build artifacts, package managers, and large virtual environments:
- `.git/`, `node_modules/`, `.venv/`, `venv/`, `env/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`, `target/`, `vendor/`, `Pods/`, `DerivedData/`, `.gradle/`, `.idea/`, `.vscode/`, `.DS_Store`.

RPX layers ignore rules in order:
1. **Built-in default exclusions**.
2. **`.gitignore`** in the project root.
3. **`.rpxignore`** in the project root (supports standard GitWildMatch patterns).
4. **CLI `--exclude` flags**.

RPX does **not** ignore useful hidden files such as `.gitignore`, `.env.example`, `.github/`, or configuration dotfiles.

---

## Configuration (.rpx.toml)

RPX supports a persistent configuration file. Generate one using:

```bash
rpx config init
```

This creates `.rpx.toml` in your project root:

```toml
[rpx]
# Maximum items shown in rankings
ranking_limit = 10

# Maximum directory tree nesting depth
max_depth = 3

# Additional directories or files to exclude
exclude = [
    "vendor",
    "docs/_build",
    "*.log"
]

# Include directories normally ignored by default
include_ignored = false

# Disable Git analytics
no_git = false

# Disable dependency manifest parsing
no_deps = false

# Disable colored terminal output
no_color = false
```

Inspect active configuration anytime with:

```bash
rpx config show
```

---

## Export System (JSON & CSV)

### JSON Export

Export structured data adhering to RPX Schema `1.0.0`:

```bash
# Print to stdout
rpx --json

# Save to file
rpx --output audit.json
```

Sample JSON structure:

```json
{
  "schema_version": "1.0.0",
  "app": {
    "name": "RPX",
    "version": "0.1.0"
  },
  "metadata": {
    "name": "sample-project",
    "path": "/Users/user/Projects/sample-project",
    "project_types": ["Python"],
    "created_at": "2026-01-01 12:00:00 UTC",
    "total_size_bytes": 175200,
    "scan_duration_seconds": 0.042
  },
  "loc": {
    "total_physical": 4800,
    "total_code": 3690,
    "total_comment": 395,
    "total_blank": 715
  },
  "health": {
    "score": 85,
    "score_breakdown": {
      "Documentation": 15,
      "Testing": 20,
      "Dependencies": 15,
      "Version Control": 15,
      "CI/CD": 0,
      "Quality Tooling": 10,
      "Env & Config": 10
    }
  }
}
```

### CSV Export

Export tabular metrics to CSV:

```bash
# Export file-level LOC statistics
rpx --csv --output files.csv

# Export language breakdown
rpx --csv --languages --output languages.csv

# Export dependencies list
rpx --csv --deps --output dependencies.csv
```

---

## Architecture Overview

```text
rpx/
├── pyproject.toml               # Package build metadata & dependencies
├── README.md                    # Documentation
├── LICENSE                      # MIT License
├── CHANGELOG.md                 # Version history
├── .gitignore                   # Git ignore patterns
│
├── src/rpx/
│   ├── __init__.py              # Version & package metadata
│   ├── __main__.py              # Python module invocation point
│   ├── cli.py                   # Typer CLI application & command dispatch
│   ├── config.py                # TOML configuration loader & generator
│   ├── constants.py             # Colors, file categories, comment syntax rules
│   ├── exceptions.py            # RPX domain exceptions
│   ├── models.py                # Typed dataclasses for metrics & schema
│   ├── scanner.py               # Recursive traversal orchestrator
│   │
│   ├── analyzers/               # Analytical engines
│   │   ├── metadata.py          # Project root detection & environment stats
│   │   ├── files.py             # Categorization, extensions & file rankings
│   │   ├── loc.py               # Language-aware LOC & comment analyzer
│   │   ├── languages.py         # Language distribution & progress bars
│   │   ├── dependencies.py      # Dependency discovery orchestrator
│   │   ├── git.py               # Local Git CLI analytics
│   │   ├── health.py            # Hygiene checklist & completeness scoring
│   │   ├── storage.py           # Disk storage categorization
│   │   └── structure.py         # Directory tree generator
│   │
│   ├── parsers/                 # Ecosystem manifest & lockfile parsers
│   │   ├── javascript.py        # package.json, lockfiles, node_modules
│   │   ├── python.py            # pyproject.toml, requirements, Pipfile, venvs
│   │   ├── rust.py              # Cargo.toml, Cargo.lock
│   │   ├── go.py                # go.mod, go.sum
│   │   ├── java.py              # pom.xml, build.gradle
│   │   ├── php.py               # composer.json, composer.lock, vendor
│   │   └── other.py             # Ruby, .NET, Dart, Swift parsers
│   │
│   ├── reporters/               # Output presentation
│   │   ├── terminal.py          # Rich terminal dashboard renderer
│   │   ├── json_report.py       # JSON schema-compliant exporter
│   │   └── csv_report.py        # Tabular CSV generator
│   │
│   └── utils/                   # Helpers
│       ├── filesystem.py        # Safe I/O, binary check, file hashing
│       ├── formatting.py        # Human-readable bytes, durations, numbers
│       ├── git_utils.py         # Subprocess wrappers for Git CLI
│       └── ignore.py            # PathSpec ignore matcher
│
└── tests/                       # Automated test suite
    ├── conftest.py              # Shared fixtures & mock repositories
    ├── test_cli.py              # CLI commands, arguments, exit codes
    ├── test_scanner.py          # Traversals, ignore rules, empty projects
    ├── test_loc.py              # Language-aware LOC counting & reconciliation
    ├── test_languages.py        # Detection & distribution logic
    ├── test_dependencies.py     # Manifest & lockfile parsing
    ├── test_parsers_extended.py # Java, PHP, Ruby, .NET, Dart, Swift tests
    ├── test_git.py              # Git analytics & velocity tests
    ├── test_health.py           # Hygiene checks & scoring methodology
    ├── test_storage.py          # Storage breakdown & byte formatting
    ├── test_structure_and_terminal.py # Directory tree & Rich dashboard tests
    ├── test_exports.py          # JSON/CSV file generation & overwrite guards
    └── test_final_polish.py     # Edge case coverage & config tests
```

---

## Development & Testing

Run all unit and integration tests with coverage:

```bash
# Run pytest with terminal coverage report
pytest --cov=rpx --cov-report=term-missing

# Run code style & lint checks
ruff check .
ruff format --check .
```

---

## Privacy, Telemetry & Security

- **100% Local**: RPX performs all analysis on your machine.
- **No Telemetry**: No tracking, phone-home requests, or analytics pings.
- **No Code Execution**: RPX never executes project code, scripts, or package managers (`npm install`, `pip`, etc.).
- **No Secret Leakage**: Environment variable values, `.env` file secrets, and private keys are never read, printed, or exported.
- **Safe Read-Only Operations**: RPX never modifies, alters, or creates files inside the analyzed project directory (unless explicitly using `rpx config init`).

---

## Troubleshooting & Known Limitations

- **Git Analytics Unavailable**: If Git is not installed or the directory is not a Git repository, RPX gracefully continues and reports Git as unavailable.
- **Very Large Files (>10 MB)**: Files exceeding 10 MB are recorded for storage statistics but skipped during line-by-line LOC analysis to preserve memory and speed.
- **Filesystem Creation Time**: macOS supports file birth time (`st_birthtime`). On Linux filesystems where birth time is unsupported, RPX displays `Unavailable` rather than inventing false timestamps.
- **Lockfile Package Counts**: Certain monorepo lockfile formats (e.g. Yarn v1 with complex multi-selectors) may report slight variations in transitive package counts.

# Contributing to RPX

Thank you for your interest in contributing to **RPX (Repository Project Explorer)**! We welcome contributions to expand language parsers, improve scanning performance, and enhance developer tooling intelligence.

---

## 1. Development Principles

1. **Local-First & Privacy First**: RPX is an offline-capable developer CLI tool. It never sends project code or file contents to external services, executes untrusted repository code, or performs telemetry.
2. **Accurate Statistics Over Guesstimates**: LOC counts, file counts, and dependency numbers must be exact and mathematically reconciled.
3. **Mandatory Secret Redaction**: Any analyzer that detects credentials or keys must sanitize and redact values before output or export.
4. **Performance & Clean Pruning**: Scanning must be fast. Avoid traversing excluded directories (`.git`, `node_modules`, `.venv`).
5. **No Breaking Changes**: Core models and existing CLI flags must remain backward-compatible.

---

## 2. Environment Setup

RPX requires **Python 3.11+**.

```bash
# Clone the repository
git clone https://github.com/vinit/rpx.git
cd rpx

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

Verify your installation:

```bash
rpx --version
python3 -m rpx --help
```

---

## 3. Running Tests & Code Quality Checks

We maintain strict quality gates: comprehensive unit and integration tests and zero Ruff lint errors.

```bash
# Run pytest with code coverage
pytest --cov=rpx --cov-report=term-missing

# Run Ruff linter
ruff check .

# Run Ruff formatter check
ruff format --check .
```

To auto-format code before committing:

```bash
ruff check . --fix
ruff format .
```

---

## 4. Architecture & Adding New Features

Refer to [ARCHITECTURE.md](ARCHITECTURE.md) for full architectural patterns and layer descriptions.

- **Adding a New Language**:
  1. Add language extensions and comment syntax rules to `src/rpx/constants.py`.
  2. If the language has specialized function declaration syntax, add recognition rules to `src/rpx/analyzers/complexity.py`.
  3. Add corresponding unit tests in `tests/`.
- **Adding a Dependency Ecosystem**:
  1. Add manifest and lockfile parsing logic to `src/rpx/analyzers/dependencies.py` or `src/rpx/parsers/`.
  2. Add monorepo package detection support in `src/rpx/analyzers/monorepo.py`.
  3. Add test fixtures and verification in `tests/test_dependencies.py`.
- **Adding a CLI Command**:
  1. Register the command in `src/rpx/cli.py` and add it to `KNOWN_SUBCOMMANDS`.
  2. Add terminal presentation rendering methods in `src/rpx/reporters/terminal.py`.
  3. Add CLI integration tests in `tests/test_v1_cli_and_modes.py`.

---

## 5. Submitting Pull Requests

1. Create a feature branch from `main`: `git checkout -b feature/my-new-analyzer`.
2. Ensure all tests pass (`pytest --cov=rpx`) and lint checks pass (`ruff check .`).
3. Commit your changes with clear, descriptive commit messages adhering to Conventional Commits.
4. Open a pull request against `main` describing your changes and test verification results.

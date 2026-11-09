# Contributing to RPX

Thank you for your interest in contributing to **RPX (Repository Project Explorer)**! We welcome contributions to expand language parsers, improve scanning performance, and enhance developer tooling intelligence.

---

## 1. Development Principles

1. **Local-First & Privacy First**: RPX is an offline-capable developer CLI tool. It never sends project code or file contents to external services, executes untrusted repository code, or performs telemetry.
2. **Accurate Statistics Over Guesstimates**: LOC counts, file counts, and dependency numbers must be exact and mathematically reconciled.
3. **Mandatory Secret Redaction**: Any analyzer that detects credentials or keys must sanitize and redact values before output or export.
4. **Performance & Clean Pruning**: Scanning must be fast. Avoid traversing excluded directories (`.git`, `node_modules`, `.venv`).
5. **No Breaking Changes**: Core models and existing CLI flags must remain backward-compatible.
6. **Cross-Platform Compatibility**: File paths and analyzers must function reliably across Linux, macOS, and Windows.

---

## 2. Environment Setup

RPX requires **Python 3.11+**.

```bash
# Clone the repository
git clone https://github.com/VinitSurve/rpx.git
cd rpx

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

Alternatively, if you use [uv](https://github.com/astral-sh/uv):

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Verify your installation:

```bash
rpx --version
python3 -m rpx --help
```

---

## 3. Running Tests & Code Quality Checks

We maintain strict quality gates: comprehensive unit and integration tests, cross-platform compatibility, and zero Ruff lint errors.

```bash
# Run pytest with code coverage
pytest --cov=rpx --cov-report=term-missing

# Run Ruff linter
ruff check .

# Run Ruff formatter check
ruff format --check .

# Run Python compilation check
python -m compileall src tests

# Run security audit on dependencies
pip-audit .
```

To auto-format code before committing:

```bash
ruff check . --fix
ruff format .
```

---

## 4. Branch Naming & Commit Conventions

### Branch Naming
Create focused, descriptive branches:
- `feature/<feature-name>` (e.g., `feature/kotlin-complexity-parser`)
- `fix/<bug-description>` (e.g., `fix/windows-symlink-resolution`)
- `docs/<doc-topic>` (e.g., `docs/homebrew-setup-guide`)
- `refactor/<module-name>` (e.g., `refactor/git-churn-cache`)
- `chore/<task>` (e.g., `chore/bump-dev-dependencies`)

### Commit Messages
We follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```text
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

**Common types**:
- `feat`: A new feature or capability.
- `fix`: A bug fix.
- `docs`: Documentation-only changes.
- `perf`: Performance improvements.
- `refactor`: Code change that neither fixes a bug nor adds a feature.
- `test`: Adding or correcting tests.
- `chore`: Build process, CI/CD, or auxiliary tooling changes.

---

## 5. Architecture & Adding New Features

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

## 6. Bug Reporting & Feature Proposals

- **Bug Reports**: Please open an issue using the [Bug Report template](https://github.com/VinitSurve/rpx/issues/new?template=bug_report.yml). Provide your OS, Python version, RPX version, reproduction steps, and error traces.
- **Feature Requests**: Open an issue using the [Feature Request template](https://github.com/VinitSurve/rpx/issues/new?template=feature_request.yml) to discuss requirements and design before starting work.
- **Security Vulnerabilities**: Refer to [SECURITY.md](SECURITY.md). Do not submit security vulnerabilities via public issues.

---

## 7. Submitting Pull Requests

1. Fork the repository and create your branch from `main`.
2. Ensure all tests pass (`pytest --cov=rpx`) and lint checks pass (`ruff check .`).
3. Verify all files compile cleanly (`python -m compileall src tests`).
4. Keep pull requests focused on a single logical change.
5. Fill out the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md) completely.
6. Check that CI passes across all operating systems and Python versions.

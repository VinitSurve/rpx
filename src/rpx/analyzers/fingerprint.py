"""Evidence-backed project fingerprinting for languages, frameworks, and developer tooling."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Sequence

from rpx.models import (
    DependencyAnalysis,
    FileRecord,
    FingerprintEvidence,
    LanguageStat,
    ProjectFingerprint,
)

# Map of normalized dependency name -> (Category, Display Name)
_DEP_SIGNATURES: dict[str, list[tuple[str, str]]] = {
    # Frameworks
    "fastapi": [("framework", "FastAPI")],
    "flask": [("framework", "Flask")],
    "django": [("framework", "Django")],
    "typer": [("framework", "Typer CLI")],
    "click": [("framework", "Click CLI")],
    "rich": [("framework", "Rich TUI")],
    "textual": [("framework", "Textual TUI")],
    "streamlit": [("framework", "Streamlit")],
    "gradio": [("framework", "Gradio")],
    "torch": [("framework", "PyTorch")],
    "tensorflow": [("framework", "TensorFlow")],
    "scikit_learn": [("framework", "scikit-learn")],
    "react": [("framework", "React")],
    "next": [("framework", "Next.js")],
    "vue": [("framework", "Vue.js")],
    "nuxt": [("framework", "Nuxt")],
    "svelte": [("framework", "Svelte")],
    "@angular/core": [("framework", "Angular")],
    "express": [("framework", "Express")],
    "@nestjs/core": [("framework", "NestJS")],
    "fastify": [("framework", "Fastify")],
    "tailwindcss": [("framework", "Tailwind CSS")],
    "actix_web": [("framework", "Actix Web")],
    "axum": [("framework", "Axum")],
    "tokio": [("framework", "Tokio")],
    "rocket": [("framework", "Rocket")],
    "clap": [("framework", "Clap CLI")],
    "gin": [("framework", "Gin")],
    # Test frameworks
    "pytest": [("test_framework", "pytest")],
    "hypothesis": [("test_framework", "Hypothesis")],
    "tox": [("test_framework", "tox")],
    "nox": [("test_framework", "nox")],
    "jest": [("test_framework", "Jest")],
    "vitest": [("test_framework", "Vitest")],
    "@playwright/test": [("test_framework", "Playwright")],
    "cypress": [("test_framework", "Cypress")],
    "mocha": [("test_framework", "Mocha")],
    # Linters & Formatters
    "ruff": [("linter", "Ruff"), ("formatter", "Ruff Format")],
    "flake8": [("linter", "Flake8")],
    "pylint": [("linter", "Pylint")],
    "bandit": [("linter", "Bandit")],
    "black": [("formatter", "Black")],
    "isort": [("formatter", "isort")],
    "eslint": [("linter", "ESLint")],
    "prettier": [("formatter", "Prettier")],
    "@biomejs/biome": [("linter", "Biome"), ("formatter", "Biome")],
    # Type checkers
    "mypy": [("type_checker", "mypy")],
    "pyright": [("type_checker", "Pyright")],
    "typescript": [("type_checker", "TypeScript")],
    # Build tools
    "vite": [("build_tool", "Vite")],
    "webpack": [("build_tool", "Webpack")],
    "esbuild": [("build_tool", "esbuild")],
    "rollup": [("build_tool", "Rollup")],
    "turbo": [("build_tool", "Turborepo")],
}


def analyze_project_fingerprint(
    project_root: Path,
    files: Sequence[FileRecord],
    languages: Sequence[LanguageStat],
    dep_analysis: DependencyAnalysis | None,
) -> ProjectFingerprint:
    """Detect languages, frameworks, build tools, test runners, linters, CI/CD, and conventions with evidence."""
    primary_languages = [lang.name for lang in languages[:5]]
    frameworks: list[str] = []
    package_managers: list[str] = []
    build_tools: list[str] = []
    test_frameworks: list[str] = []
    linters: list[str] = []
    formatters: list[str] = []
    type_checkers: list[str] = []
    ci_cd_systems: list[str] = []
    container_tools: list[str] = []
    conventions: list[str] = []
    evidence: list[FingerprintEvidence] = []

    def _add(target_list: list[str], category: str, name: str, ev_str: str) -> None:
        if name not in target_list:
            target_list.append(name)
            evidence.append(FingerprintEvidence(category=category, detected=name, evidence=ev_str))

    rel_paths = {f.relative_path.replace("\\", "/") for f in files}
    filenames = {f.name: f.relative_path for f in files}

    # 1. Inspect language evidence
    for lang in languages[:3]:
        evidence.append(
            FingerprintEvidence(
                category="language",
                detected=lang.name,
                evidence=f"{lang.files} source files ({lang.percentage:.1f}% of code)",
            )
        )

    # 2. Package managers & Lockfiles
    pm_rules = [
        ("uv.lock", "uv"),
        ("poetry.lock", "Poetry"),
        ("Pipfile", "Pipenv"),
        ("Pipfile.lock", "Pipenv"),
        ("requirements.txt", "pip"),
        ("environment.yml", "Conda"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "Yarn"),
        ("bun.lockb", "Bun"),
        ("package-lock.json", "npm"),
        ("package.json", "npm"),
        ("Cargo.toml", "Cargo"),
        ("go.mod", "Go Modules"),
        ("pom.xml", "Maven"),
        ("build.gradle", "Gradle"),
        ("build.gradle.kts", "Gradle"),
        ("composer.json", "Composer"),
        ("Gemfile", "Bundler"),
    ]
    for fname, pm_name in pm_rules:
        if fname in filenames:
            _add(package_managers, "package_manager", pm_name, f"Found {filenames[fname]}")

    # 3. Inspect pyproject.toml for Python build backend & tool configs
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.is_file():
        try:
            with open(pyproject_path, "rb") as f:
                py_data = tomllib.load(f)
            build_backend = py_data.get("build-system", {}).get("build-backend", "")
            if " setuptools" in f" {build_backend}" or "setuptools" in build_backend:
                _add(build_tools, "build_tool", "setuptools", "pyproject.toml [build-system]")
            elif "hatchling" in build_backend:
                _add(
                    build_tools, "build_tool", "Hatch / hatchling", "pyproject.toml [build-system]"
                )
            elif "poetry" in build_backend:
                _add(build_tools, "build_tool", "Poetry", "pyproject.toml [build-system]")
                _add(package_managers, "package_manager", "Poetry", "pyproject.toml [build-system]")
            elif "flit" in build_backend:
                _add(build_tools, "build_tool", "Flit", "pyproject.toml [build-system]")
            elif "maturin" in build_backend:
                _add(build_tools, "build_tool", "Maturin", "pyproject.toml [build-system]")

            tools = py_data.get("tool", {})
            if isinstance(tools, dict):
                if "pytest" in tools:
                    _add(
                        test_frameworks, "test_framework", "pytest", "pyproject.toml [tool.pytest]"
                    )
                if "ruff" in tools:
                    _add(linters, "linter", "Ruff", "pyproject.toml [tool.ruff]")
                    _add(formatters, "formatter", "Ruff Format", "pyproject.toml [tool.ruff]")
                if "black" in tools:
                    _add(formatters, "formatter", "Black", "pyproject.toml [tool.black]")
                if "isort" in tools:
                    _add(formatters, "formatter", "isort", "pyproject.toml [tool.isort]")
                if "mypy" in tools:
                    _add(type_checkers, "type_checker", "mypy", "pyproject.toml [tool.mypy]")
                if "pyright" in tools:
                    _add(type_checkers, "type_checker", "Pyright", "pyproject.toml [tool.pyright]")
                if "uv" in tools:
                    _add(package_managers, "package_manager", "uv", "pyproject.toml [tool.uv]")
        except Exception:
            pass

    # 4. Inspect dependencies for frameworks, test runners, linters, type checkers, build tools
    cat_map = {
        "framework": frameworks,
        "test_framework": test_frameworks,
        "linter": linters,
        "formatter": formatters,
        "type_checker": type_checkers,
        "build_tool": build_tools,
    }
    if dep_analysis:
        for dep in dep_analysis.dependencies:
            norm = dep.name.lower().replace("-", "_")
            for key in (dep.name.lower(), norm):
                if key in _DEP_SIGNATURES:
                    for cat, disp in _DEP_SIGNATURES[key]:
                        _add(
                            cat_map[cat],
                            cat,
                            disp,
                            f"Dependency '{dep.name}' in {dep.source_file}",
                        )

    # 5. File-based detection for build tools, linters, formatters, type checkers, tests
    file_tool_rules = [
        ("Makefile", build_tools, "build_tool", "Make"),
        ("CMakeLists.txt", build_tools, "build_tool", "CMake"),
        ("turbo.json", build_tools, "build_tool", "Turborepo"),
        ("nx.json", build_tools, "build_tool", "Nx"),
        ("vite.config.ts", build_tools, "build_tool", "Vite"),
        ("vite.config.js", build_tools, "build_tool", "Vite"),
        ("webpack.config.js", build_tools, "build_tool", "Webpack"),
        ("tsconfig.json", type_checkers, "type_checker", "TypeScript"),
        ("mypy.ini", type_checkers, "type_checker", "mypy"),
        ("pyrightconfig.json", type_checkers, "type_checker", "Pyright"),
        ("ruff.toml", linters, "linter", "Ruff"),
        (".ruff.toml", linters, "linter", "Ruff"),
        (".flake8", linters, "linter", "Flake8"),
        (".eslintrc.js", linters, "linter", "ESLint"),
        (".eslintrc.json", linters, "linter", "ESLint"),
        ("eslint.config.js", linters, "linter", "ESLint"),
        ("biome.json", linters, "linter", "Biome"),
        (".prettierrc", formatters, "formatter", "Prettier"),
        (".prettierrc.json", formatters, "formatter", "Prettier"),
        ("prettier.config.js", formatters, "formatter", "Prettier"),
        (".editorconfig", formatters, "formatter", "EditorConfig"),
        ("pytest.ini", test_frameworks, "test_framework", "pytest"),
        ("conftest.py", test_frameworks, "test_framework", "pytest"),
        ("jest.config.js", test_frameworks, "test_framework", "Jest"),
        ("jest.config.ts", test_frameworks, "test_framework", "Jest"),
        ("vitest.config.ts", test_frameworks, "test_framework", "Vitest"),
    ]
    for fname, target_lst, cat, disp in file_tool_rules:
        if fname in filenames:
            _add(target_lst, cat, disp, f"Found {filenames[fname]}")

    # 6. CI/CD systems
    for rp in sorted(rel_paths):
        if rp.startswith(".github/workflows/") and rp.endswith((".yml", ".yaml")):
            _add(ci_cd_systems, "ci_cd", "GitHub Actions", f"Found {rp}")
        elif rp == ".gitlab-ci.yml":
            _add(ci_cd_systems, "ci_cd", "GitLab CI", "Found .gitlab-ci.yml")
        elif rp.startswith(".circleci/"):
            _add(ci_cd_systems, "ci_cd", "CircleCI", f"Found {rp}")
        elif rp == "Jenkinsfile":
            _add(ci_cd_systems, "ci_cd", "Jenkins", "Found Jenkinsfile")
        elif rp == "azure-pipelines.yml":
            _add(ci_cd_systems, "ci_cd", "Azure Pipelines", "Found azure-pipelines.yml")

    # 7. Container tooling
    for fname in ("Dockerfile", "Containerfile"):
        if fname in filenames:
            _add(container_tools, "container", "Docker", f"Found {filenames[fname]}")
    for fname in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if fname in filenames:
            _add(container_tools, "container", "Docker Compose", f"Found {filenames[fname]}")
    if any(rp.startswith(".devcontainer/") for rp in rel_paths):
        _add(container_tools, "container", "Dev Containers", "Found .devcontainer/")

    # 8. Repository conventions
    if any(rp.startswith("src/") for rp in rel_paths):
        _add(conventions, "convention", "src-layout", "Source code organized under src/")
    if any(rp.startswith(("tests/", "test/")) for rp in rel_paths):
        _add(conventions, "convention", "dedicated-test-dir", "Dedicated tests/ directory")
    if "py.typed" in filenames:
        _add(conventions, "convention", "pep561-typed", f"Found {filenames['py.typed']}")
    if ".pre-commit-config.yaml" in filenames:
        _add(conventions, "convention", "pre-commit-hooks", "Found .pre-commit-config.yaml")
    if any(k.lower().startswith("changelog") for k in filenames):
        _add(conventions, "convention", "changelog-maintained", "Found CHANGELOG")
    if any(k.lower().startswith(("license", "copying")) for k in filenames):
        _add(conventions, "convention", "license-present", "Found LICENSE")

    return ProjectFingerprint(
        primary_languages=primary_languages,
        frameworks=frameworks,
        package_managers=package_managers,
        build_tools=build_tools,
        test_frameworks=test_frameworks,
        linters=linters,
        formatters=formatters,
        type_checkers=type_checkers,
        ci_cd_systems=ci_cd_systems,
        container_tools=container_tools,
        conventions=conventions,
        evidence=evidence,
    )

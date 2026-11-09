"""Shared pytest fixtures, mock projects, and temporary directory helpers."""

import subprocess
from pathlib import Path

import pytest

from rpx.models import (
    DependencyAnalysis,
    DirectoryStats,
    FileLOC,
    FileStats,
    GitAnalytics,
    HealthFindings,
    LanguageDistribution,
    LOCStats,
    ProjectMetadata,
    ScanResult,
    StorageAnalytics,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary multi-language sample project."""
    proj = tmp_path / "sample_project"
    proj.mkdir()

    # Python source
    src_dir = proj / "src"
    src_dir.mkdir()
    py_file = src_dir / "main.py"
    py_file.write_text(
        "#!/usr/bin/env python3\n"
        '"""Module docstring\n'
        "describing sample project.\n"
        '"""\n'
        "import os\n"
        "import sys\n"
        "\n"
        "def hello(name: str) -> str:\n"
        "    # Greeting helper\n"
        '    msg = f"Hello {name}"  # inline comment\n'
        "    print(msg)\n"
        "    return msg\n"
        "\n"
        "# TODO: Add more functions\n"
        'if __name__ == "__main__":\n'
        '    hello("world")\n',
        encoding="utf-8",
    )

    # TypeScript source
    ts_file = src_dir / "index.ts"
    ts_file.write_text(
        "/*\n"
        " * Multi-line header comment\n"
        " */\n"
        "export function calculate(a: number, b: number): number {\n"
        "  // calculate sum\n"
        "  const sum = a + b; // inline comment\n"
        "  console.log(sum);\n"
        "  return sum;\n"
        "}\n"
        "\n"
        "// FIXME: handle overflow\n",
        encoding="utf-8",
    )

    # Tests
    tests_dir = proj / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_main.py"
    test_file.write_text(
        "import pytest\n"
        "from src.main import hello\n"
        "\n"
        "def test_hello():\n"
        '    assert hello("test") == "Hello test"\n',
        encoding="utf-8",
    )

    # Config and manifests
    pyproject = proj / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        'name = "sample-project"\n'
        'version = "1.0.0"\n'
        "dependencies = [\n"
        '    "requests>=2.28.0",\n'
        '    "click>=8.0.0",\n'
        "]\n"
        "\n"
        "[project.optional-dependencies]\n"
        "dev = [\n"
        '    "pytest>=7.0.0",\n'
        "]\n",
        encoding="utf-8",
    )

    pkg_json = proj / "package.json"
    pkg_json.write_text(
        "{\n"
        '  "name": "sample-node",\n'
        '  "version": "1.0.0",\n'
        '  "dependencies": {\n'
        '    "express": "^4.18.2"\n'
        "  },\n"
        '  "devDependencies": {\n'
        '    "typescript": "^5.0.0"\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    # Readme, License, gitignore
    (proj / "README.md").write_text(
        "# Sample Project\nA comprehensive test project.\n", encoding="utf-8"
    )
    (proj / "LICENSE").write_text("MIT License\nCopyright 2026\n", encoding="utf-8")
    (proj / ".gitignore").write_text("node_modules/\n*.pyc\n.cache/\n", encoding="utf-8")
    (proj / ".env.example").write_text("API_KEY=your_key_here\n", encoding="utf-8")

    return proj


@pytest.fixture
def temp_git_project(temp_project: Path) -> Path:
    """Initialize a git repository in the temporary project with commits."""
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_project, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_project,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=temp_project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_project, capture_output=True, check=True
    )

    # Second commit
    readme = temp_project / "README.md"
    readme.write_text("# Sample Project Updated\nMore details.\n", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "-am", "Update README"], cwd=temp_project, capture_output=True, check=True
    )

    # Add a tag
    subprocess.run(["git", "tag", "v1.0.0"], cwd=temp_project, capture_output=True, check=True)

    return temp_project


@pytest.fixture
def mock_scan_result() -> ScanResult:
    """Mock ScanResult instance for report tests."""
    meta = ProjectMetadata(
        name="test-repo",
        path="/path/to/test-repo",
        project_types=["Python"],
        created_at="2026-01-01 00:00:00 UTC",
        total_size_bytes=5000,
        scan_duration_seconds=0.12,
    )
    floc = FileLOC(
        path="app.py", language="Python", total_physical=50, code=40, comments=5, blank=5
    )
    return ScanResult(
        metadata=meta,
        files=FileStats(total_files=1, source_files=1),
        directories=DirectoryStats(),
        loc=LOCStats(
            total_physical=50, total_code=40, total_comment=5, total_blank=5, per_file_loc=[floc]
        ),
        languages=LanguageDistribution(total_detected_languages=1),
        dependencies=DependencyAnalysis(),
        git=GitAnalytics(),
        health=HealthFindings(score=85),
        storage=StorageAnalytics(total_project_size_bytes=5000),
    )

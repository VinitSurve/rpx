"""Tests for multi-ecosystem dependency analyzers and parsers."""

from pathlib import Path

from rpx.analyzers.dependencies import analyze_dependencies
from rpx.parsers.go import parse_go_mod
from rpx.parsers.javascript import parse_package_json
from rpx.parsers.python import parse_pyproject_toml, parse_requirements_txt
from rpx.parsers.rust import parse_cargo_toml


def test_python_dependencies(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        "dependencies = [\n"
        '    "fastapi>=0.100.0",\n'
        '    "uvicorn[standard]>=0.22.0",\n'
        "]\n"
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=7.0.0"]\n',
        encoding="utf-8",
    )

    direct, dev = parse_pyproject_toml(pyproject)
    assert len(direct) == 2
    assert any(d.name == "fastapi" for d in direct)
    assert len(dev) == 1
    assert dev[0].name == "pytest"

    # Requirements.txt
    req = tmp_path / "requirements.txt"
    req.write_text(
        "# Core dependencies\nrequests>=2.28.0\npydantic~=2.0\n-r other.txt\n",
        encoding="utf-8",
    )
    req_deps = parse_requirements_txt(req)
    assert len(req_deps) == 2
    assert req_deps[0].name == "requests"


def test_javascript_dependencies(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        "{\n"
        '  "dependencies": {\n'
        '    "react": "^18.2.0",\n'
        '    "react-dom": "^18.2.0"\n'
        "  },\n"
        '  "devDependencies": {\n'
        '    "vite": "^4.4.0"\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    direct, dev = parse_package_json(pkg_json)
    assert len(direct) == 2
    assert len(dev) == 1
    assert direct[0].name == "react"
    assert dev[0].name == "vite"


def test_rust_and_go_dependencies(tmp_path: Path):
    # Rust
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n\n'
        '[dependencies]\ntokio = "1.0"\nserde = { version = "1.0", features = ["derive"] }\n\n'
        '[dev-dependencies]\ntempfile = "3.0"\n',
        encoding="utf-8",
    )
    direct, dev = parse_cargo_toml(cargo)
    assert len(direct) == 2
    assert len(dev) == 1
    assert direct[0].name == "tokio"

    # Go
    go_mod = tmp_path / "go.mod"
    go_mod.write_text(
        "module github.com/user/demo\n\ngo 1.21\n\n"
        "require (\n"
        "\tgithub.com/gin-gonic/gin v1.9.1\n"
        "\tgolang.org/x/crypto v0.14.0 // indirect\n"
        ")\n",
        encoding="utf-8",
    )
    g_direct, g_indirect = parse_go_mod(go_mod)
    assert len(g_direct) == 1
    assert g_direct[0].name == "github.com/gin-gonic/gin"
    assert len(g_indirect) == 1
    assert g_indirect[0].name == "golang.org/x/crypto"


def test_analyze_dependencies_orchestration(temp_project: Path):
    analysis = analyze_dependencies(temp_project)
    assert "Python" in analysis.ecosystems
    assert "JavaScript/TypeScript" in analysis.ecosystems
    assert analysis.direct_dependencies_count >= 3
    assert len(analysis.manifest_files) >= 2

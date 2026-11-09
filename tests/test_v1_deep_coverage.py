"""Deep coverage tests for monorepo ecosystems, AI providers, CI gates, snapshots, and exporters."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rpx.ai import (
    GeminiProvider,
    GroqProvider,
    KeypoolCredentialProvider,
    run_ai_insights,
)
from rpx.analyzers.monorepo import analyze_monorepo
from rpx.ci import evaluate_ci_gates, format_ci_report
from rpx.models import FileRecord, ModuleNode
from rpx.reporters.context_report import export_context_report
from rpx.reporters.csv_report import save_csv_report
from rpx.reporters.json_report import save_json_report
from rpx.reporters.mermaid_report import export_mermaid_report, generate_mermaid_graph
from rpx.scanner import ProjectScanner
from rpx.snapshots import get_snapshot


def test_monorepo_all_workspace_ecosystems(tmp_path: Path):
    mono = tmp_path / "poly_mono"
    mono.mkdir()

    # Workspace root configs
    (mono / "nx.json").write_text("{}", encoding="utf-8")
    (mono / "lerna.json").write_text("{}", encoding="utf-8")
    (mono / "pnpm-workspace.yaml").write_text("packages:\n  - 'pkgs/*'\n", encoding="utf-8")
    (mono / "go.work").write_text("go 1.22\nuse ./services/auth\n", encoding="utf-8")
    (mono / "settings.gradle").write_text("include(':app')\n", encoding="utf-8")
    (mono / "pom.xml").write_text(
        "<project><modules><module>java-svc</module></modules></project>", encoding="utf-8"
    )
    (mono / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    (mono / "package.json").write_text(
        '{"name": "root", "workspaces": ["pkgs/*"]}', encoding="utf-8"
    )
    (mono / "pyproject.toml").write_text(
        "[tool.uv.workspace]\nmembers = ['py/*']\n", encoding="utf-8"
    )
    (mono / "Cargo.toml").write_text("[workspace]\nmembers = ['crates/*']\n", encoding="utf-8")

    # Sub-packages across Python, Rust, Go, Maven
    py_pkg = mono / "py" / "core_lib"
    py_pkg.mkdir(parents=True)
    (py_pkg / "pyproject.toml").write_text(
        '[project]\nname = "core-lib"\ndependencies = ["pydantic>=2.0"]\n',
        encoding="utf-8",
    )
    (py_pkg / "mod.py").write_text("x = 1\n", encoding="utf-8")

    rs_pkg = mono / "crates" / "engine"
    rs_pkg.mkdir(parents=True)
    (rs_pkg / "Cargo.toml").write_text(
        '[package]\nname = "engine"\n[dependencies]\nserde = "1.0"\n',
        encoding="utf-8",
    )
    (rs_pkg / "lib.rs").write_text("pub fn run() {}\n", encoding="utf-8")

    go_pkg = mono / "services" / "auth"
    go_pkg.mkdir(parents=True)
    (go_pkg / "go.mod").write_text(
        "module github.com/acme/auth\nrequire (\n  github.com/gin-gonic/gin v1.9.1\n)\n",
        encoding="utf-8",
    )
    (go_pkg / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

    java_pkg = mono / "java-svc"
    java_pkg.mkdir(parents=True)
    (java_pkg / "pom.xml").write_text(
        "<project><artifactId>java-svc</artifactId></project>", encoding="utf-8"
    )

    files = [
        FileRecord("nx.json", "nx.json", ".json"),
        FileRecord("lerna.json", "lerna.json", ".json"),
        FileRecord("pnpm-workspace.yaml", "pnpm-workspace.yaml", ".yaml"),
        FileRecord("go.work", "go.work", ".work"),
        FileRecord("settings.gradle", "settings.gradle", ".gradle"),
        FileRecord("pom.xml", "pom.xml", ".xml"),
        FileRecord("yarn.lock", "yarn.lock", ".lock"),
        FileRecord("package.json", "package.json", ".json"),
        FileRecord("pyproject.toml", "pyproject.toml", ".toml"),
        FileRecord("Cargo.toml", "Cargo.toml", ".toml"),
        FileRecord("py/core_lib/pyproject.toml", "pyproject.toml", ".toml"),
        FileRecord(
            "py/core_lib/mod.py", "mod.py", ".py", is_source=True, language="Python", code_lines=5
        ),
        FileRecord("crates/engine/Cargo.toml", "Cargo.toml", ".toml"),
        FileRecord(
            "crates/engine/lib.rs", "lib.rs", ".rs", is_source=True, language="Rust", code_lines=10
        ),
        FileRecord("services/auth/go.mod", "go.mod", ".mod"),
        FileRecord(
            "services/auth/main.go", "main.go", ".go", is_source=True, language="Go", code_lines=8
        ),
        FileRecord("java-svc/pom.xml", "pom.xml", ".xml"),
    ]

    res = analyze_monorepo(mono, files)
    assert res.is_monorepo is True
    assert "Nx" in res.workspace_tools
    assert "Lerna" in res.workspace_tools
    assert "pnpm Workspaces" in res.workspace_tools
    assert "Go Workspace" in res.workspace_tools
    assert "Gradle Multi-Project" in res.workspace_tools
    assert "Yarn Workspaces" in res.workspace_tools
    assert "uv Workspace" in res.workspace_tools
    assert "Cargo Workspace" in res.workspace_tools
    assert "Maven Multi-Module" in res.workspace_tools
    assert len(res.packages) == 4


def test_ai_groq_gemini_and_keypool_mocked(temp_git_project: Path, monkeypatch: pytest.MonkeyPatch):
    # 1. Mock KeypoolCredentialProvider
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/local/bin/keypool" if cmd == "keypool" else None
    )
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "kp_secret_key_123\n"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_proc)

    kp = KeypoolCredentialProvider(enabled=True)
    assert kp.is_available() is True
    assert kp.get_api_key("groq") == "kp_secret_key_123"

    # 2. Mock GroqProvider HTTP call
    class FakeHTTPResponse:
        def __init__(self, payload: dict):
            self._bytes = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self._bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=20.0: FakeHTTPResponse(
            {"choices": [{"message": {"content": "Groq architectural summary"}}]}
        ),
    )
    groq = GroqProvider(api_key="dummy")
    assert groq.generate_insights("context", focus="architecture") == "Groq architectural summary"

    # 3. Mock GeminiProvider HTTP call
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=20.0: FakeHTTPResponse(
            {"candidates": [{"content": {"parts": [{"text": "Gemini refactoring summary"}]}}]}
        ),
    )
    gem = GeminiProvider(api_key="dummy")
    assert gem.generate_insights("context", focus="refactoring") == "Gemini refactoring summary"

    # 4. Test run_ai_insights with Gemini preference
    res = ProjectScanner(temp_git_project).scan()
    prov, out = run_ai_insights(res, provider_pref="gemini", cred_provider=kp)
    assert prov == "gemini"
    assert "Gemini refactoring summary" in out


def test_ci_all_gates_and_exporters(temp_git_project: Path, tmp_path: Path):
    res = ProjectScanner(temp_git_project).scan()
    # Add a fake cycle to test fail_on_cycles
    res.graph.cycles = [["mod_a", "mod_b", "mod_a"]]
    res.graph.modules = [
        ModuleNode(name="mod_a", file_path="a.py", language="Python", layer="core"),
        ModuleNode(name="mod_b", file_path="b.py", language="Python", layer="core"),
    ]
    res.graph.edges = [("mod_a", "mod_b"), ("mod_b", "mod_a")]
    res.graph.inferred_layers = {"core": ["mod_a", "mod_b"]}

    ci_res = evaluate_ci_gates(
        res,
        min_health_score=10,
        max_high_security=5,
        max_high_debt=0,
        max_complexity=50,
        fail_on_cycles=True,
    )
    assert ci_res["passed"] is False
    assert any(
        c["gate"] == "no_circular_dependencies" and not c["passed"] for c in ci_res["checks"]
    )
    assert "FAILED" in format_ci_report(ci_res, fmt="text")
    assert '"passed": false' in format_ci_report(ci_res, fmt="json")

    # Mermaid with cycles and .md wrapper
    mmd_str = generate_mermaid_graph(res.graph)
    assert "cycle" in mmd_str
    md_out = export_mermaid_report(res, tmp_path / "graph.md")
    assert "```mermaid" in md_out.read_text(encoding="utf-8")

    # Context report file export (both md and json)
    ctx_md_file = export_context_report(res, tmp_path / "ctx.md", fmt="markdown", max_chars=500)
    assert ctx_md_file.is_file()
    ctx_js_file = export_context_report(res, tmp_path / "ctx.json", fmt="json")
    assert ctx_js_file.is_file()

    # CSV save_csv_report for complexity, debt, security
    save_csv_report(res, tmp_path / "comp.csv", table_type="complexity", force=True)
    save_csv_report(res, tmp_path / "debt.csv", table_type="debt", force=True)
    save_csv_report(res, tmp_path / "sec.csv", table_type="security", force=True)
    assert (tmp_path / "comp.csv").is_file()
    assert (tmp_path / "debt.csv").is_file()
    assert (tmp_path / "sec.csv").is_file()

    # Snapshot loading from an exported JSON report file
    json_report_path = tmp_path / "full_report.json"
    save_json_report(res, json_report_path, force=True)
    loaded_from_report = get_snapshot(temp_git_project, str(json_report_path))
    assert "metrics" in loaded_from_report

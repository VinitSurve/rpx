"""Tests for Feature Groups B, D, and E: Complexity, Dependency Graph, Debt, Dead Code, Fingerprinting, Health, and Security."""

from __future__ import annotations

from pathlib import Path

from rpx.analyzers.complexity import (
    aggregate_complexity,
    analyze_brace_file_complexity,
    analyze_python_file_complexity,
)
from rpx.analyzers.debt import analyze_technical_debt
from rpx.analyzers.fingerprint import analyze_project_fingerprint
from rpx.analyzers.graph import analyze_dependency_graph
from rpx.analyzers.security import (
    analyze_security,
    redact_all_secrets_in_text,
    redact_secret,
)
from rpx.config import RPXConfig
from rpx.models import DependencyAnalysis, DependencyInfo, FileRecord, LanguageStats


def test_python_and_brace_complexity_analysis():
    cfg = RPXConfig(
        complexity_low_max=3,
        complexity_medium_max=6,
        complexity_high_max=10,
        max_function_lines=10,
        max_nesting_depth=2,
        max_parameters=3,
    )
    py_code = """
class Processor:
    def run(self, a, b, c, d):
        if a > 0 and b > 0:
            for i in range(a):
                if i % 2 == 0:
                    while b > 0:
                        b -= 1
                elif i % 3 == 0:
                    pass
        try:
            return a + b
        except ValueError:
            return 0
"""
    fc_py, ok = analyze_python_file_complexity("src/proc.py", py_code, 18, cfg)
    assert ok is True
    assert fc_py.class_count == 1
    assert fc_py.function_count == 1
    fn = fc_py.functions[0]
    assert fn.name == "Processor.run"
    assert fn.parameter_count == 4  # excludes 'self'
    assert fn.cyclomatic_complexity >= 7
    assert fn.max_nesting_depth >= 3
    assert fn.severity in ("high", "critical")

    # Syntax error fallback
    fc_bad, ok_bad = analyze_python_file_complexity("bad.py", "def broken(:\n", 1, cfg)
    assert ok_bad is False
    assert fc_bad.function_count == 0

    # TypeScript / Go / Rust brace complexity
    ts_code = """
export class OrderService {
    public calculate(items: number[], discount: boolean): number {
        let total = 0;
        for (const x of items) {
            if (x > 100 && discount) {
                total += x * 0.9;
            } else if (x > 0) {
                total += x;
            }
        }
        return total;
    }
}
"""
    fc_ts = analyze_brace_file_complexity("src/order.ts", "TypeScript", ts_code, 16, cfg)
    assert fc_ts.class_count == 1
    assert fc_ts.function_count == 1
    assert fc_ts.functions[0].cyclomatic_complexity >= 4

    go_code = """
func Compute(x int, y int) int {
    if x > y {
        return x
    }
    return y
}
"""
    fc_go = analyze_brace_file_complexity("main.go", "Go", go_code, 8, cfg)
    assert fc_go.function_count == 1
    assert fc_go.functions[0].name == "Compute"
    assert fc_go.functions[0].cyclomatic_complexity >= 2

    rust_code = """
pub async fn process_data(input: &str) -> bool {
    if input.is_empty() || input.len() > 100 {
        return false;
    }
    true
}
"""
    fc_rs = analyze_brace_file_complexity("lib.rs", "Rust", rust_code, 8, cfg)
    assert fc_rs.function_count == 1
    assert fc_rs.functions[0].name == "process_data"

    agg = aggregate_complexity([fc_py, fc_ts, fc_go, fc_rs], cfg)
    assert agg.total_functions == 4
    assert len(agg.high_complexity_functions) >= 1
    assert len(agg.many_param_functions) >= 1
    assert len(agg.deep_nesting_functions) >= 1


def test_dependency_graph_cycles_and_layer_violations(tmp_path: Path):
    proj = tmp_path / "graph_proj"
    (proj / "src" / "pkg").mkdir(parents=True)
    (proj / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    # Cycle between a.py and b.py + layer violation (models importing cli)
    (proj / "src" / "pkg" / "cli.py").write_text(
        "import requests\nfrom . import a\n",
        encoding="utf-8",
    )
    (proj / "src" / "pkg" / "a.py").write_text(
        "from . import b\n",
        encoding="utf-8",
    )
    (proj / "src" / "pkg" / "b.py").write_text(
        "from . import a\nfrom . import models\n",
        encoding="utf-8",
    )
    (proj / "src" / "pkg" / "models.py").write_text(
        "from . import cli\n",
        encoding="utf-8",
    )

    files = [
        FileRecord("src/pkg/__init__.py", "__init__.py", ".py", is_source=True, language="Python"),
        FileRecord("src/pkg/cli.py", "cli.py", ".py", is_source=True, language="Python"),
        FileRecord("src/pkg/a.py", "a.py", ".py", is_source=True, language="Python"),
        FileRecord("src/pkg/b.py", "b.py", ".py", is_source=True, language="Python"),
        FileRecord("src/pkg/models.py", "models.py", ".py", is_source=True, language="Python"),
    ]

    graph = analyze_dependency_graph(proj, files)
    assert graph.total_modules == 5
    assert "requests" in graph.external_packages
    assert len(graph.cycles) >= 1
    assert len(graph.unexpected_layer_dependencies) >= 1


def test_technical_debt_and_dead_code_heuristics(tmp_path: Path):
    proj = tmp_path / "debt_proj"
    proj.mkdir()
    (proj / "service.py").write_text(
        "import math\n"
        "import json\n"
        "# TODO: optimize query\n"
        "# FIXME: handle race condition\n"
        "# HACK: temporary workaround\n"
        "def _unused_private_helper():\n"
        "    return 123\n"
        "def active_fn(x):\n"
        "    pdb.set_trace()\n"
        "    return json.dumps({'x': x})\n",
        encoding="utf-8",
    )

    files = [
        FileRecord(
            "service.py",
            "service.py",
            ".py",
            is_source=True,
            language="Python",
            total_lines=10,
            code_lines=7,
        )
    ]
    deps = DependencyAnalysis(
        declared_dependencies=[
            DependencyInfo(
                name="unused-fancy-lib", constraint=">=1.0", dep_type="direct", ecosystem="Python"
            )
        ]
    )
    graph = analyze_dependency_graph(proj, files)
    # Give graph an external package so unused-fancy-lib is checked
    graph.external_packages["json_ext"] = ["service"]

    debt = analyze_technical_debt(
        project_root=proj,
        files=files,
        complexity=None,
        dep_graph=graph,
        dep_analysis=deps,
        config=RPXConfig(),
    )

    assert debt.todo_count == 1
    assert debt.fixme_count == 1
    assert debt.hack_count == 1
    assert debt.debug_statement_count == 1
    assert debt.total_items >= 4

    dead_names = {d.name for d in debt.dead_code_indicators}
    assert "math" in dead_names  # unused import
    assert "_unused_private_helper" in dead_names  # unused private function
    assert "unused-fancy-lib" in dead_names  # unused dependency heuristic


def test_security_scanner_and_mandatory_secret_redaction(tmp_path: Path):
    proj = tmp_path / "sec_proj"
    proj.mkdir()

    raw_aws_key = "AKIA" + "IOSFODNN7EXAMPLE"
    raw_gh_token = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyzABCD"

    (proj / ".env").write_text(f"AWS_KEY={raw_aws_key}\n", encoding="utf-8")
    (proj / ".env.example").write_text("AWS_KEY=your_api_key_here\n", encoding="utf-8")
    (proj / "id_rsa").write_text("private key file", encoding="utf-8")
    (proj / "app.py").write_text(
        f'GITHUB_TOKEN = "{raw_gh_token}"\n'
        "def run_unsafe(cmd):\n"
        "    eval(cmd)\n"
        "    subprocess.run(cmd, shell=True)\n",
        encoding="utf-8",
    )

    files = [
        FileRecord(".env", ".env", "", is_source=False),
        FileRecord(".env.example", ".env.example", ".example", is_source=False),
        FileRecord("id_rsa", "id_rsa", "", is_source=False),
        FileRecord("app.py", "app.py", ".py", is_source=True, language="Python"),
    ]
    deps = DependencyAnalysis(
        declared_dependencies=[
            DependencyInfo(
                name="legacy-pkg", constraint="*", dep_type="direct", ecosystem="Python"
            ),
            DependencyInfo(
                name="insecure-pkg",
                constraint="http://example.com/pkg.tar.gz",
                dep_type="direct",
                ecosystem="Python",
            ),
        ]
    )

    sec = analyze_security(proj, files, deps, RPXConfig())
    assert ".env" in sec.committed_env_files
    assert ".env.example" not in sec.committed_env_files
    assert "id_rsa" in sec.sensitive_files
    assert sec.total_findings >= 6

    # CRITICAL: Verify that raw secrets NEVER appear in any finding message or snippet
    serialized = str(sec.to_dict())
    assert raw_aws_key not in serialized
    assert raw_gh_token not in serialized
    assert "REDACTED" in serialized

    # Also test direct redaction helpers
    assert raw_gh_token not in redact_secret(raw_gh_token)
    assert raw_aws_key not in redact_all_secrets_in_text(f"my key is {raw_aws_key} here")


def test_project_fingerprinting_with_evidence(tmp_path: Path):
    proj = tmp_path / "fp_proj"
    (proj / ".github" / "workflows").mkdir(parents=True)
    (proj / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "tests").mkdir()
    (proj / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    (proj / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (proj / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (proj / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (proj / "pyproject.toml").write_text(
        '[build-system]\nbuild-backend = "hatchling.build"\n'
        "[tool.ruff]\nline-length = 100\n"
        "[tool.pytest.ini_options]\n"
        "[tool.mypy]\nstrict = true\n",
        encoding="utf-8",
    )

    files = [
        FileRecord(".github/workflows/ci.yml", "ci.yml", ".yml"),
        FileRecord("src/app.py", "app.py", ".py", is_source=True, language="Python"),
        FileRecord(
            "tests/test_app.py",
            "test_app.py",
            ".py",
            is_source=True,
            is_test=True,
            language="Python",
        ),
        FileRecord("Dockerfile", "Dockerfile", ""),
        FileRecord("LICENSE", "LICENSE", ""),
        FileRecord("CHANGELOG.md", "CHANGELOG.md", ".md"),
        FileRecord("uv.lock", "uv.lock", ".lock"),
        FileRecord("pyproject.toml", "pyproject.toml", ".toml"),
    ]
    langs = [LanguageStats(name="Python", files=2, code_lines=100, percentage=100.0)]
    deps = DependencyAnalysis(
        declared_dependencies=[
            DependencyInfo(
                name="fastapi", constraint=">=0.110", dep_type="direct", ecosystem="Python"
            ),
        ]
    )

    fp = analyze_project_fingerprint(proj, files, langs, deps)
    assert "Python" in fp.primary_languages
    assert "FastAPI" in fp.frameworks
    assert "uv" in fp.package_managers
    assert "Hatch / hatchling" in fp.build_tools
    assert "pytest" in fp.test_frameworks
    assert "Ruff" in fp.linters
    assert "mypy" in fp.type_checkers
    assert "GitHub Actions" in fp.ci_cd_systems
    assert "Docker" in fp.container_tools
    assert "src-layout" in fp.conventions
    assert len(fp.evidence) >= 8

"""Tests for Feature Groups F, G, H, I and all 23 CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpx.ai import (
    CompositeCredentialProvider,
    CredentialProvider,
    EnvCredentialProvider,
    KeypoolCredentialProvider,
    run_ai_insights,
)
from rpx.cli import main
from rpx.explore import run_interactive_explorer
from rpx.reporters.terminal import TerminalReporter
from rpx.scanner import ProjectScanner
from rpx.watch import collect_workspace_state, detect_workspace_changes


def test_all_cli_subcommands_end_to_end(
    temp_git_project: Path, tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("RPX_DATA_DIR", str(tmp_path / "rpx_data"))
    monkeypatch.setenv("RPX_CONFIG_DIR", str(tmp_path / "rpx_cfg"))

    proj_str = str(temp_git_project)

    # 1. summary
    main(["summary", proj_str, "--no-color"])
    out = capsys.readouterr().out
    assert "EXECUTIVE REPOSITORY SUMMARY" in out

    main(["summary", proj_str, "--json"])
    out_json = json.loads(capsys.readouterr().out)
    assert "metrics" in out_json

    # 2. tree
    main(["tree", proj_str, "--depth", "2", "--no-color"])
    assert "PROJECT STRUCTURE" in capsys.readouterr().out

    # 3. languages
    main(["languages", proj_str, "--no-color"])
    assert "PROGRAMMING LANGUAGE DISTRIBUTION" in capsys.readouterr().out

    main(["languages", proj_str, "--csv"])
    assert "Language,Files,Code Lines" in capsys.readouterr().out

    # 4. dependencies
    main(["dependencies", proj_str, "--no-color"])
    assert "DEPENDENCY & PACKAGE ANALYSIS" in capsys.readouterr().out

    # 5. complexity
    main(["complexity", proj_str, "--no-color"])
    assert "CODE COMPLEXITY" in capsys.readouterr().out

    main(["complexity", proj_str, "--file", "main.py", "--no-color"])
    assert "FILE COMPLEXITY" in capsys.readouterr().out

    main(["complexity", proj_str, "--csv"])
    assert "Cyclomatic Complexity" in capsys.readouterr().out

    # 6. graph
    main(["graph", proj_str, "--no-color"])
    assert "INTERNAL DEPENDENCY GRAPH" in capsys.readouterr().out

    main(["graph", proj_str, "--format", "mermaid"])
    assert "flowchart LR" in capsys.readouterr().out

    main(["graph", proj_str, "--format", "json"])
    g_json = json.loads(capsys.readouterr().out)
    assert "modules" in g_json

    # 7. debt
    main(["debt", proj_str, "--no-color"])
    assert "TECHNICAL DEBT" in capsys.readouterr().out

    main(["debt", proj_str, "--export", "json"])
    d_json = json.loads(capsys.readouterr().out)
    assert "total_items" in d_json

    # 8. security
    main(["security", proj_str, "--no-color"])
    assert "SECURITY HYGIENE" in capsys.readouterr().out

    main(["security", proj_str, "--csv"])
    assert "Rule ID,Severity" in capsys.readouterr().out

    # 9. git & subcommands (contributors, churn, hotspots, branches)
    main(["git", proj_str, "--no-color"])
    assert "GIT REPOSITORY ANALYTICS" in capsys.readouterr().out

    main(["git", "contributors", proj_str, "--no-color"])
    assert "GIT CONTRIBUTORS" in capsys.readouterr().out

    main(["git", "churn", proj_str, "--no-color"])
    assert "GIT FILE CHURN" in capsys.readouterr().out

    main(["git", "hotspots", proj_str, "--no-color"])
    assert "GIT ENGINEERING HOTSPOTS" in capsys.readouterr().out

    main(["git", "branches", proj_str, "--no-color"])
    assert "GIT BRANCHES" in capsys.readouterr().out

    # 10. health
    main(["health", proj_str, "--no-color"])
    assert "PROJECT HEALTH" in capsys.readouterr().out

    # 11. monorepo
    main(["monorepo", proj_str, "--no-color"])
    assert "MONOREPO & WORKSPACE ANALYSIS" in capsys.readouterr().out

    # 12. snapshot, history, compare
    main(["snapshot", "create", proj_str, "--label", "baseline"])
    assert "Saved snapshot" in capsys.readouterr().out

    main(["history", proj_str, "--no-color"])
    assert "REPOSITORY SNAPSHOT HISTORY" in capsys.readouterr().out

    main(["compare", proj_str, "--against", "baseline", "--no-color"])
    assert "COMPARISON" in capsys.readouterr().out

    main(["compare", proj_str, "--against", "baseline", "--format", "csv"])
    assert "Metric," in capsys.readouterr().out

    # Compare two directories directly
    other_proj = tmp_path / "other_proj"
    other_proj.mkdir()
    (other_proj / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    main(["compare", proj_str, str(other_proj), "--format", "json"])
    comp_data = json.loads(capsys.readouterr().out)
    assert "metrics" in comp_data

    # 13. report (HTML, Mermaid, JSON, CSV)
    html_file = tmp_path / "out.html"
    main(["report", proj_str, "--format", "html", "--output", str(html_file)])
    capsys.readouterr()
    assert html_file.is_file()
    html_text = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert "Project Health Breakdown" in html_text

    mmd_file = tmp_path / "out.mmd"
    main(["report", proj_str, "--format", "mermaid", "--output", str(mmd_file)])
    capsys.readouterr()
    assert mmd_file.is_file()
    assert "flowchart LR" in mmd_file.read_text(encoding="utf-8")

    # 14. context (Markdown & JSON)
    main(["context", proj_str, "--format", "markdown"])
    ctx_md = capsys.readouterr().out
    assert "# Repository Context:" in ctx_md
    assert "## 3. Architecture & Module Structure" in ctx_md

    main(["context", proj_str, "--format", "json"])
    ctx_js = json.loads(capsys.readouterr().out)
    assert "fingerprint" in ctx_js

    # 15. explore (--non-interactive)
    main(["explore", proj_str, "--non-interactive", "--no-color"])
    exp_out = capsys.readouterr().out
    assert "EXECUTIVE REPOSITORY SUMMARY" in exp_out

    # 16. watch (--cycles 1)
    main(
        [
            "watch",
            proj_str,
            "--interval",
            "0.01",
            "--debounce",
            "0.01",
            "--cycles",
            "1",
            "--no-color",
        ]
    )
    watch_out = capsys.readouterr().out
    assert "Watching" in watch_out

    # 17. ci (passing and failing gates)
    main(["ci", proj_str, "--min-health", "10", "--format", "text"])
    ci_out = capsys.readouterr().out
    assert "PASSED" in ci_out

    with pytest.raises(SystemExit) as exc:
        main(["ci", proj_str, "--min-health", "100", "--format", "json"])
    assert exc.value.code == 1
    capsys.readouterr()

    # 18. cache status & clear
    main(["cache", "status", proj_str])
    assert "RPX Incremental Scan Cache Status" in capsys.readouterr().out

    main(["cache", "clear", proj_str])
    assert "Cleared" in capsys.readouterr().out

    # 19. config check & path
    main(["config", "check", proj_str])
    assert "Configuration is valid" in capsys.readouterr().out

    main(["config", "path", proj_str])
    assert "RPX Configuration & Data Paths" in capsys.readouterr().out

    # 20. ai (--offline)
    main(["ai", proj_str, "--offline", "--no-color"])
    ai_out = capsys.readouterr().out
    assert "RPX AI INTELLIGENCE" in ai_out

    # 21. scan flags (--full, --explain-ignored, --complexity, --debt, --security, --graph, --monorepo)
    main(
        [
            "scan",
            proj_str,
            "--full",
            "--complexity",
            "--debt",
            "--security",
            "--graph",
            "--monorepo",
            "--no-color",
        ]
    )
    scan_flags_out = capsys.readouterr().out
    assert "CODE COMPLEXITY" in scan_flags_out
    assert "TECHNICAL DEBT" in scan_flags_out
    assert "SECURITY HYGIENE" in scan_flags_out


def test_ai_credential_providers_and_fallback(
    temp_git_project: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    env_cred = EnvCredentialProvider()
    assert env_cred.get_api_key("groq") is None

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_dummy_key")
    assert env_cred.get_api_key("groq") == "gsk_test_dummy_key"

    kp_cred = KeypoolCredentialProvider(enabled=False)
    assert kp_cred.get_api_key("groq") is None

    comp_cred = CompositeCredentialProvider([env_cred, kp_cred])
    assert comp_cred.get_api_key("groq") == "gsk_test_dummy_key"

    # When no credentials exist, run_ai_insights falls back to local deterministic synthesis
    class EmptyCreds(CredentialProvider):
        def get_api_key(self, provider_name: str) -> str | None:
            return None

    res = ProjectScanner(temp_git_project).scan()
    prov, text = run_ai_insights(res, cred_provider=EmptyCreds())
    assert prov == "local-fallback"
    assert "Offline Architectural & Engineering Synthesis" in text


def test_watch_change_detection(tmp_path: Path):
    proj = tmp_path / "w_proj"
    proj.mkdir()
    f1 = proj / "mod.py"
    f1.write_text("x = 1\n", encoding="utf-8")

    scanner = ProjectScanner(proj)
    st1 = collect_workspace_state(proj, scanner.ignore_manager)
    assert "mod.py" in st1

    f1.write_text("x = 2\ny = 3\n", encoding="utf-8")
    (proj / "new.py").write_text("z = 4\n", encoding="utf-8")
    st2 = collect_workspace_state(proj, scanner.ignore_manager)

    changes = detect_workspace_changes(st1, st2)
    assert "mod.py" in changes
    assert "new.py" in changes


def test_interactive_explorer_simulated_tty(
    temp_git_project: Path, monkeypatch: pytest.MonkeyPatch
):
    res = ProjectScanner(temp_git_project).scan()
    reporter = TerminalReporter(no_color=True)

    # Simulate TTY and feed sequence of choices
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    choices = iter(["1", "2", "3", "4", "5", "6", "7", "8", "9", "q"])
    monkeypatch.setattr(reporter.console, "input", lambda prompt="": next(choices))

    run_interactive_explorer(res, reporter, non_interactive=False)

"""Tests for Feature Group A: Incremental scanning, caching, snapshots, comparison, monorepo, ignore explainability, and coverage."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from rpx.analyzers.compare import compare_scan_results, compare_snapshot_dicts
from rpx.cache import clear_cache, get_cache_status
from rpx.config import check_config, get_config_paths
from rpx.exceptions import SnapshotError
from rpx.scanner import ProjectScanner
from rpx.snapshots import (
    clean_snapshots,
    get_snapshot,
    list_snapshots,
    save_snapshot,
)
from rpx.utils.ignore import IgnoreManager


def test_incremental_scan_and_cache_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "rpx_data"
    monkeypatch.setenv("RPX_DATA_DIR", str(data_dir))

    proj = tmp_path / "sample_repo"
    proj.mkdir()
    (proj / "a.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (proj / "b.py").write_text("def beta():\n    return 2\n", encoding="utf-8")

    # 1. Cold scan
    scanner1 = ProjectScanner(proj, use_cache=True)
    res1 = scanner1.scan()
    assert res1.cache_stats.enabled is True
    assert res1.cache_stats.is_incremental is False
    assert res1.cache_stats.misses >= 2
    assert res1.cache_stats.hits == 0

    # 2. Warm incremental scan (no changes)
    scanner2 = ProjectScanner(proj, use_cache=True)
    res2 = scanner2.scan()
    assert res2.cache_stats.enabled is True
    assert res2.cache_stats.is_incremental is True
    assert res2.cache_stats.hits == 2
    assert res2.cache_stats.misses == 0
    assert res2.loc.total_code == res1.loc.total_code

    # 3. Rename b.py -> b_renamed.py, modify a.py, add c.py
    time.sleep(0.02)
    (proj / "b.py").rename(proj / "b_renamed.py")
    (proj / "a.py").write_text("def alpha():\n    x = 10\n    return x + 1\n", encoding="utf-8")
    (proj / "c.py").write_text("def gamma():\n    return 3\n", encoding="utf-8")

    scanner3 = ProjectScanner(proj, use_cache=True)
    res3 = scanner3.scan()
    assert res3.cache_stats.modified >= 1
    assert res3.cache_stats.renamed == 1
    assert res3.cache_stats.added == 1

    # 4. Force full scan bypasses cache
    scanner4 = ProjectScanner(proj, use_cache=True, force_full=True)
    res4 = scanner4.scan()
    assert res4.cache_stats.hits == 0
    assert res4.cache_stats.misses >= 3

    # 5. Cache status and clear
    st = get_cache_status(proj)
    assert st["current_project_cached"] is True
    assert st["total_cache_files"] >= 1

    cleared = clear_cache(proj)
    assert cleared == 1
    st_after = get_cache_status(proj)
    assert st_after["current_project_cached"] is False


def test_snapshots_and_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RPX_DATA_DIR", str(tmp_path / "rpx_data"))

    proj = tmp_path / "comp_repo"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "comp_repo"\ndependencies = ["rich>=13.0"]\n',
        encoding="utf-8",
    )
    (proj / "main.py").write_text("def run():\n    return 42\n", encoding="utf-8")

    res_v1 = ProjectScanner(proj).scan()
    snap1 = save_snapshot(res_v1, label="v1", project_root=proj)
    assert snap1["label"] == "v1"

    # Modify project for v2
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "comp_repo"\ndependencies = ["typer>=0.12", "pydantic>=2.0"]\n',
        encoding="utf-8",
    )
    (proj / "main.py").write_text(
        "def run(x):\n    if x > 0:\n        return x\n    return 0\n",
        encoding="utf-8",
    )
    (proj / "extra.py").write_text(
        "# TODO: refactor\ndef helper():\n    return 1\n", encoding="utf-8"
    )

    res_v2 = ProjectScanner(proj).scan()
    snap2 = save_snapshot(res_v2, label="v2", project_root=proj)

    snaps = list_snapshots(proj)
    assert len(snaps) == 2

    loaded_v1 = get_snapshot(proj, "v1")
    assert loaded_v1["snapshot_id"] == snap1["snapshot_id"]

    diff = compare_snapshot_dicts(loaded_v1, snap2)
    assert diff.metrics["total_files"]["delta"] == 1
    assert "typer" in diff.dependencies_added
    assert "rich" in diff.dependencies_removed

    # Direct ScanResult comparison
    direct_diff = compare_scan_results(res_v1, res_v2, label_a="Before", label_b="After")
    assert direct_diff.metrics["code_lines"]["delta"] > 0

    # Clean snapshots keeping 1
    removed = clean_snapshots(proj, keep_last=1)
    assert removed == 1
    assert len(list_snapshots(proj)) == 1

    with pytest.raises(SnapshotError):
        get_snapshot(proj, "non_existent_snapshot_id")


def test_monorepo_detection_and_package_scoping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RPX_DATA_DIR", str(tmp_path / "rpx_data"))

    mono = tmp_path / "workspace_repo"
    mono.mkdir()
    (mono / "turbo.json").write_text('{"pipeline": {}}', encoding="utf-8")
    (mono / "package.json").write_text(
        '{"name": "root", "private": true, "workspaces": ["packages/*"]}',
        encoding="utf-8",
    )

    pkg_ui = mono / "packages" / "ui"
    pkg_ui.mkdir(parents=True)
    (pkg_ui / "package.json").write_text(
        '{"name": "@acme/ui", "dependencies": {"@acme/utils": "workspace:*", "react": "^18.0.0"}}',
        encoding="utf-8",
    )
    (pkg_ui / "button.tsx").write_text(
        "export function Button() {\n  return <button>Click</button>;\n}\n",
        encoding="utf-8",
    )

    pkg_utils = mono / "packages" / "utils"
    pkg_utils.mkdir(parents=True)
    (pkg_utils / "package.json").write_text(
        '{"name": "@acme/utils", "dependencies": {"lodash": "^4.17.21"}}',
        encoding="utf-8",
    )
    (pkg_utils / "format.ts").write_text(
        "export function fmt(s: string): string {\n  return s.trim();\n}\n",
        encoding="utf-8",
    )

    res = ProjectScanner(mono).scan()
    assert res.monorepo.is_monorepo is True
    assert "Turborepo" in res.monorepo.workspace_tools
    assert "npm Workspaces" in res.monorepo.workspace_tools
    assert len(res.monorepo.packages) == 2
    assert ("@acme/ui", "@acme/utils") in res.monorepo.package_relationships

    # Scoped package scan
    scoped_res = ProjectScanner(mono, package_filter="@acme/ui").scan()
    assert scoped_res.files.source_files == 1


def test_ignore_explainability_and_dockerignore(tmp_path: Path):
    proj = tmp_path / "ignore_test"
    proj.mkdir()
    (proj / ".gitignore").write_text("*.secret\n!allowed.secret\n", encoding="utf-8")
    (proj / ".dockerignore").write_text("docker_cache/\n*.tmp\n", encoding="utf-8")
    (proj / ".rpxignore").write_text("legacy_dir/\n", encoding="utf-8")

    (proj / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (proj / "db.secret").write_text("hidden\n", encoding="utf-8")
    (proj / "allowed.secret").write_text("visible\n", encoding="utf-8")
    (proj / "scratch.tmp").write_text("temp\n", encoding="utf-8")

    mgr = IgnoreManager(proj)
    assert mgr.is_ignored(proj / "db.secret") is True
    assert mgr.is_ignored(proj / "allowed.secret") is False
    assert mgr.is_ignored(proj / "scratch.tmp") is True

    exp_secret = mgr.explain_ignored(proj / "db.secret")
    assert exp_secret is not None
    assert exp_secret.source == ".gitignore"
    assert exp_secret.pattern == "*.secret"

    exp_docker = mgr.explain_ignored(proj / "scratch.tmp")
    assert exp_docker is not None
    assert exp_docker.source == ".dockerignore"

    # Full scan with explain_ignored=True
    res = ProjectScanner(proj, explain_ignored=True).scan()
    ignored_paths = {item.path for item in res.ignored_items}
    assert "db.secret" in ignored_paths
    assert "scratch.tmp" in ignored_paths
    assert res.coverage.files_discovered >= 4
    assert res.coverage.files_ignored >= 2


def test_config_validation_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RPX_CONFIG_DIR", str(tmp_path / "global_cfg"))
    proj = tmp_path / "cfg_proj"
    proj.mkdir()
    (proj / ".rpx.toml").write_text(
        "[rpx]\nranking_limit = 15\n[rpx.complexity]\nlow_max = 4\nmedium_max = 9\nhigh_max = 18\n",
        encoding="utf-8",
    )

    ok, msgs, cfg = check_config(proj)
    assert ok is True
    assert cfg.ranking_limit == 15
    assert cfg.complexity_low_max == 4

    paths = get_config_paths(proj)
    assert paths["project_config"] == str(proj / ".rpx.toml")

    # Invalid threshold order
    (proj / ".rpx.toml").write_text(
        "[rpx.complexity]\nlow_max = 20\nmedium_max = 10\nhigh_max = 5\n",
        encoding="utf-8",
    )
    ok_bad, msgs_bad, _ = check_config(proj)
    assert ok_bad is False

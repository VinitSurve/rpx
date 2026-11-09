"""Targeted tests to maximize test coverage across analyzers, CLI, and reporters."""

import subprocess
from pathlib import Path

from rpx.analyzers.dependencies import analyze_dependencies
from rpx.analyzers.git import analyze_git
from rpx.analyzers.metadata import detect_project_root, extract_project_name
from rpx.cli import main
from rpx.models import ScanResult
from rpx.reporters.csv_report import save_csv_report


def test_dependencies_multi_ecosystem(tmp_path: Path):
    proj = tmp_path / "mega_repo"
    proj.mkdir()

    # Cargo
    (proj / "Cargo.toml").write_text(
        '[package]\nname = "rust_pkg"\n[dependencies]\nserde = "1.0"\n', encoding="utf-8"
    )
    (proj / "Cargo.lock").write_text(
        '[[package]]\nname = "serde"\nversion = "1.0.1"\n', encoding="utf-8"
    )

    # Go
    (proj / "go.mod").write_text(
        "module demo\ngo 1.20\nrequire github.com/stretchr/testify v1.8.0\n", encoding="utf-8"
    )
    (proj / "go.sum").write_text("github.com/stretchr/testify v1.8.0 h1:abc\n", encoding="utf-8")

    # PHP
    (proj / "composer.json").write_text('{"require": {"psr/log": "^1.0"}}\n', encoding="utf-8")
    (proj / "composer.lock").write_text(
        '{"packages": [{"name": "psr/log", "version": "1.0.0"}]}\n', encoding="utf-8"
    )

    # Java Maven & Gradle
    (proj / "pom.xml").write_text(
        "<project><dependencies><dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13</version></dependency></dependencies></project>\n",
        encoding="utf-8",
    )
    (proj / "build.gradle").write_text(
        'dependencies { implementation "com.google.guava:guava:30.0" }\n', encoding="utf-8"
    )

    # .NET
    (proj / "service.csproj").write_text(
        '<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.1" /></ItemGroup></Project>\n',
        encoding="utf-8",
    )

    # Dart
    (proj / "pubspec.yaml").write_text(
        "name: dart_pkg\ndependencies:\n  http: ^0.13.0\n", encoding="utf-8"
    )

    # Swift
    (proj / "Package.resolved").write_text(
        '{"pins": [{"identity": "alamofire", "state": {"version": "5.0.0"}}]}\n', encoding="utf-8"
    )

    # Python requirements & lock
    (proj / "requirements.txt").write_text("flask>=2.0.0\n", encoding="utf-8")
    (proj / "requirements-dev.txt").write_text("black\n", encoding="utf-8")
    (proj / "poetry.lock").write_text(
        '[[package]]\nname = "flask"\nversion = "2.2.0"\n', encoding="utf-8"
    )

    # Node
    (proj / "package.json").write_text('{"dependencies": {"lodash": "^4.0.0"}}\n', encoding="utf-8")
    (proj / "package-lock.json").write_text(
        '{"packages": {"node_modules/lodash": {"version": "4.17.21"}}}\n', encoding="utf-8"
    )

    analysis = analyze_dependencies(proj)
    assert "Rust" in analysis.ecosystems
    assert "Go" in analysis.ecosystems
    assert "PHP" in analysis.ecosystems
    assert "Java/Maven" in analysis.ecosystems
    assert "Java/Gradle" in analysis.ecosystems
    assert ".NET" in analysis.ecosystems
    assert "Dart/Flutter" in analysis.ecosystems
    assert "Swift" in analysis.ecosystems
    assert "Python" in analysis.ecosystems
    assert "JavaScript/TypeScript" in analysis.ecosystems
    assert analysis.direct_dependencies_count >= 8
    assert len(analysis.lock_files) >= 6


def test_git_uncommitted_changes(tmp_path: Path):
    repo = tmp_path / "dirty_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    tracked = repo / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)

    # Modify tracked
    tracked.write_text("v2\n", encoding="utf-8")
    # Add untracked
    untracked = repo / "untracked.txt"
    untracked.write_text("new\n", encoding="utf-8")

    analytics = analyze_git(repo)
    assert analytics.is_git_repo is True
    assert analytics.uncommitted_changes is True
    assert "tracked.txt" in analytics.modified_files
    assert "untracked.txt" in analytics.untracked_files


def test_metadata_extraction(tmp_path: Path):
    # Cargo name
    cargo_dir = tmp_path / "cargo_proj"
    cargo_dir.mkdir()
    (cargo_dir / "Cargo.toml").write_text('[package]\nname = "my_crate"\n', encoding="utf-8")
    assert extract_project_name(cargo_dir) == "my_crate"

    # Package.json name
    node_dir = tmp_path / "node_proj"
    node_dir.mkdir()
    (node_dir / "package.json").write_text('{"name": "my-node-pkg"}\n', encoding="utf-8")
    assert extract_project_name(node_dir) == "my-node-pkg"

    # Pyproject name
    py_dir = tmp_path / "py_proj"
    py_dir.mkdir()
    (py_dir / "pyproject.toml").write_text('[project]\nname = "my-py-pkg"\n', encoding="utf-8")
    assert extract_project_name(py_dir) == "my-py-pkg"

    # Nested detection
    sub_dir = py_dir / "src" / "deep"
    sub_dir.mkdir(parents=True)
    assert detect_project_root(sub_dir) == py_dir


def test_cli_remaining_options(temp_project: Path, tmp_path: Path, capsys):
    # --tree
    main(["--tree", str(temp_project), "--depth", "2", "--no-color"])
    captured = capsys.readouterr()
    assert "PROJECT STRUCTURE" in captured.out

    # --storage
    main(["--storage", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "STORAGE ANALYTICS" in captured.out

    # --deps
    main(["--deps", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "DEPENDENCY & PACKAGE ANALYSIS" in captured.out

    # --languages
    main(["--languages", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "PROGRAMMING LANGUAGE DISTRIBUTION" in captured.out

    # --health
    main(["--health", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "PROJECT HEALTH & CODE QUALITY" in captured.out

    # Output to file
    out_json = tmp_path / "saved_report.json"
    main([str(temp_project), "--output", str(out_json)])
    assert out_json.is_file()

    out_csv = tmp_path / "saved_report.csv"
    main([str(temp_project), "--csv", "--output", str(out_csv)])
    assert out_csv.is_file()


def test_csv_save_types(tmp_path: Path, mock_scan_result: ScanResult):
    lang_csv = tmp_path / "lang.csv"
    save_csv_report(mock_scan_result, lang_csv, table_type="languages")
    assert "Language,Files,Code Lines" in lang_csv.read_text()

    dep_csv = tmp_path / "dep.csv"
    save_csv_report(mock_scan_result, dep_csv, table_type="deps")
    assert "Package Name,Constraint" in dep_csv.read_text()

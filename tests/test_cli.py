"""Tests for CLI argument routing, options, and exit codes."""

from pathlib import Path

import pytest

from rpx.cli import main


def test_cli_version(capsys):
    main(["--version"])
    captured = capsys.readouterr()
    assert "RPX version" in captured.out


def test_cli_help(capsys):
    main(["--help"])
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "--loc" in captured.out
    assert "--json" in captured.out


def test_cli_sections(temp_project: Path, capsys):
    main(["--loc", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "LINES OF CODE (LOC) ANALYTICS" in captured.out

    main(["--files", str(temp_project), "--no-color"])
    captured = capsys.readouterr()
    assert "FILE & DIRECTORY STATISTICS" in captured.out


def test_cli_json_export(temp_project: Path, capsys):
    main(["--json", str(temp_project)])
    captured = capsys.readouterr()
    assert '"schema_version": "1.0.0"' in captured.out


def test_cli_csv_export(temp_project: Path, capsys):
    main(["--csv", str(temp_project)])
    captured = capsys.readouterr()
    assert "File,Language,Total Physical Lines" in captured.out


def test_cli_config_commands(temp_project: Path, capsys):
    main(["config", "show", str(temp_project)])
    captured = capsys.readouterr()
    assert "RPX Configuration" in captured.out

    # Init config
    main(["config", "init", str(temp_project)])
    captured = capsys.readouterr()
    assert "Created configuration file" in captured.out
    assert (temp_project / ".rpx.toml").is_file()


def test_cli_invalid_path():
    with pytest.raises(SystemExit) as exc:
        main(["/path/that/does/not/exist/99999999"])
    assert exc.value.code == 1

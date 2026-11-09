"""Final polish tests pushing coverage above 90% for core analyzers and configuration."""

from pathlib import Path

from rpx.analyzers.loc import analyze_file_loc
from rpx.cli import main
from rpx.config import init_config, load_config
from rpx.utils.filesystem import (
    get_creation_time,
    get_modification_time,
    get_safe_stat,
    read_text_lines_safely,
)
from rpx.utils.formatting import format_duration, truncate_string


def test_loc_additional_languages_and_edge_cases(tmp_path: Path):
    # Rust file with doc comments and block comments
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text(
        "//! Module level doc comment\n"
        "/// Function level doc comment\n"
        "fn compute() {\n"
        "    /* Block comment inside function */\n"
        "    let x = 42; // line comment\n"
        "}\n",
        encoding="utf-8",
    )
    floc, ind = analyze_file_loc(rs_file, "Rust")
    assert floc is not None
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 6
    assert floc.comments >= 3

    # Lua file with --[[ block comment
    lua_file = tmp_path / "script.lua"
    lua_file.write_text(
        "-- Single line comment\n--[[ Multi-line block\n     comment in Lua ]]\nlocal x = 10\n",
        encoding="utf-8",
    )
    floc, _ = analyze_file_loc(lua_file, "Lua")
    assert floc is not None
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 4
    assert floc.comments == 3

    # Empty file
    empty_file = tmp_path / "empty.py"
    empty_file.touch()
    floc, _ = analyze_file_loc(empty_file, "Python")
    assert floc is not None
    assert floc.total_physical == 0


def test_config_loading_and_init(tmp_path: Path):
    proj = tmp_path / "cfg_proj"
    proj.mkdir()

    # Init config
    cfg_file = init_config(proj)
    assert cfg_file.is_file()

    # Load config
    cfg = load_config(proj)
    assert cfg.ranking_limit == 10
    assert cfg.max_depth == 3
    assert "vendor" in cfg.exclude

    # Modify config
    cfg_file.write_text(
        "[rpx]\nranking_limit = 25\nmax_depth = 5\ninclude_ignored = true\nno_git = true\n",
        encoding="utf-8",
    )
    loaded = load_config(proj)
    assert loaded.ranking_limit == 25
    assert loaded.max_depth == 5
    assert loaded.include_ignored is True
    assert loaded.no_git is True


def test_filesystem_and_formatting_utilities(tmp_path: Path):
    # Non-existent file stat
    bad_path = tmp_path / "does_not_exist.txt"
    assert get_safe_stat(bad_path) is None
    assert get_creation_time(None) is None
    assert get_modification_time(None) is None

    # Safe reading of large or non-existent file
    lines = list(read_text_lines_safely(bad_path))
    assert len(lines) == 0

    # Duration formatting
    assert format_duration(0.0005) == "<1 ms"
    assert "ms" in format_duration(0.05)
    assert "s" in format_duration(2.5)
    assert "m" in format_duration(125.0)

    # Truncate string
    assert truncate_string("short", 10) == "short"
    assert truncate_string("this is a very long string that should be truncated", 15).endswith(
        "..."
    )


def test_cli_flags_and_save(temp_project: Path, tmp_path: Path, monkeypatch):
    # Set current working directory to temp_project
    monkeypatch.chdir(temp_project)

    # Save default json
    main(["--save", "--quiet"])
    assert (temp_project / "rpx-report.json").is_file()

    # Save default csv with force
    main(["--csv", "--save", "--force", "--quiet"])
    assert (temp_project / "rpx-report.csv").is_file()

    # Run with exclusions and top ranking
    main(["--top", "5", "--exclude", "tests,docs", "--no-deps", "--no-git", "--quiet"])

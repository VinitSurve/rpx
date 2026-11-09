"""Tests for language-aware lines of code (LOC) counter."""

from pathlib import Path

from rpx.analyzers.loc import analyze_file_loc


def test_loc_python_docstrings_and_comments(tmp_path: Path):
    py_file = tmp_path / "test.py"
    py_file.write_text(
        "#!/usr/bin/env python3\n"
        '"""Module docstring\n'
        "spanning multiple lines.\n"
        '"""\n'
        "\n"
        "# Standalone single comment\n"
        "def add(a, b):\n"
        "    # Function comment\n"
        "    return a + b  # Inline comment\n"
        "\n"
        "# TODO: implement multiply\n"
        "# FIXME: fix edge case\n"
        'val = """multi-line\n'
        'string assigned to variable"""\n',
        encoding="utf-8",
    )

    floc, indicators = analyze_file_loc(py_file, "Python")
    assert floc is not None
    # Verify strict mathematical reconciliation
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 14
    assert floc.blank == 2
    assert floc.comments >= 5  # shebang + 3 docstring lines + standalone comments
    assert floc.inline_comments >= 1
    assert indicators["todo"] == 1
    assert indicators["fixme"] == 1


def test_loc_c_style_block_comments(tmp_path: Path):
    c_file = tmp_path / "test.c"
    c_file.write_text(
        "/*\n"
        " * Multi-line license block\n"
        " */\n"
        "#include <stdio.h>\n"
        "\n"
        "int main() {\n"
        "    // single comment\n"
        "    int x = 10; /* inline block comment */\n"
        "    /* comment before code */ int y = 20;\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    floc, indicators = analyze_file_loc(c_file, "C")
    assert floc is not None
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 11
    assert floc.blank == 1
    assert floc.comments >= 4  # 3 block lines + 1 single comment line
    assert floc.inline_comments >= 2  # inline block comment and comment before code


def test_loc_html_comments(tmp_path: Path):
    html_file = tmp_path / "test.html"
    html_file.write_text(
        "<!DOCTYPE html>\n"
        "<!-- HTML Header Comment\n"
        "     Multi-line -->\n"
        "<html>\n"
        "  <body>\n"
        "    <!-- Single line comment -->\n"
        "    <h1>Hello</h1>\n"
        "  </body>\n"
        "</html>\n",
        encoding="utf-8",
    )

    floc, indicators = analyze_file_loc(html_file, "HTML")
    assert floc is not None
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 9
    assert floc.comments == 3  # 2 lines multi-line + 1 single line comment


def test_loc_sql_comments(tmp_path: Path):
    sql_file = tmp_path / "query.sql"
    sql_file.write_text(
        "-- Select active users\n"
        "SELECT id, name\n"
        "FROM users\n"
        "WHERE active = true; -- inline SQL comment\n"
        "\n"
        "/*\n"
        "   Block SQL comment\n"
        "*/\n"
        "DROP TABLE temp;\n",
        encoding="utf-8",
    )

    floc, indicators = analyze_file_loc(sql_file, "SQL")
    assert floc is not None
    assert floc.total_physical == floc.code + floc.comments + floc.blank
    assert floc.total_physical == 9
    assert floc.comments == 4  # 1 single line + 3 block comment lines
    assert floc.inline_comments == 1


def test_loc_debug_indicators(tmp_path: Path):
    ts_file = tmp_path / "app.ts"
    ts_file.write_text(
        'console.log("debug statement 1");\n'
        "debugger;\n"
        "const a = 1;\n"
        '// console.log("this is commented out, not code");\n'
        'console.error("error debug");\n',
        encoding="utf-8",
    )

    floc, indicators = analyze_file_loc(ts_file, "TypeScript")
    assert floc is not None
    assert indicators["debug"] == 3  # 2 console.log/error + debugger (commented out ignored)

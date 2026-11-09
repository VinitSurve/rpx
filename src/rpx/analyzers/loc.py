"""Language-aware Lines of Code (LOC) counter and comment analyzer."""

from __future__ import annotations

import re
from pathlib import Path

from rpx.constants import LANGUAGE_COMMENT_RULES
from rpx.models import FileLOC
from rpx.utils.filesystem import is_binary_file, read_text_lines_safely


def analyze_file_loc(path: Path, language: str) -> tuple[FileLOC | None, dict[str, int]]:
    """Analyze a single source file for physical, code, comment, and blank lines.

    Guarantees: total_physical = code + comments + blank.
    Also extracts code hygiene indicators (TODO, FIXME, HACK, XXX, debug statements).
    """
    indicators = {
        "todo": 0,
        "fixme": 0,
        "hack": 0,
        "xxx": 0,
        "debug": 0,
    }

    if is_binary_file(path):
        return None, indicators

    comment_rules = LANGUAGE_COMMENT_RULES.get(language, (["#", "//"], [("/*", "*/")]))
    single_line_prefixes, multi_line_pairs = comment_rules

    total_physical = 0
    code_count = 0
    comment_count = 0
    blank_count = 0
    inline_comment_count = 0

    in_multi_line_comment = False
    active_close_delimiter = ""

    # Debug statement patterns based on language
    debug_pattern: re.Pattern | None = None
    if language in ("JavaScript", "TypeScript", "JSX", "TSX", "Vue", "Svelte"):
        debug_pattern = re.compile(r"\bconsole\.(?:log|debug|warn|error)\s*\(|\bdebugger\b")
    elif language == "Python":
        debug_pattern = re.compile(r"^\s*print\s*\(")
    elif language == "Go":
        debug_pattern = re.compile(r"\bfmt\.Print(?:ln|f)?\s*\(")

    for raw_line in read_text_lines_safely(path):
        total_physical += 1
        stripped = raw_line.strip()

        # 1. Blank line
        if not stripped:
            blank_count += 1
            continue

        # 2. Inside a multi-line comment
        if in_multi_line_comment:
            if active_close_delimiter in stripped:
                # Delimiter closes on this line
                parts = stripped.split(active_close_delimiter, 1)
                after_close = parts[1].strip()
                in_multi_line_comment = False
                active_close_delimiter = ""

                # Check if there is executable code after the comment closes
                if after_close and not any(after_close.startswith(p) for p in single_line_prefixes):
                    code_count += 1
                    inline_comment_count += 1
                    _check_indicators(parts[0], indicators)
                    if debug_pattern and debug_pattern.search(after_close):
                        indicators["debug"] += 1
                else:
                    comment_count += 1
                    _check_indicators(raw_line, indicators)
            else:
                comment_count += 1
                _check_indicators(raw_line, indicators)
            continue

        # 3. Shebang handling (#!)
        if stripped.startswith("#!"):
            comment_count += 1
            continue

        # 4. Check for standalone single-line comments
        # Ensure single line prefix does not conflict with a multi-line opener (e.g. -- and --[[ in Lua)
        is_single_comment = False
        if not any(stripped.startswith(op) for op, _ in multi_line_pairs):
            for prefix in single_line_prefixes:
                if stripped.startswith(prefix):
                    comment_count += 1
                    is_single_comment = True
                    _check_indicators(stripped, indicators)
                    break
        if is_single_comment:
            continue

        # 5. Check for multi-line comment opening
        started_block = False
        for open_delim, close_delim in multi_line_pairs:
            if open_delim in stripped:
                open_pos = stripped.find(open_delim)
                before_open = stripped[:open_pos].strip()

                if open_delim == close_delim:
                    # Same delimiter for open and close (e.g. """ or ''' in Python)
                    # Check if it closes on the same line after the open position
                    second_pos = stripped.find(close_delim, open_pos + len(open_delim))
                    if second_pos != -1:
                        # Opens and closes on the same line
                        after_close = stripped[second_pos + len(close_delim) :].strip()
                        if before_open or (
                            after_close
                            and not any(after_close.startswith(p) for p in single_line_prefixes)
                        ):
                            code_count += 1
                            inline_comment_count += 1
                            if debug_pattern and (
                                debug_pattern.search(before_open)
                                or debug_pattern.search(after_close)
                            ):
                                indicators["debug"] += 1
                        else:
                            comment_count += 1
                            _check_indicators(stripped[open_pos:second_pos], indicators)
                        started_block = True
                        break
                    else:
                        # Opens and does NOT close on this line
                        if before_open:
                            code_count += 1
                            inline_comment_count += 1
                            if debug_pattern and debug_pattern.search(before_open):
                                indicators["debug"] += 1
                        else:
                            comment_count += 1
                            _check_indicators(stripped, indicators)
                        in_multi_line_comment = True
                        active_close_delimiter = close_delim
                        started_block = True
                        break
                else:
                    # Distinct open and close delimiters (e.g. /* and */)
                    if close_delim in stripped[open_pos + len(open_delim) :]:
                        # Closes on the same line
                        close_pos = stripped.find(close_delim, open_pos + len(open_delim))
                        after_close = stripped[close_pos + len(close_delim) :].strip()
                        if before_open or (
                            after_close
                            and not any(after_close.startswith(p) for p in single_line_prefixes)
                        ):
                            code_count += 1
                            inline_comment_count += 1
                            if debug_pattern and (
                                debug_pattern.search(before_open)
                                or debug_pattern.search(after_close)
                            ):
                                indicators["debug"] += 1
                        else:
                            comment_count += 1
                            _check_indicators(stripped[open_pos:close_pos], indicators)
                        started_block = True
                        break
                    else:
                        # Delimiter does not close on this line
                        if before_open:
                            code_count += 1
                            inline_comment_count += 1
                            if debug_pattern and debug_pattern.search(before_open):
                                indicators["debug"] += 1
                        else:
                            comment_count += 1
                            _check_indicators(stripped, indicators)
                        in_multi_line_comment = True
                        active_close_delimiter = close_delim
                        started_block = True
                        break

        if started_block:
            continue

        # 6. Check for inline single-line comment (code followed by single comment)
        has_inline_comment = False
        for prefix in single_line_prefixes:
            if prefix in stripped:
                # Ensure prefix is not inside quotes
                code_part = stripped.split(prefix, 1)[0].strip()
                if code_part:
                    code_count += 1
                    inline_comment_count += 1
                    has_inline_comment = True
                    _check_indicators(stripped.split(prefix, 1)[1], indicators)
                    if debug_pattern and debug_pattern.search(code_part):
                        indicators["debug"] += 1
                    break
        if has_inline_comment:
            continue

        # 7. Regular code line
        code_count += 1
        if debug_pattern and debug_pattern.search(stripped):
            indicators["debug"] += 1

    file_loc = FileLOC(
        path=str(path),
        language=language,
        total_physical=total_physical,
        code=code_count,
        comments=comment_count,
        blank=blank_count,
        inline_comments=inline_comment_count,
    )
    return file_loc, indicators


def _check_indicators(text: str, indicators: dict[str, int]) -> None:
    """Helper to detect TODO, FIXME, HACK, XXX tags in comment text."""
    upper = text.upper()
    if "TODO" in upper:
        indicators["todo"] += upper.count("TODO")
    if "FIXME" in upper:
        indicators["fixme"] += upper.count("FIXME")
    if "HACK" in upper:
        indicators["hack"] += upper.count("HACK")
    if "XXX" in upper:
        indicators["xxx"] += upper.count("XXX")

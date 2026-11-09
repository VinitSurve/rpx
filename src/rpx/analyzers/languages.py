"""Programming and markup language identification and analytics."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from rpx.constants import (
    EXTENSION_LANGUAGE_MAP,
    FILENAME_LANGUAGE_MAP,
    MARKUP_AND_DATA_LANGUAGES,
)
from rpx.models import FileLOC, LanguageDistribution, LanguageStats


def detect_file_language(path: Path) -> str | None:
    """Detect language of a file from its filename or extension."""
    # 1. Exact filename match (e.g. Dockerfile, Makefile, Gemfile)
    if path.name in FILENAME_LANGUAGE_MAP:
        return FILENAME_LANGUAGE_MAP[path.name]

    # 2. Multi-extension match (e.g. .blade.php, .test.ts)
    suffix = path.suffix.lower()
    if suffix in EXTENSION_LANGUAGE_MAP:
        return EXTENSION_LANGUAGE_MAP[suffix]

    # 3. Check compound extension like .tar.gz if needed
    suffixes = "".join(path.suffixes).lower()
    if suffixes in EXTENSION_LANGUAGE_MAP:
        return EXTENSION_LANGUAGE_MAP[suffixes]

    return None


def calculate_language_distribution(
    file_locs: Sequence[FileLOC],
) -> LanguageDistribution:
    """Calculate aggregated language metrics and code line percentages."""
    languages_map: dict[str, LanguageStats] = {}

    for floc in file_locs:
        lang_name = floc.language
        is_markup = lang_name in MARKUP_AND_DATA_LANGUAGES

        if lang_name not in languages_map:
            languages_map[lang_name] = LanguageStats(
                name=lang_name,
                files=0,
                code_lines=0,
                comment_lines=0,
                blank_lines=0,
                percentage=0.0,
                is_markup_or_data=is_markup,
            )

        stat = languages_map[lang_name]
        stat.files += 1
        stat.code_lines += floc.code
        stat.comment_lines += floc.comments
        stat.blank_lines += floc.blank

    # Total programming language code lines (excluding pure markup/data)
    total_prog_code_lines = sum(
        stat.code_lines for stat in languages_map.values() if not stat.is_markup_or_data
    )

    # Fallback to all code lines if only markup/data exists
    denominator = total_prog_code_lines or sum(stat.code_lines for stat in languages_map.values())

    most_used: str | None = None
    max_code = -1

    for lang_name, stat in languages_map.items():
        if not stat.is_markup_or_data and denominator > 0:
            stat.percentage = round((stat.code_lines / denominator) * 100.0, 1)
        elif stat.is_markup_or_data and denominator > 0:
            # For markup/data, calculate percentage relative to total
            stat.percentage = round((stat.code_lines / denominator) * 100.0, 1)

        # Track most used programming language
        if not stat.is_markup_or_data and stat.code_lines > max_code:
            max_code = stat.code_lines
            most_used = lang_name

    # If no pure programming language found, pick whatever has max code lines
    if most_used is None and languages_map:
        most_used = max(languages_map.values(), key=lambda s: s.code_lines).name

    # Sort languages by code lines descending
    sorted_languages = dict(
        sorted(
            languages_map.items(),
            key=lambda item: (item[1].is_markup_or_data, -item[1].code_lines),
        )
    )

    total_source_files = sum(
        stat.files for stat in languages_map.values() if not stat.is_markup_or_data
    )

    return LanguageDistribution(
        languages=sorted_languages,
        most_used_language=most_used,
        total_detected_languages=len(languages_map),
        total_source_files=total_source_files
        if total_source_files > 0
        else sum(s.files for s in languages_map.values()),
        total_source_code_lines=total_prog_code_lines if total_prog_code_lines > 0 else denominator,
    )

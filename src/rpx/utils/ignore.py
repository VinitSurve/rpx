"""Ignore rule compilation and matching using pathspec."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pathspec

from rpx.constants import DEFAULT_EXCLUSIONS


class IgnoreManager:
    """Manages ignore rules from defaults, .gitignore, .rpxignore, and CLI exclusions."""

    def __init__(
        self,
        project_root: Path,
        cli_exclusions: Sequence[str] | None = None,
        include_ignored: bool = False,
        respect_gitignore: bool = True,
        respect_rpxignore: bool = True,
    ):
        self.project_root = project_root.resolve()
        self.include_ignored = include_ignored
        self.patterns: list[str] = []

        if not include_ignored:
            # 1. Built-in default patterns
            self.patterns.extend(DEFAULT_EXCLUSIONS)

            # 2. .gitignore
            if respect_gitignore:
                gitignore_path = self.project_root / ".gitignore"
                if gitignore_path.is_file():
                    try:
                        with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                            self.patterns.extend(
                                line.strip()
                                for line in f
                                if line.strip() and not line.startswith("#")
                            )
                    except (OSError, PermissionError):
                        pass

            # 3. .rpxignore
            if respect_rpxignore:
                rpxignore_path = self.project_root / ".rpxignore"
                if rpxignore_path.is_file():
                    try:
                        with open(rpxignore_path, "r", encoding="utf-8", errors="replace") as f:
                            self.patterns.extend(
                                line.strip()
                                for line in f
                                if line.strip() and not line.startswith("#")
                            )
                    except (OSError, PermissionError):
                        pass

            # 4. CLI exclusions
            if cli_exclusions:
                for excl in cli_exclusions:
                    # Support comma-separated values
                    for item in excl.split(","):
                        cleaned = item.strip()
                        if cleaned:
                            self.patterns.append(cleaned)

        self.spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, self.patterns
        )

    def is_ignored(self, path: Path, is_dir: bool = False) -> bool:
        """Check if a given path is ignored relative to the project root."""
        if self.include_ignored:
            return False

        try:
            rel_path = path.resolve().relative_to(self.project_root)
        except ValueError:
            # Outside project root
            return True

        rel_str = str(rel_path).replace("\\", "/")
        if is_dir:
            rel_dir_str = rel_str + "/"
            # Check directory name directly and relative path
            if rel_path.name in DEFAULT_EXCLUSIONS:
                return True
            return self.spec.match_file(rel_dir_str) or self.spec.match_file(rel_str)

        # Check filename directly against defaults (e.g. .DS_Store)
        if rel_path.name in DEFAULT_EXCLUSIONS:
            return True

        return self.spec.match_file(rel_str)

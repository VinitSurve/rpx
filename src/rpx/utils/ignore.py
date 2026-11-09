"""Ignore rule compilation, matching, and explainability using pathspec."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

import pathspec

from rpx.constants import DEFAULT_EXCLUSIONS
from rpx.models import IgnoredItem


class IgnoreManager:
    """Manages ignore rules from defaults, .gitignore, .dockerignore, .rpxignore, and CLI/config exclusions."""

    def __init__(
        self,
        project_root: Path,
        cli_exclusions: Sequence[str] | None = None,
        include_ignored: bool = False,
        respect_gitignore: bool = True,
        respect_dockerignore: bool = True,
        respect_rpxignore: bool = True,
    ):
        self.project_root = project_root.resolve()
        self.include_ignored = include_ignored
        self.patterns: list[str] = []
        # List of (source_name, pattern_str, compiled_single_spec) for explainability
        self._sourced_rules: list[tuple[str, str, pathspec.PathSpec]] = []

        if not include_ignored:
            # 1. Built-in default patterns
            for pat in DEFAULT_EXCLUSIONS:
                self._add_rule("default", pat)

            # 2. .gitignore
            if respect_gitignore:
                self._load_ignore_file(self.project_root / ".gitignore", ".gitignore")

            # 3. .dockerignore
            if respect_dockerignore:
                self._load_ignore_file(self.project_root / ".dockerignore", ".dockerignore")

            # 4. .rpxignore
            if respect_rpxignore:
                self._load_ignore_file(self.project_root / ".rpxignore", ".rpxignore")

            # 5. CLI / Config exclusions
            if cli_exclusions:
                for excl in cli_exclusions:
                    for item in excl.split(","):
                        cleaned = item.strip()
                        if cleaned:
                            self._add_rule("config/cli", cleaned)

        self.spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, self.patterns
        )

    def _add_rule(self, source: str, pattern: str) -> None:
        self.patterns.append(pattern)
        try:
            single_spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern, [pattern]
            )
            self._sourced_rules.append((source, pattern, single_spec))
        except Exception:
            pass

    def _load_ignore_file(self, filepath: Path, source_label: str) -> None:
        if filepath.is_file():
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            self._add_rule(source_label, stripped)
            except (OSError, PermissionError):
                pass

    @property
    def signature(self) -> str:
        """Deterministic hash of active ignore configuration for cache invalidation."""
        h = hashlib.sha256()
        h.update(f"include_ignored={self.include_ignored}\n".encode("utf-8"))
        for source, pat, _ in self._sourced_rules:
            h.update(f"{source}:{pat}\n".encode("utf-8"))
        return h.hexdigest()[:16]

    def is_ignored(self, path: Path, is_dir: bool = False) -> bool:
        """Check if a given path is ignored relative to the project root."""
        if self.include_ignored:
            return False

        try:
            rel_path = path.resolve().relative_to(self.project_root)
        except ValueError:
            return True

        rel_str = str(rel_path).replace("\\", "/")
        if is_dir:
            rel_dir_str = rel_str + "/"
            if rel_path.name in DEFAULT_EXCLUSIONS:
                return True
            return self.spec.match_file(rel_dir_str) or self.spec.match_file(rel_str)

        if rel_path.name in DEFAULT_EXCLUSIONS:
            return True

        return self.spec.match_file(rel_str)

    def explain_ignored(self, path: Path, is_dir: bool = False) -> IgnoredItem | None:
        """Explain why a path is ignored, returning the source and matching pattern."""
        if self.include_ignored:
            return None

        try:
            rel_path = path.resolve().relative_to(self.project_root)
        except ValueError:
            return IgnoredItem(
                path=str(path),
                reason="Outside project root",
                source="boundary",
                pattern="..",
                is_dir=is_dir,
            )

        rel_str = str(rel_path).replace("\\", "/")
        if rel_path.name in DEFAULT_EXCLUSIONS:
            return IgnoredItem(
                path=rel_str,
                reason=f"Matched built-in default exclusion '{rel_path.name}'",
                source="default",
                pattern=rel_path.name,
                is_dir=is_dir,
            )

        # Evaluate sourced rules in reverse order (last matching rule wins, unless negated)
        matched_source: str | None = None
        matched_pattern: str | None = None
        rel_dir_str = rel_str + "/" if is_dir else rel_str

        for source, pat, single_spec in self._sourced_rules:
            if pat.startswith("!"):
                # Negation pattern
                pos_spec = pathspec.PathSpec.from_lines(
                    pathspec.patterns.GitWildMatchPattern, [pat[1:]]
                )
                if pos_spec.match_file(rel_dir_str) or pos_spec.match_file(rel_str):
                    matched_source = None
                    matched_pattern = None
            else:
                if single_spec.match_file(rel_dir_str) or single_spec.match_file(rel_str):
                    matched_source = source
                    matched_pattern = pat

        if matched_source and matched_pattern:
            return IgnoredItem(
                path=rel_str,
                reason=f"Matched pattern '{matched_pattern}' from {matched_source}",
                source=matched_source,
                pattern=matched_pattern,
                is_dir=is_dir,
            )

        if self.is_ignored(path, is_dir=is_dir):
            return IgnoredItem(
                path=rel_str,
                reason="Matched composite ignore specification",
                source="ignore_spec",
                pattern="*",
                is_dir=is_dir,
            )

        return None

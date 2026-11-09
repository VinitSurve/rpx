"""Typed data models for RPX scan statistics and reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExtensionInfo:
    """Statistics for a single file extension."""

    extension: str
    count: int = 0
    total_size_bytes: int = 0


@dataclass
class FileInfo:
    """Basic file metadata."""

    path: str
    size_bytes: int
    modified_time: str
    is_source: bool = False
    is_test: bool = False
    lines_of_code: int = 0


@dataclass
class FileLOC:
    """Detailed lines-of-code statistics for an individual source file."""

    path: str
    language: str
    total_physical: int
    code: int
    comments: int
    blank: int
    inline_comments: int = 0


@dataclass
class DirectoryInfo:
    """Aggregated information for a directory."""

    path: str
    file_count: int
    total_size_bytes: int
    depth: int


@dataclass
class ProjectMetadata:
    """High-level metadata describing the project and execution environment."""

    name: str
    path: str
    project_types: list[str] = field(default_factory=list)
    created_at: str | None = None
    first_commit_date: str | None = None
    last_modified: str | None = None
    last_commit_date: str | None = None
    total_size_bytes: int = 0
    scan_duration_seconds: float = 0.0
    os_info: str = ""
    python_version: str = ""
    git_available: bool = False
    is_git_repo: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileStats:
    """Summary of files and directory distribution across the project."""

    total_files: int = 0
    total_directories: int = 0
    source_files: int = 0
    config_files: int = 0
    doc_files: int = 0
    test_files: int = 0
    asset_files: int = 0
    binary_files: int = 0
    empty_files: int = 0
    hidden_files: int = 0
    symlinks: int = 0
    unreadable_files: int = 0
    skipped_files: int = 0
    extensions: dict[str, ExtensionInfo] = field(default_factory=dict)
    top_largest_files: list[FileInfo] = field(default_factory=list)
    top_longest_files: list[FileLOC] = field(default_factory=list)
    top_recent_files: list[FileInfo] = field(default_factory=list)
    empty_file_list: list[str] = field(default_factory=list)
    unusually_large_source_files: list[FileInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DirectoryStats:
    """Summary of directory hierarchy and nesting metrics."""

    deepest_directory: str = ""
    max_depth: int = 0
    largest_directories: list[DirectoryInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LOCStats:
    """Overall lines of code and comment metrics."""

    total_physical: int = 0
    total_code: int = 0
    total_comment: int = 0
    total_blank: int = 0
    total_inline_comments: int = 0
    analyzed_files_count: int = 0
    avg_code_lines_per_file: float = 0.0
    avg_physical_lines_per_file: float = 0.0
    largest_file_by_loc: tuple[str, int] | None = None
    highest_comment_ratio_file: tuple[str, float] | None = None
    per_file_loc: list[FileLOC] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LanguageStats:
    """Aggregated statistics for a specific programming or markup language."""

    name: str
    files: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    percentage: float = 0.0
    is_markup_or_data: bool = False


@dataclass
class LanguageDistribution:
    """Breakdown of detected languages in the project."""

    languages: dict[str, LanguageStats] = field(default_factory=dict)
    most_used_language: str | None = None
    total_detected_languages: int = 0
    total_source_files: int = 0
    total_source_code_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyInfo:
    """Detailed information for a single declared, locked, or installed dependency."""

    name: str
    constraint: str = ""
    resolved_version: str | None = None
    dep_type: str = "direct"  # direct, dev, peer, optional, transitive
    ecosystem: str = ""


@dataclass
class DependencyAnalysis:
    """Project-wide dependency statistics across detected ecosystems."""

    ecosystems: list[str] = field(default_factory=list)
    manifest_files: list[str] = field(default_factory=list)
    lock_files: list[str] = field(default_factory=list)
    direct_dependencies_count: int = 0
    dev_dependencies_count: int = 0
    transitive_dependencies_count: int | None = None
    installed_dependencies_count: int | None = None
    missing_dependencies_count: int | None = None
    declared_dependencies: list[DependencyInfo] = field(default_factory=list)
    locked_dependencies: list[DependencyInfo] = field(default_factory=list)
    installed_dependencies: list[DependencyInfo] = field(default_factory=list)
    missing_dependencies: list[str] = field(default_factory=list)
    completeness_status: str = "Normal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommitInfo:
    """Information for a Git commit."""

    hash: str
    author: str
    date: str
    message: str


@dataclass
class GitAnalytics:
    """Git repository status and historical metrics."""

    git_available: bool = False
    is_git_repo: bool = False
    branch: str | None = None
    commit_hash: str | None = None
    total_commits: int = 0
    first_commit_date: str | None = None
    latest_commit_date: str | None = None
    contributors_count: int = 0
    contributors: list[tuple[str, int]] = field(default_factory=list)
    uncommitted_changes: bool = False
    modified_files: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    repository_size_bytes: int | None = None
    total_branches: int = 0
    tags_count: int = 0
    recent_commits: list[CommitInfo] = field(default_factory=list)
    commit_activity_7d: int = 0
    commit_activity_30d: int = 0
    commit_activity_90d: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthFindings:
    """Project completeness, hygiene, and code quality indicators."""

    has_readme: bool = False
    has_license: bool = False
    has_gitignore: bool = False
    has_tests: bool = False
    test_files_count: int = 0
    has_ci: bool = False
    has_docker: bool = False
    has_env_example: bool = False
    has_docs: bool = False
    has_typecheck_config: bool = False
    has_lint_config: bool = False
    has_format_config: bool = False
    todo_count: int = 0
    fixme_count: int = 0
    hack_count: int = 0
    xxx_count: int = 0
    potential_debug_statements_count: int = 0
    unusually_long_files: list[tuple[str, int]] = field(default_factory=list)
    empty_source_files: list[str] = field(default_factory=list)
    duplicate_files: list[tuple[str, str]] = field(default_factory=list)
    score: int = 0
    score_breakdown: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorageAnalytics:
    """Breakdown of disk storage usage across file categories."""

    total_project_size_bytes: int = 0
    source_size_bytes: int = 0
    docs_size_bytes: int = 0
    config_size_bytes: int = 0
    assets_size_bytes: int = 0
    largest_files: list[tuple[str, int]] = field(default_factory=list)
    largest_directories: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """Root model representing the complete scan output."""

    metadata: ProjectMetadata
    files: FileStats
    directories: DirectoryStats
    loc: LOCStats
    languages: LanguageDistribution
    dependencies: DependencyAnalysis
    git: GitAnalytics
    health: HealthFindings
    storage: StorageAnalytics
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "metadata": self.metadata.to_dict(),
            "files": self.files.to_dict(),
            "directories": self.directories.to_dict(),
            "loc": self.loc.to_dict(),
            "languages": self.languages.to_dict(),
            "dependencies": self.dependencies.to_dict(),
            "git": self.git.to_dict(),
            "health": self.health.to_dict(),
            "storage": self.storage.to_dict(),
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
        }

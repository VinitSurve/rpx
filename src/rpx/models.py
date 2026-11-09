"""Typed data models for RPX scan statistics, code intelligence, and reporting."""

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
class FileRecord:
    """Enriched internal file record used by v1.0 code intelligence analyzers."""

    relative_path: str
    name: str
    extension: str
    size_bytes: int = 0
    mtime: str = ""
    is_source: bool = False
    is_binary: bool = False
    is_test: bool = False
    language: str | None = None
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0


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
class IgnoredItem:
    """Explainability record for an ignored or skipped file/directory."""

    path: str
    reason: str = ""
    source: str = "default"  # default, .gitignore, .dockerignore, .rpxignore, config/cli
    pattern: str = ""
    is_dir: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageReport:
    """Analysis coverage and omission breakdown."""

    files_discovered: int = 0
    files_analyzed: int = 0
    files_skipped_binary: int = 0
    files_ignored: int = 0
    unsupported_file_types: int = 0
    parsing_failures: int = 0
    files_exceeding_limits: int = 0
    symlinks_skipped: int = 0
    unreadable_files: int = 0
    omission_reasons: dict[str, int] = field(default_factory=dict)
    omitted_files_sample: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CacheStats:
    """Incremental scan cache statistics."""

    enabled: bool = False
    is_incremental: bool = False
    hits: int = 0
    misses: int = 0
    added: int = 0
    modified: int = 0
    deleted: int = 0
    renamed: int = 0
    invalidated_reason: str | None = None
    cache_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    @property
    def absolute_path(self) -> str:
        return self.path

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

    @property
    def total_physical_lines(self) -> int:
        return self.total_physical

    @property
    def code_lines(self) -> int:
        return self.total_code

    @property
    def comment_lines(self) -> int:
        return self.total_comment

    @property
    def blank_lines(self) -> int:
        return self.total_blank

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


LanguageStat = LanguageStats


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
    source_file: str = "manifest"

    @property
    def version_spec(self) -> str:
        return self.constraint

    @property
    def category(self) -> str:
        return "production" if self.dep_type == "direct" else self.dep_type


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

    @property
    def dependencies(self) -> list[DependencyInfo]:
        return self.declared_dependencies

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
class FileChurnInfo:
    """Git modification and line churn metrics for a file."""

    path: str
    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    churn_score: int = 0

    @property
    def total_churn(self) -> int:
        return self.insertions + self.deletions


@dataclass
class GitHotspot:
    """File combining high modification frequency with code size/complexity."""

    path: str
    commits: int = 0
    churn_lines: int = 0
    max_complexity: int = 1
    line_count: int = 0
    risk_score: float = 0.0


@dataclass
class BranchInfo:
    """Git branch metadata and staleness indicator."""

    name: str
    last_commit_date: str = ""
    last_commit_hash: str = ""
    is_current: bool = False
    is_stale: bool = False
    days_since_commit: int = 0


@dataclass
class GitAnalytics:
    """Git repository status and historical metrics."""

    git_available: bool = False
    is_git_repo: bool = False
    is_shallow: bool = False
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
    commit_frequency_per_week: float = 0.0
    file_churn: list[FileChurnInfo] = field(default_factory=list)
    hotspots: list[GitHotspot] = field(default_factory=list)
    branches: list[BranchInfo] = field(default_factory=list)
    stale_branches_count: int = 0
    activity_by_month: dict[str, int] = field(default_factory=dict)
    change_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthDeduction:
    """Explainable deduction in the project health score."""

    category: str
    points_deducted: int
    reason: str
    is_missing_evidence: bool = False
    recommendation: str = ""


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
    category_max_scores: dict[str, int] = field(default_factory=dict)
    deductions: list[HealthDeduction] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
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
class FunctionComplexity:
    """Complexity and structural metrics for a single function or method."""

    name: str
    file_path: str
    start_line: int
    end_line: int
    line_count: int
    cyclomatic_complexity: int
    parameter_count: int = 0
    max_nesting_depth: int = 0
    is_method: bool = False
    severity: str = "low"


@dataclass
class ClassComplexity:
    """Structural metrics for a class or struct definition."""

    name: str
    file_path: str
    start_line: int
    end_line: int
    line_count: int
    method_count: int = 0


@dataclass
class FileComplexity:
    """Complexity summary for a single source file."""

    path: str
    language: str
    line_count: int = 0
    function_count: int = 0
    class_count: int = 0
    avg_complexity: float = 1.0
    max_complexity: int = 1
    max_nesting_depth: int = 0
    functions: list[FunctionComplexity] = field(default_factory=list)
    classes: list[ClassComplexity] = field(default_factory=list)
    is_long_file: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComplexityAnalysis:
    """Repository-wide code complexity metrics."""

    files_analyzed: int = 0
    total_functions: int = 0
    total_classes: int = 0
    avg_function_complexity: float = 0.0
    max_function_complexity: int = 0
    avg_function_length: float = 0.0
    max_nesting_depth: int = 0
    distribution: dict[str, int] = field(default_factory=dict)
    high_complexity_functions: list[FunctionComplexity] = field(default_factory=list)
    large_functions: list[FunctionComplexity] = field(default_factory=list)
    deep_nesting_functions: list[FunctionComplexity] = field(default_factory=list)
    many_param_functions: list[FunctionComplexity] = field(default_factory=list)
    long_files: list[FileComplexity] = field(default_factory=list)
    files: list[FileComplexity] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModuleNode:
    """Node in the internal module dependency graph."""

    name: str
    file_path: str
    language: str
    layer: str = "core"
    internal_imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    external_imports: list[str] = field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0


@dataclass
class DependencyGraph:
    """Internal module dependency graph and architectural insights."""

    total_modules: int = 0
    total_internal_edges: int = 0
    total_external_packages: int = 0
    modules: list[ModuleNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    external_packages: dict[str, list[str]] = field(default_factory=dict)
    cycles: list[list[str]] = field(default_factory=list)
    highly_coupled_modules: list[str] = field(default_factory=list)
    central_hub_modules: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    inferred_layers: dict[str, list[str]] = field(default_factory=dict)
    unexpected_layer_dependencies: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DebtItem:
    """Single technical debt finding with exact location, severity, and confidence."""

    category: str
    severity: str  # high, medium, low
    confidence: str  # high, medium, low
    file_path: str
    line_number: int | None
    message: str
    snippet: str = ""


@dataclass
class DeadCodeIndicator:
    """Heuristic indicator of potentially unused code, imports, or dependencies."""

    kind: str  # unused_import, unreferenced_module, unused_dependency, unused_function
    name: str
    file_path: str
    line_number: int | None = None
    confidence: str = "low"
    reason: str = ""


@dataclass
class DebtAnalysis:
    """Consolidated technical debt and dead-code indicators."""

    total_items: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    todo_count: int = 0
    fixme_count: int = 0
    hack_count: int = 0
    xxx_count: int = 0
    debug_statement_count: int = 0
    items: list[DebtItem] = field(default_factory=list)
    dead_code_indicators: list[DeadCodeIndicator] = field(default_factory=list)
    hotspot_files: list[dict[str, str | int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SecurityFinding:
    """Local security indicator with mandatory secret redaction."""

    category: str
    severity: str  # high, medium, low
    file_path: str
    line_number: int | None
    rule_id: str
    message: str
    redacted_snippet: str = ""
    recommendation: str = ""


@dataclass
class SecurityAnalysis:
    """Summary of local security indicators."""

    total_findings: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    committed_env_files: list[str] = field(default_factory=list)
    sensitive_files: list[str] = field(default_factory=list)
    findings: list[SecurityFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FingerprintEvidence:
    """Detected project technology, tool, or convention with supporting evidence."""

    category: str
    detected: str
    evidence: str


@dataclass
class ProjectFingerprint:
    """Collection of all fingerprinted technologies and conventions."""

    primary_languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    test_frameworks: list[str] = field(default_factory=list)
    linters: list[str] = field(default_factory=list)
    formatters: list[str] = field(default_factory=list)
    type_checkers: list[str] = field(default_factory=list)
    ci_cd_systems: list[str] = field(default_factory=list)
    container_tools: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)
    evidence: list[FingerprintEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkspacePackage:
    """Individual package or application within a monorepo/workspace."""

    name: str
    path: str
    ecosystem: str
    manifest_file: str
    file_count: int = 0
    code_lines: int = 0
    primary_language: str | None = None
    internal_dependencies: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)


@dataclass
class MonorepoAnalysis:
    """Monorepo and multi-package workspace detection results."""

    is_monorepo: bool = False
    workspace_type: str | None = None
    workspace_tools: list[str] = field(default_factory=list)
    packages: list[WorkspacePackage] = field(default_factory=list)
    package_relationships: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonDiff:
    """Structured diff between two repository snapshots or projects."""

    label_a: str
    label_b: str
    timestamp_a: str = ""
    timestamp_b: str = ""
    metrics: dict[str, dict[str, int | float]] = field(default_factory=dict)
    language_deltas: dict[str, dict[str, int | float]] = field(default_factory=dict)
    dependencies_added: list[str] = field(default_factory=list)
    dependencies_removed: list[str] = field(default_factory=list)
    directory_growth: list[dict[str, str | int]] = field(default_factory=list)
    debt_deltas: dict[str, int] = field(default_factory=dict)

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
    coverage: CoverageReport = field(default_factory=CoverageReport)
    cache_stats: CacheStats = field(default_factory=CacheStats)
    complexity: ComplexityAnalysis = field(default_factory=ComplexityAnalysis)
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    debt: DebtAnalysis = field(default_factory=DebtAnalysis)
    security: SecurityAnalysis = field(default_factory=SecurityAnalysis)
    fingerprint: ProjectFingerprint = field(default_factory=ProjectFingerprint)
    monorepo: MonorepoAnalysis = field(default_factory=MonorepoAnalysis)
    ignored_items: list[IgnoredItem] = field(default_factory=list)

    @property
    def file_stats(self) -> FileStats:
        return self.files

    @property
    def loc_stats(self) -> LOCStats:
        return self.loc

    @property
    def directory_stats(self) -> list[DirectoryInfo]:
        return self.directories.largest_directories

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
            "coverage": self.coverage.to_dict(),
            "cache_stats": self.cache_stats.to_dict(),
            "complexity": self.complexity.to_dict(),
            "graph": self.graph.to_dict(),
            "debt": self.debt.to_dict(),
            "security": self.security.to_dict(),
            "fingerprint": self.fingerprint.to_dict(),
            "monorepo": self.monorepo.to_dict(),
            "ignored_items": [item.to_dict() for item in self.ignored_items],
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
        }

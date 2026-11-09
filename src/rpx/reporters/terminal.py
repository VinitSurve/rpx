"""Rich terminal dashboard renderer with color palettes, tables, and progress bars."""

from __future__ import annotations

import os
from pathlib import Path

from rich.box import ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rpx import __version__
from rpx.analyzers.structure import build_structure_tree
from rpx.constants import (
    COLOR_ACCENT,
    COLOR_ERROR,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_WHITE,
)
from rpx.models import ScanResult
from rpx.utils.formatting import (
    format_bytes,
    format_duration,
    format_number,
    format_percentage,
    render_horizontal_bar,
    truncate_string,
)
from rpx.utils.ignore import IgnoreManager

ASCII_LOGO = rf"""[bold {COLOR_PRIMARY}]  ____  ______  __  [/]
[bold {COLOR_PRIMARY}] |  _ \|  _ \ \/ /  [/]
[bold {COLOR_SECONDARY}] | |_) | |_) \  /   [/]
[bold {COLOR_SECONDARY}] |  _ <|  __/ /  \  [/]
[bold {COLOR_ACCENT}] |_| \_\_|   /_/\_\ [/]
[bold {COLOR_WHITE}] REPOSITORY PROJECT EXPLORER[/] [dim {COLOR_MUTED}]v{__version__}[/]"""


class TerminalReporter:
    """Renders the RPX scan results to the terminal using Rich."""

    def __init__(self, console: Console | None = None, no_color: bool = False):
        if console is not None:
            self.console = console
        else:
            self.console = Console(
                no_color=no_color or "NO_COLOR" in os.environ,
                highlight=False,
            )

    def render_dashboard(
        self,
        result: ScanResult,
        ranking_limit: int = 10,
        tree_depth: int = 3,
        show_structure: bool = False,
    ) -> None:
        """Render the complete RPX visual dashboard."""
        self.render_header(result)
        self.render_overview_cards(result)
        self.render_metadata_panel(result)
        self.render_loc_panel(result)
        self.render_language_panel(result)
        self.render_file_stats_panel(result, ranking_limit=ranking_limit)
        self.render_dependency_panel(result)
        if result.git.git_available and result.git.is_git_repo:
            self.render_git_panel(result)
        self.render_health_panel(result)
        self.render_storage_panel(result, ranking_limit=ranking_limit)
        if show_structure:
            self.render_tree_panel(result, depth=tree_depth)
        self.render_footer(result)

    def render_header(self, result: ScanResult) -> None:
        """Render ASCII banner and high-level project summary."""
        self.console.print()
        self.console.print(ASCII_LOGO)
        self.console.print()

        proj_type_str = ", ".join(result.metadata.project_types) or "General"
        header_text = Text()
        header_text.append("Project: ", style=f"bold {COLOR_MUTED}")
        header_text.append(f"{result.metadata.name}\n", style=f"bold {COLOR_PRIMARY}")
        header_text.append("Location: ", style=f"bold {COLOR_MUTED}")
        header_text.append(f"{result.metadata.path}\n", style=f"{COLOR_WHITE}")
        header_text.append("Ecosystem: ", style=f"bold {COLOR_MUTED}")
        header_text.append(f"{proj_type_str}  ", style=f"bold {COLOR_SECONDARY}")
        header_text.append("•  Scan Time: ", style=f"bold {COLOR_MUTED}")
        header_text.append(
            f"{format_duration(result.duration_seconds)}", style=f"bold {COLOR_SUCCESS}"
        )

        self.console.print(
            Panel(
                header_text,
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
                padding=(0, 1),
            )
        )
        self.console.print()

    def render_overview_cards(self, result: ScanResult) -> None:
        """Render 8 high-density metric overview cards."""
        cards = [
            self._make_metric_card(
                "Total Files", format_number(result.files.total_files), COLOR_PRIMARY
            ),
            self._make_metric_card(
                "Source Files", format_number(result.files.source_files), COLOR_ACCENT
            ),
            self._make_metric_card(
                "Directories", format_number(result.files.total_directories), COLOR_SECONDARY
            ),
            self._make_metric_card(
                "Total Lines", format_number(result.loc.total_physical), COLOR_PRIMARY
            ),
            self._make_metric_card(
                "Code Lines", format_number(result.loc.total_code), COLOR_SUCCESS
            ),
            self._make_metric_card(
                "Languages", str(result.languages.total_detected_languages), COLOR_SECONDARY
            ),
            self._make_metric_card(
                "Dependencies", str(result.dependencies.direct_dependencies_count), COLOR_WARNING
            ),
            self._make_metric_card(
                "Project Size", format_bytes(result.metadata.total_size_bytes), COLOR_WHITE
            ),
        ]
        self.console.print(Columns(cards, equal=True, expand=True))
        self.console.print()

    def _make_metric_card(self, title: str, value: str, color: str) -> Panel:
        """Helper to create a single styled metric tile."""
        t = Text()
        t.append(f"{title}\n", style=f"dim {COLOR_MUTED}")
        t.append(f"{value}", style=f"bold {color}")
        return Panel(t, box=ROUNDED, border_style="dim", padding=(0, 1))

    def render_metadata_panel(self, result: ScanResult) -> None:
        """Render project metadata table."""
        table = Table(box=SIMPLE, expand=True, show_header=False)
        table.add_column("Property", style=f"bold {COLOR_MUTED}", width=22)
        table.add_column("Value", style=COLOR_WHITE)

        table.add_row("Project Name", result.metadata.name)
        table.add_row("Absolute Path", result.metadata.path)
        table.add_row("Detected Ecosystems", ", ".join(result.metadata.project_types))
        table.add_row("Filesystem Created", result.metadata.created_at or "[dim]Unavailable[/dim]")
        table.add_row(
            "Last File Modified", result.metadata.last_modified or "[dim]Unavailable[/dim]"
        )

        if result.git.git_available and result.git.is_git_repo:
            table.add_row(
                "First Git Commit", result.metadata.first_commit_date or "[dim]Unavailable[/dim]"
            )
            table.add_row(
                "Latest Git Commit", result.metadata.last_commit_date or "[dim]Unavailable[/dim]"
            )
            table.add_row(
                "Git Branch / HEAD",
                f"{result.git.branch or 'HEAD'} ({result.git.commit_hash or 'None'})",
            )

        table.add_row("Operating System", result.metadata.os_info)
        table.add_row("Python Runtime", f"Python {result.metadata.python_version}")

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_PRIMARY}]PROJECT METADATA[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_loc_panel(self, result: ScanResult) -> None:
        """Render lines-of-code breakdown and mathematical reconciliation."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Metric", style=f"bold {COLOR_MUTED}")
        table.add_column("Count", justify="right", style=f"bold {COLOR_WHITE}")
        table.add_column("Proportion", justify="right", style=COLOR_SECONDARY)

        tot_p = max(result.loc.total_physical, 1)
        code_pct = (result.loc.total_code / tot_p) * 100
        comm_pct = (result.loc.total_comment / tot_p) * 100
        blank_pct = (result.loc.total_blank / tot_p) * 100

        table.add_row(
            "Executable Code", format_number(result.loc.total_code), format_percentage(code_pct)
        )
        table.add_row(
            "Comments & Docs", format_number(result.loc.total_comment), format_percentage(comm_pct)
        )
        table.add_row(
            "Blank Lines", format_number(result.loc.total_blank), format_percentage(blank_pct)
        )
        table.add_row("─────────────────────────", "──────────────", "──────────────")
        table.add_row(
            "[bold]Total Physical Lines[/]",
            f"[bold]{format_number(result.loc.total_physical)}[/]",
            "[bold]100.0%[/]",
        )
        table.add_row(
            "Inline Comments (Mixed)", format_number(result.loc.total_inline_comments), "—"
        )
        table.add_row("Analyzed Source Files", format_number(result.loc.analyzed_files_count), "—")
        table.add_row("Avg Code Lines / File", str(result.loc.avg_code_lines_per_file), "—")
        table.add_row("Avg Physical Lines / File", str(result.loc.avg_physical_lines_per_file), "—")

        if result.loc.largest_file_by_loc:
            fname, loc = result.loc.largest_file_by_loc
            table.add_row(
                "Largest File by LOC",
                f"{truncate_string(fname, 40)}",
                f"[bold {COLOR_WARNING}]{format_number(loc)} LOC[/]",
            )

        if result.loc.highest_comment_ratio_file:
            fname, ratio = result.loc.highest_comment_ratio_file
            table.add_row(
                "Highest Comment Ratio",
                f"{truncate_string(fname, 40)}",
                f"[bold {COLOR_SUCCESS}]{ratio}:1[/]",
            )

        # Verification tag
        reconciled = (
            result.loc.total_physical
            == result.loc.total_code + result.loc.total_comment + result.loc.total_blank
        )
        recon_text = (
            f"[{COLOR_SUCCESS}]✔ LOC counts mathematically reconciled[/]"
            if reconciled
            else f"[{COLOR_ERROR}]✘ Warning: Line mismatch[/]"
        )

        self.console.print(
            Panel(
                Group(table, Text(f"\n{recon_text}", justify="right")),
                title=f"[bold {COLOR_SUCCESS}]LINES OF CODE (LOC) ANALYTICS[/]",
                border_style=COLOR_SUCCESS,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_language_panel(self, result: ScanResult) -> None:
        """Render programming language distribution with graphical horizontal bars."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Language", style=f"bold {COLOR_WHITE}", width=18)
        table.add_column("Files", justify="right", style=f"{COLOR_MUTED}", width=8)
        table.add_column("Code Lines", justify="right", style=f"bold {COLOR_WHITE}", width=12)
        table.add_column("Distribution", style=COLOR_PRIMARY, width=22)
        table.add_column("Share", justify="right", style=f"bold {COLOR_SECONDARY}", width=8)

        # Programming languages first
        for name, stat in result.languages.languages.items():
            if not stat.is_markup_or_data:
                bar = render_horizontal_bar(stat.percentage, width=18)
                table.add_row(
                    name,
                    format_number(stat.files),
                    format_number(stat.code_lines),
                    f"[{COLOR_PRIMARY}]{bar}[/]",
                    format_percentage(stat.percentage),
                )

        # Markup & config languages section
        markup_stats = [s for s in result.languages.languages.values() if s.is_markup_or_data]
        if markup_stats:
            table.add_row("[dim]Markup & Config[/]", "", "", "", "")
            for stat in markup_stats:
                bar = render_horizontal_bar(stat.percentage, width=18)
                table.add_row(
                    f"[dim]{stat.name}[/]",
                    f"[dim]{format_number(stat.files)}[/]",
                    f"[dim]{format_number(stat.code_lines)}[/]",
                    f"[dim]{bar}[/]",
                    f"[dim]{format_percentage(stat.percentage)}[/]",
                )

        summary_text = f"Primary Language: [bold {COLOR_PRIMARY}]{result.languages.most_used_language or 'None'}[/]  •  Detected: [bold {COLOR_WHITE}]{result.languages.total_detected_languages}[/] languages"

        self.console.print(
            Panel(
                Group(table, Text(f"\n{summary_text}", justify="left")),
                title=f"[bold {COLOR_SECONDARY}]PROGRAMMING LANGUAGE DISTRIBUTION[/]",
                border_style=COLOR_SECONDARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_file_stats_panel(self, result: ScanResult, ranking_limit: int = 10) -> None:
        """Render file categorization breakdown and top extensions table."""
        # Left: file categories
        cat_table = Table(box=SIMPLE, show_header=False, expand=True)
        cat_table.add_column("Category", style=f"bold {COLOR_MUTED}")
        cat_table.add_column("Count", justify="right", style=COLOR_WHITE)

        cat_table.add_row("Source Code Files", format_number(result.files.source_files))
        cat_table.add_row("Configuration Files", format_number(result.files.config_files))
        cat_table.add_row("Documentation Files", format_number(result.files.doc_files))
        cat_table.add_row("Test Files", format_number(result.files.test_files))
        cat_table.add_row("Asset Files", format_number(result.files.asset_files))
        cat_table.add_row("Binary Files", format_number(result.files.binary_files))
        cat_table.add_row("Empty Files", format_number(result.files.empty_files))
        cat_table.add_row("Hidden Files", format_number(result.files.hidden_files))
        cat_table.add_row("Symbolic Links", format_number(result.files.symlinks))
        cat_table.add_row("Skipped / Ignored", format_number(result.files.skipped_files))
        cat_table.add_row("Unreadable Files", format_number(result.files.unreadable_files))

        # Right: top extensions
        ext_table = Table(box=SIMPLE, expand=True)
        ext_table.add_column("Extension", style=f"bold {COLOR_PRIMARY}")
        ext_table.add_column("Files", justify="right", style=COLOR_WHITE)
        ext_table.add_column("Total Size", justify="right", style=COLOR_ACCENT)

        for ext, info in list(result.files.extensions.items())[:ranking_limit]:
            ext_table.add_row(ext, format_number(info.count), format_bytes(info.total_size_bytes))

        cols = Columns(
            [
                Panel(cat_table, title="[bold]File Categories[/]", box=ROUNDED, border_style="dim"),
                Panel(
                    ext_table,
                    title=f"[bold]Top {ranking_limit} Extensions[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
            ],
            expand=True,
        )

        self.console.print(
            Panel(
                cols,
                title=f"[bold {COLOR_ACCENT}]FILE & DIRECTORY STATISTICS[/]",
                border_style=COLOR_ACCENT,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_dependency_panel(self, result: ScanResult) -> None:
        """Render multi-ecosystem dependency analysis table."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Attribute", style=f"bold {COLOR_MUTED}", width=24)
        table.add_column("Details", style=COLOR_WHITE)

        table.add_row(
            "Detected Ecosystems", ", ".join(result.dependencies.ecosystems) or "[dim]None[/dim]"
        )
        table.add_row(
            "Manifest Files", ", ".join(result.dependencies.manifest_files) or "[dim]None[/dim]"
        )
        table.add_row(
            "Lockfiles", ", ".join(result.dependencies.lock_files) or "[dim]None (Unpinned)[/dim]"
        )
        table.add_row("Direct Dependencies", str(result.dependencies.direct_dependencies_count))
        table.add_row("Dev Dependencies", str(result.dependencies.dev_dependencies_count))

        if result.dependencies.transitive_dependencies_count is not None:
            table.add_row(
                "Locked Packages (Transitive)",
                str(result.dependencies.transitive_dependencies_count),
            )

        if result.dependencies.installed_dependencies_count is not None:
            table.add_row(
                "Verified Installed (Local)", str(result.dependencies.installed_dependencies_count)
            )

        status_style = (
            COLOR_SUCCESS
            if "Complete" in result.dependencies.completeness_status
            else COLOR_WARNING
        )
        table.add_row(
            "Manifest Status", f"[{status_style}]{result.dependencies.completeness_status}[/]"
        )

        if result.dependencies.missing_dependencies:
            missing_sample = ", ".join(result.dependencies.missing_dependencies[:5])
            if len(result.dependencies.missing_dependencies) > 5:
                missing_sample += (
                    f" ... (+{len(result.dependencies.missing_dependencies) - 5} more)"
                )
            table.add_row("Missing in Lockfile/Env", f"[{COLOR_ERROR}]{missing_sample}[/]")

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_WARNING}]DEPENDENCY & PACKAGE ANALYSIS[/]",
                border_style=COLOR_WARNING,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_git_panel(self, result: ScanResult) -> None:
        """Render Git analytics, status, activity timelines, and recent commits."""
        git = result.git

        # Left: Repo details & activity
        left_table = Table(box=SIMPLE, show_header=False, expand=True)
        left_table.add_column("Property", style=f"bold {COLOR_MUTED}")
        left_table.add_column("Value", style=COLOR_WHITE)

        left_table.add_row("Current Branch", f"[bold {COLOR_PRIMARY}]{git.branch}[/]")
        left_table.add_row("HEAD Commit", git.commit_hash or "None")
        left_table.add_row("Total Commits", format_number(git.total_commits))
        left_table.add_row("Total Branches", str(git.total_branches))
        left_table.add_row("Tags", str(git.tags_count))
        left_table.add_row("Contributors", str(git.contributors_count))
        if git.repository_size_bytes is not None:
            left_table.add_row("Git Directory Size", format_bytes(git.repository_size_bytes))

        status_str = (
            f"[{COLOR_ERROR}]Dirty (Uncommitted)[/]"
            if git.uncommitted_changes
            else f"[{COLOR_SUCCESS}]Clean[/]"
        )
        left_table.add_row("Working Tree Status", status_str)
        if git.uncommitted_changes:
            chg = f"M: {len(git.modified_files)}, A: {len(git.added_files)}, D: {len(git.deleted_files)}, ?: {len(git.untracked_files)}"
            left_table.add_row("Pending Changes", chg)

        left_table.add_row("─────────────────────", "──────────────────")
        left_table.add_row(
            "Activity (Last 7d)", f"[bold {COLOR_ACCENT}]{git.commit_activity_7d} commits[/]"
        )
        left_table.add_row(
            "Activity (Last 30d)", f"[bold {COLOR_ACCENT}]{git.commit_activity_30d} commits[/]"
        )
        left_table.add_row(
            "Activity (Last 90d)", f"[bold {COLOR_ACCENT}]{git.commit_activity_90d} commits[/]"
        )

        # Right: Recent commits
        recent_table = Table(box=SIMPLE, expand=True)
        recent_table.add_column("Hash", style=f"bold {COLOR_PRIMARY}", width=8)
        recent_table.add_column("Author", style=COLOR_MUTED, width=14)
        recent_table.add_column("Date", style=COLOR_MUTED, width=10)
        recent_table.add_column("Message", style=COLOR_WHITE)

        for c in git.recent_commits:
            recent_table.add_row(
                c.hash, truncate_string(c.author, 13), c.date, truncate_string(c.message, 32)
            )

        cols = Columns(
            [
                Panel(
                    left_table,
                    title="[bold]Repository Status & Velocity[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
                Panel(
                    recent_table, title="[bold]Recent 5 Commits[/]", box=ROUNDED, border_style="dim"
                ),
            ],
            expand=True,
        )

        self.console.print(
            Panel(
                cols,
                title=f"[bold {COLOR_PRIMARY}]GIT REPOSITORY ANALYTICS[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_health_panel(self, result: ScanResult) -> None:
        """Render project health checklist, code quality indicators, and completeness score."""
        h = result.health

        # Score bar
        score_color = (
            COLOR_SUCCESS if h.score >= 80 else (COLOR_WARNING if h.score >= 50 else COLOR_ERROR)
        )
        score_bar = render_horizontal_bar(h.score, width=25)

        score_text = Text()
        score_text.append("Completeness Score: ", style=f"bold {COLOR_WHITE}")
        score_text.append(f"{h.score}/100 ", style=f"bold {score_color}")
        score_text.append(f"[{score_color}]{score_bar}[/]\n")
        score_text.append(
            "[dim]Note: Heuristic completeness metric; does not evaluate correctness or security.[/dim]\n"
        )

        # Left: Hygiene checklist
        check_table = Table(box=SIMPLE, show_header=False, expand=True)
        check_table.add_column("Check", style=f"bold {COLOR_MUTED}")
        check_table.add_column("Status", justify="right")

        def _fmt_check(ok: bool) -> str:
            return f"[{COLOR_SUCCESS}]✔ Present[/]" if ok else f"[{COLOR_ERROR}]✘ Missing[/]"

        check_table.add_row("README Documentation", _fmt_check(h.has_readme))
        check_table.add_row("License File", _fmt_check(h.has_license))
        check_table.add_row(".gitignore File", _fmt_check(h.has_gitignore))
        check_table.add_row("Test Infrastructure", _fmt_check(h.has_tests))
        check_table.add_row("CI/CD Pipeline", _fmt_check(h.has_ci))
        check_table.add_row("Container Config (Docker)", _fmt_check(h.has_docker))
        check_table.add_row("Environment Template (.env.example)", _fmt_check(h.has_env_example))
        check_table.add_row("Linter Configuration", _fmt_check(h.has_lint_config))
        check_table.add_row("Formatter Configuration", _fmt_check(h.has_format_config))
        check_table.add_row("Type-checker Config", _fmt_check(h.has_typecheck_config))

        # Right: Code indicators & score breakdown
        ind_table = Table(box=SIMPLE, show_header=False, expand=True)
        ind_table.add_column("Indicator", style=f"bold {COLOR_MUTED}")
        ind_table.add_column("Count", justify="right", style=f"bold {COLOR_WHITE}")

        ind_table.add_row("TODO Comments", str(h.todo_count))
        ind_table.add_row("FIXME Comments", str(h.fixme_count))
        ind_table.add_row("HACK Comments", str(h.hack_count))
        ind_table.add_row("XXX Comments", str(h.xxx_count))
        ind_table.add_row("Potential Debug Statements", str(h.potential_debug_statements_count))
        ind_table.add_row("Unusually Long Files (>1000 LOC)", str(len(h.unusually_long_files)))
        ind_table.add_row("Empty Source Files", str(len(h.empty_source_files)))
        ind_table.add_row("Duplicate Files Detected", str(len(h.duplicate_files)))

        ind_table.add_row("─────────────────────", "──────")
        for category, pts in h.score_breakdown.items():
            ind_table.add_row(f"[dim]{category}[/]", f"[dim]{pts} pts[/]")

        cols = Columns(
            [
                Panel(
                    check_table, title="[bold]Hygiene Checklist[/]", box=ROUNDED, border_style="dim"
                ),
                Panel(
                    ind_table,
                    title="[bold]Code Quality Indicators & Score Breakdown[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
            ],
            expand=True,
        )

        self.console.print(
            Panel(
                Group(score_text, cols),
                title=f"[bold {score_color}]PROJECT HEALTH & CODE QUALITY[/]",
                border_style=score_color,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_storage_panel(self, result: ScanResult, ranking_limit: int = 10) -> None:
        """Render storage breakdown by category and largest files."""
        # Left: Storage breakdown
        st_table = Table(box=SIMPLE, show_header=False, expand=True)
        st_table.add_column("Category", style=f"bold {COLOR_MUTED}")
        st_table.add_column("Size", justify="right", style=f"bold {COLOR_WHITE}")

        st_table.add_row("Source Code Size", format_bytes(result.storage.source_size_bytes))
        st_table.add_row("Documentation Size", format_bytes(result.storage.docs_size_bytes))
        st_table.add_row("Configuration Size", format_bytes(result.storage.config_size_bytes))
        st_table.add_row("Asset Files Size", format_bytes(result.storage.assets_size_bytes))
        st_table.add_row("─────────────────────────", "──────────────")
        st_table.add_row(
            "[bold]Total Project Size[/]",
            f"[bold {COLOR_PRIMARY}]{format_bytes(result.storage.total_project_size_bytes)}[/]",
        )

        # Right: Top largest files
        lg_table = Table(box=SIMPLE, expand=True)
        lg_table.add_column("File Path", style=COLOR_WHITE)
        lg_table.add_column("Size", justify="right", style=f"bold {COLOR_WARNING}", width=12)

        for path_str, size in result.storage.largest_files[:ranking_limit]:
            lg_table.add_row(truncate_string(path_str, 38), format_bytes(size))

        cols = Columns(
            [
                Panel(
                    st_table, title="[bold]Storage Distribution[/]", box=ROUNDED, border_style="dim"
                ),
                Panel(
                    lg_table,
                    title=f"[bold]Top {ranking_limit} Largest Files[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
            ],
            expand=True,
        )

        self.console.print(
            Panel(
                cols,
                title=f"[bold {COLOR_PRIMARY}]STORAGE ANALYTICS[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_tree_panel(self, result: ScanResult, depth: int = 3) -> None:
        """Render project directory tree."""
        ignore_mgr = IgnoreManager(Path(result.metadata.path))
        tree = build_structure_tree(
            Path(result.metadata.path), ignore_manager=ignore_mgr, max_depth=depth
        )
        self.console.print(
            Panel(
                tree,
                title=f"[bold {COLOR_PRIMARY}]PROJECT STRUCTURE (Depth: {depth})[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_footer(self, result: ScanResult) -> None:
        """Render final summary footer."""
        if result.warnings:
            warn_text = Text()
            warn_text.append("Scan Warnings:\n", style=f"bold {COLOR_WARNING}")
            for w in result.warnings[:5]:
                warn_text.append(f" • {w}\n", style=COLOR_WARNING)
            if len(result.warnings) > 5:
                warn_text.append(
                    f" • (+{len(result.warnings) - 5} more warnings)\n",
                    style=f"dim {COLOR_WARNING}",
                )
            self.console.print(Panel(warn_text, box=ROUNDED, border_style=COLOR_WARNING))
            self.console.print()

        footer_text = Text()
        footer_text.append("✔ Scan completed in ", style=f"bold {COLOR_SUCCESS}")
        footer_text.append(
            f"{format_duration(result.duration_seconds)}", style=f"bold {COLOR_WHITE}"
        )
        footer_text.append("  •  RPX version: ", style=f"bold {COLOR_MUTED}")
        footer_text.append(f"v{__version__}", style=f"bold {COLOR_PRIMARY}")
        self.console.print(footer_text)
        self.console.print()

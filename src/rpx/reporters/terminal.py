"""Rich terminal dashboard renderer with color palettes, tables, and progress bars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

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
from rpx.models import ComparisonDiff, ScanResult
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
        self.render_coverage_panel(result)
        if show_structure:
            self.render_tree_panel(result, depth=tree_depth)
        if result.ignored_items:
            self.render_ignored_items(result)
        self.render_footer(result)

    def render_summary(self, result: ScanResult) -> None:
        """Render a concise executive summary of the repository."""
        self.render_header(result)
        self.render_overview_cards(result)

        table = Table(box=SIMPLE, expand=True, show_header=False)
        table.add_column("Metric", style=f"bold {COLOR_MUTED}", width=26)
        table.add_column("Value", style=COLOR_WHITE)

        fp = result.fingerprint
        table.add_row(
            "Primary Languages",
            ", ".join(fp.primary_languages) or (result.languages.most_used_language or "None"),
        )
        if fp.frameworks:
            table.add_row("Detected Frameworks", ", ".join(fp.frameworks))
        if fp.package_managers or fp.build_tools:
            table.add_row(
                "Tooling & Build",
                ", ".join(dict.fromkeys(fp.package_managers + fp.build_tools)),
            )
        if fp.test_frameworks or fp.linters:
            table.add_row(
                "Quality & Testing",
                ", ".join(dict.fromkeys(fp.test_frameworks + fp.linters + fp.type_checkers)),
            )

        table.add_row(
            "Code Complexity",
            f"Avg CC: {result.complexity.avg_function_complexity:.2f} • Max CC: {result.complexity.max_function_complexity} • Functions: {result.complexity.total_functions}",
        )
        table.add_row(
            "Technical Debt",
            f"{result.debt.total_items} items (High: {result.debt.by_severity.get('high', 0)}, Medium: {result.debt.by_severity.get('medium', 0)}, Low: {result.debt.by_severity.get('low', 0)})",
        )
        table.add_row(
            "Security Indicators",
            f"{result.security.total_findings} findings (High: {result.security.by_severity.get('high', 0)})",
        )
        score_color = (
            COLOR_SUCCESS
            if result.health.score >= 80
            else (COLOR_WARNING if result.health.score >= 55 else COLOR_ERROR)
        )
        table.add_row(
            "Project Health Score",
            f"[bold {score_color}]{result.health.score}/100[/]",
        )
        if result.health.recommendations:
            table.add_row(
                "Top Next Step",
                f"[{COLOR_PRIMARY}]{result.health.recommendations[0]}[/]",
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_PRIMARY}]EXECUTIVE REPOSITORY SUMMARY[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.render_footer(result)

    def render_header(self, result: ScanResult) -> None:
        """Render ASCII banner and high-level project summary."""
        self.console.print()
        self.console.print(ASCII_LOGO)
        self.console.print()

        proj_type_str = ", ".join(result.metadata.project_types) or "General"
        cache_badge = ""
        if result.cache_stats.enabled:
            if result.cache_stats.is_incremental and result.cache_stats.hits > 0:
                cache_badge = f"  •  Cache: [bold {COLOR_SUCCESS}]Incremental ({result.cache_stats.hits} hits)[/]"
            else:
                cache_badge = f"  •  Cache: [dim]Cold/Full ({result.cache_stats.misses} scanned)[/]"

        header_text = Text.from_markup(
            f"[bold {COLOR_MUTED}]Project:[/] [bold {COLOR_PRIMARY}]{result.metadata.name}[/]\n"
            f"[bold {COLOR_MUTED}]Location:[/] [{COLOR_WHITE}]{result.metadata.path}[/]\n"
            f"[bold {COLOR_MUTED}]Ecosystem:[/] [bold {COLOR_SECONDARY}]{proj_type_str}[/]  "
            f"•  [bold {COLOR_MUTED}]Scan Time:[/] [bold {COLOR_SUCCESS}]{format_duration(result.duration_seconds)}[/]"
            f"{cache_badge}"
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
        """Render project metadata and fingerprinting evidence table."""
        table = Table(box=SIMPLE, expand=True, show_header=False)
        table.add_column("Property", style=f"bold {COLOR_MUTED}", width=24)
        table.add_column("Value", style=COLOR_WHITE)

        table.add_row("Project Name", result.metadata.name)
        table.add_row("Absolute Path", result.metadata.path)
        table.add_row("Detected Ecosystems", ", ".join(result.metadata.project_types))

        fp = result.fingerprint
        if fp.frameworks:
            table.add_row("Frameworks", ", ".join(fp.frameworks))
        if fp.package_managers:
            table.add_row("Package Managers", ", ".join(fp.package_managers))
        if fp.build_tools:
            table.add_row("Build Tools", ", ".join(fp.build_tools))
        if fp.test_frameworks:
            table.add_row("Test Frameworks", ", ".join(fp.test_frameworks))
        if fp.linters or fp.formatters:
            table.add_row(
                "Linters & Formatters",
                ", ".join(dict.fromkeys(fp.linters + fp.formatters)),
            )
        if fp.conventions:
            table.add_row("Conventions", ", ".join(fp.conventions))

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
                title=f"[bold {COLOR_PRIMARY}]PROJECT METADATA & FINGERPRINT[/]",
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
                Group(table, Text.from_markup(f"\n{recon_text}", justify="right")),
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
                Group(table, Text.from_markup(f"\n{summary_text}", justify="left")),
                title=f"[bold {COLOR_SECONDARY}]PROGRAMMING LANGUAGE DISTRIBUTION[/]",
                border_style=COLOR_SECONDARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_file_stats_panel(self, result: ScanResult, ranking_limit: int = 10) -> None:
        """Render file categorization breakdown and top extensions table."""
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

        # Also list declared packages if any
        dep_table = Table(box=SIMPLE, expand=True)
        dep_table.add_column("Package", style=f"bold {COLOR_PRIMARY}")
        dep_table.add_column("Constraint", style=COLOR_WHITE)
        dep_table.add_column("Type", style=COLOR_MUTED)
        dep_table.add_column("Ecosystem", style=COLOR_SECONDARY)

        for dep in result.dependencies.declared_dependencies[:20]:
            dep_table.add_row(dep.name, dep.constraint or "*", dep.dep_type, dep.ecosystem)

        body = Group(table, dep_table) if result.dependencies.declared_dependencies else table
        self.console.print(
            Panel(
                body,
                title=f"[bold {COLOR_WARNING}]DEPENDENCY & PACKAGE ANALYSIS[/]",
                border_style=COLOR_WARNING,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_complexity_panel(
        self,
        result: ScanResult,
        threshold_filter: str | None = None,
        file_filter: str | None = None,
    ) -> None:
        """Render code complexity analysis, distribution, and hotspot functions."""
        comp = result.complexity

        # If a specific file filter is requested, show per-function details for that file
        if file_filter:
            norm_filter = file_filter.replace("\\", "/")
            matched_fc = next(
                (
                    fc
                    for fc in comp.files
                    if fc.path == norm_filter or fc.path.endswith(norm_filter)
                ),
                None,
            )
            if not matched_fc:
                self.console.print(
                    f"[{COLOR_WARNING}]No complexity data found for file '{file_filter}'.[/]"
                )
                return

            f_table = Table(box=SIMPLE, expand=True)
            f_table.add_column("Function / Method", style=f"bold {COLOR_PRIMARY}")
            f_table.add_column("Lines", justify="right", style=COLOR_MUTED)
            f_table.add_column("Length", justify="right", style=COLOR_WHITE)
            f_table.add_column("Cyclomatic (CC)", justify="right", style=f"bold {COLOR_WHITE}")
            f_table.add_column("Params", justify="right", style=COLOR_MUTED)
            f_table.add_column("Nesting", justify="right", style=COLOR_SECONDARY)
            f_table.add_column("Severity", justify="center")

            for fn in matched_fc.functions:
                sev_col = (
                    COLOR_ERROR
                    if fn.severity in ("high", "critical")
                    else (COLOR_WARNING if fn.severity == "medium" else COLOR_SUCCESS)
                )
                f_table.add_row(
                    fn.name,
                    f"{fn.start_line}-{fn.end_line}",
                    str(fn.line_count),
                    str(fn.cyclomatic_complexity),
                    str(fn.parameter_count),
                    str(fn.max_nesting_depth),
                    f"[bold {sev_col}]{fn.severity.upper()}[/]",
                )

            self.console.print(
                Panel(
                    f_table,
                    title=f"[bold {COLOR_PRIMARY}]FILE COMPLEXITY: {matched_fc.path} ({matched_fc.language})[/]",
                    border_style=COLOR_PRIMARY,
                    box=ROUNDED,
                )
            )
            self.console.print()
            return

        # Summary & distribution table
        sum_table = Table(box=SIMPLE, show_header=False, expand=True)
        sum_table.add_column("Metric", style=f"bold {COLOR_MUTED}")
        sum_table.add_column("Value", justify="right", style=f"bold {COLOR_WHITE}")

        sum_table.add_row("Source Files Analyzed", format_number(comp.files_analyzed))
        sum_table.add_row("Total Functions / Methods", format_number(comp.total_functions))
        sum_table.add_row("Total Classes / Structs", format_number(comp.total_classes))
        sum_table.add_row("Average Cyclomatic Complexity", f"{comp.avg_function_complexity:.2f}")
        sum_table.add_row("Maximum Cyclomatic Complexity", str(comp.max_function_complexity))
        sum_table.add_row("Average Function Length", f"{comp.avg_function_length:.1f} lines")
        sum_table.add_row("Max Control-Flow Nesting", str(comp.max_nesting_depth))

        dist_table = Table(box=SIMPLE, expand=True)
        dist_table.add_column("Band", style=f"bold {COLOR_WHITE}")
        dist_table.add_column("Functions", justify="right", style=COLOR_WHITE)
        dist_table.add_column("Share", justify="right", style=COLOR_SECONDARY)

        tot_fn = max(1, comp.total_functions)
        for band, col in [
            ("low", COLOR_SUCCESS),
            ("medium", COLOR_WARNING),
            ("high", COLOR_ERROR),
            ("critical", COLOR_ERROR),
        ]:
            cnt = comp.distribution.get(band, 0)
            pct = (cnt / tot_fn) * 100.0
            dist_table.add_row(
                f"[bold {col}]{band.upper()}[/]",
                format_number(cnt),
                format_percentage(pct),
            )

        # Hotspot functions table
        fn_table = Table(box=SIMPLE, expand=True)
        fn_table.add_column("Function", style=f"bold {COLOR_PRIMARY}")
        fn_table.add_column("Location", style=COLOR_MUTED)
        fn_table.add_column("CC", justify="right", style=f"bold {COLOR_WARNING}")
        fn_table.add_column("Lines", justify="right", style=COLOR_WHITE)
        fn_table.add_column("Nesting", justify="right", style=COLOR_SECONDARY)
        fn_table.add_column("Params", justify="right", style=COLOR_MUTED)
        fn_table.add_column("Severity", justify="center")

        all_fns = [fn for fc in comp.files for fn in fc.functions]
        if threshold_filter:
            tf = threshold_filter.lower()
            if tf == "high":
                all_fns = [f for f in all_fns if f.severity in ("high", "critical")]
            elif tf == "medium":
                all_fns = [f for f in all_fns if f.severity in ("medium", "high", "critical")]
            elif tf == "critical":
                all_fns = [f for f in all_fns if f.severity == "critical"]

        all_fns.sort(key=lambda x: (x.cyclomatic_complexity, x.line_count), reverse=True)
        for fn in all_fns[:15]:
            sev_col = (
                COLOR_ERROR
                if fn.severity in ("high", "critical")
                else (COLOR_WARNING if fn.severity == "medium" else COLOR_SUCCESS)
            )
            fn_table.add_row(
                truncate_string(fn.name, 28),
                f"{truncate_string(fn.file_path, 30)}:{fn.start_line}",
                str(fn.cyclomatic_complexity),
                str(fn.line_count),
                str(fn.max_nesting_depth),
                str(fn.parameter_count),
                f"[bold {sev_col}]{fn.severity.upper()}[/]",
            )

        top_cols = Columns(
            [
                Panel(
                    sum_table, title="[bold]Complexity Summary[/]", box=ROUNDED, border_style="dim"
                ),
                Panel(
                    dist_table,
                    title="[bold]Complexity Distribution[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
            ],
            expand=True,
        )

        self.console.print(
            Panel(
                Group(
                    top_cols,
                    Panel(
                        fn_table,
                        title="[bold]Most Complex Functions[/]",
                        box=ROUNDED,
                        border_style="dim",
                    ),
                ),
                title=f"[bold {COLOR_PRIMARY}]CODE COMPLEXITY & STRUCTURE ANALYSIS[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_graph_panel(self, result: ScanResult) -> None:
        """Render internal module dependency graph, coupling, layers, and circular dependencies."""
        g = result.graph

        meta_table = Table(box=SIMPLE, show_header=False, expand=True)
        meta_table.add_column("Metric", style=f"bold {COLOR_MUTED}")
        meta_table.add_column("Value", justify="right", style=f"bold {COLOR_WHITE}")

        meta_table.add_row("Internal Modules", str(g.total_modules))
        meta_table.add_row("Internal Import Edges", str(g.total_internal_edges))
        meta_table.add_row("External Packages Referenced", str(g.total_external_packages))
        meta_table.add_row("Circular Dependency Cycles", str(len(g.cycles)))
        meta_table.add_row("Layer Violations", str(len(g.unexpected_layer_dependencies)))
        meta_table.add_row(
            "Detected Entry Points", ", ".join(g.entry_points[:5]) or "[dim]None[/dim]"
        )
        meta_table.add_row(
            "Central Hub Modules", ", ".join(g.central_hub_modules[:5]) or "[dim]None[/dim]"
        )

        mod_table = Table(box=SIMPLE, expand=True)
        mod_table.add_column("Module", style=f"bold {COLOR_PRIMARY}")
        mod_table.add_column("Layer", style=COLOR_SECONDARY)
        mod_table.add_column("Fan-In", justify="right", style=COLOR_SUCCESS)
        mod_table.add_column("Fan-Out", justify="right", style=COLOR_WARNING)
        mod_table.add_column("Internal Imports", style=COLOR_WHITE)

        for mod in g.modules[:15]:
            imps = ", ".join(mod.internal_imports[:4])
            if len(mod.internal_imports) > 4:
                imps += f" (+{len(mod.internal_imports) - 4})"
            mod_table.add_row(
                mod.name,
                mod.layer,
                str(mod.fan_in),
                str(mod.fan_out),
                imps or "[dim]—[/dim]",
            )

        elements: list[Any] = [meta_table, mod_table]

        if g.cycles:
            cyc_text = Text()
            cyc_text.append("\nCircular Dependencies Detected:\n", style=f"bold {COLOR_ERROR}")
            for cyc in g.cycles[:10]:
                cyc_text.append(f"  • {' -> '.join(cyc)}\n", style=COLOR_ERROR)
            elements.append(cyc_text)

        if g.unexpected_layer_dependencies:
            viol_text = Text()
            viol_text.append("\nArchitectural Layer Violations:\n", style=f"bold {COLOR_WARNING}")
            for v in g.unexpected_layer_dependencies[:8]:
                viol_text.append(
                    f"  • {v['from_module']} ({v['from_layer']}) -> {v['to_module']} ({v['to_layer']})\n",
                    style=COLOR_WARNING,
                )
            elements.append(viol_text)

        self.console.print(
            Panel(
                Group(*elements),
                title=f"[bold {COLOR_SECONDARY}]INTERNAL DEPENDENCY GRAPH & ARCHITECTURE INSIGHTS[/]",
                border_style=COLOR_SECONDARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_debt_panel(
        self,
        result: ScanResult,
        severity_filter: str | None = None,
        category_filter: str | None = None,
    ) -> None:
        """Render technical debt items, hotspots, and dead-code heuristic indicators."""
        debt = result.debt

        items = debt.items
        if severity_filter:
            sf = severity_filter.lower()
            items = [i for i in items if i.severity == sf]
        if category_filter:
            cf = category_filter.lower()
            items = [i for i in items if cf in i.category.lower()]

        sum_text = Text.from_markup(
            f"Total Debt Items: [bold {COLOR_WHITE}]{debt.total_items}[/]  •  "
            f"High: [bold {COLOR_ERROR}]{debt.by_severity.get('high', 0)}[/]  •  "
            f"Medium: [bold {COLOR_WARNING}]{debt.by_severity.get('medium', 0)}[/]  •  "
            f"Low: [bold {COLOR_SUCCESS}]{debt.by_severity.get('low', 0)}[/]  •  "
            f"Dead-Code Heuristics: [bold {COLOR_SECONDARY}]{len(debt.dead_code_indicators)}[/]\n"
        )

        item_table = Table(box=SIMPLE, expand=True)
        item_table.add_column("Severity", width=10)
        item_table.add_column("Category", style=COLOR_SECONDARY, width=20)
        item_table.add_column("Location", style=f"bold {COLOR_PRIMARY}", width=30)
        item_table.add_column("Finding", style=COLOR_WHITE)

        for item in items[:25]:
            scol = (
                COLOR_ERROR
                if item.severity == "high"
                else (COLOR_WARNING if item.severity == "medium" else COLOR_SUCCESS)
            )
            loc = f"{item.file_path}:{item.line_number}" if item.line_number else item.file_path
            item_table.add_row(
                f"[bold {scol}]{item.severity.upper()}[/]",
                item.category,
                truncate_string(loc, 30),
                truncate_string(item.message, 60),
            )

        group_items: list[Any] = [sum_text, item_table]

        if debt.dead_code_indicators:
            dc_table = Table(box=SIMPLE, expand=True)
            dc_table.add_column("Kind", style=COLOR_SECONDARY, width=20)
            dc_table.add_column("Symbol / Target", style=f"bold {COLOR_PRIMARY}", width=24)
            dc_table.add_column("Location", style=COLOR_MUTED, width=26)
            dc_table.add_column("Confidence", width=10)
            dc_table.add_column("Heuristic Reason", style=COLOR_WHITE)

            for dc in debt.dead_code_indicators[:15]:
                loc = f"{dc.file_path}:{dc.line_number}" if dc.line_number else dc.file_path
                dc_table.add_row(
                    dc.kind,
                    dc.name,
                    truncate_string(loc, 26),
                    dc.confidence.upper(),
                    truncate_string(dc.reason, 52),
                )
            group_items.append(
                Panel(
                    dc_table,
                    title="[bold]Heuristic Dead-Code Indicators (Review Before Action)[/]",
                    box=ROUNDED,
                    border_style="dim",
                )
            )

        self.console.print(
            Panel(
                Group(*group_items),
                title=f"[bold {COLOR_WARNING}]TECHNICAL DEBT & DEAD-CODE ANALYSIS[/]",
                border_style=COLOR_WARNING,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_security_panel(
        self,
        result: ScanResult,
        severity_filter: str | None = None,
    ) -> None:
        """Render local security hygiene indicators with mandatory redaction."""
        sec = result.security
        findings = sec.findings
        if severity_filter:
            sf = severity_filter.lower()
            findings = [f for f in findings if f.severity == sf]

        header = Text.from_markup(
            f"Total Findings: [bold {COLOR_WHITE}]{sec.total_findings}[/]  •  "
            f"High: [bold {COLOR_ERROR}]{sec.by_severity.get('high', 0)}[/]  •  "
            f"Medium: [bold {COLOR_WARNING}]{sec.by_severity.get('medium', 0)}[/]  •  "
            f"Low: [bold {COLOR_SUCCESS}]{sec.by_severity.get('low', 0)}[/]\n"
            f"[dim]Disclaimer: Local heuristic security indicators only; secrets are automatically redacted.[/dim]\n"
        )

        if not findings:
            self.console.print(
                Panel(
                    Group(
                        header,
                        Text.from_markup(
                            f"[{COLOR_SUCCESS}]✔ No matching security risk indicators found.[/]"
                        ),
                    ),
                    title=f"[bold {COLOR_SUCCESS}]SECURITY HYGIENE INDICATORS[/]",
                    border_style=COLOR_SUCCESS,
                    box=ROUNDED,
                )
            )
            self.console.print()
            return

        table = Table(box=SIMPLE, expand=True)
        table.add_column("Rule", style=f"bold {COLOR_PRIMARY}", width=8)
        table.add_column("Severity", width=9)
        table.add_column("Location", style=COLOR_WHITE, width=28)
        table.add_column("Finding & Redacted Snippet", style=COLOR_WHITE)
        table.add_column("Recommendation", style=COLOR_MUTED, width=32)

        for item in findings[:25]:
            scol = (
                COLOR_ERROR
                if item.severity == "high"
                else (COLOR_WARNING if item.severity == "medium" else COLOR_SUCCESS)
            )
            loc = f"{item.file_path}:{item.line_number}" if item.line_number else item.file_path
            table.add_row(
                item.rule_id,
                f"[bold {scol}]{item.severity.upper()}[/]",
                truncate_string(loc, 28),
                f"{item.message}\n[dim]{truncate_string(item.redacted_snippet, 50)}[/dim]",
                truncate_string(item.recommendation, 32),
            )

        border_col = COLOR_ERROR if sec.by_severity.get("high", 0) > 0 else COLOR_WARNING
        self.console.print(
            Panel(
                Group(header, table),
                title=f"[bold {border_col}]SECURITY HYGIENE INDICATORS (REDACTED)[/]",
                border_style=border_col,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_monorepo_panel(self, result: ScanResult) -> None:
        """Render monorepo and workspace detection results."""
        mono = result.monorepo
        info = Text.from_markup(
            f"Monorepo Detected: [bold {COLOR_PRIMARY}]{'Yes' if mono.is_monorepo else 'No (Single-Package Repository)'}[/]  •  "
            f"Workspace Tooling: [bold {COLOR_SECONDARY}]{', '.join(mono.workspace_tools) or 'None'}[/]  •  "
            f"Sub-Packages: [bold {COLOR_WHITE}]{len(mono.packages)}[/]\n"
        )

        if not mono.packages:
            self.console.print(
                Panel(
                    info,
                    title=f"[bold {COLOR_PRIMARY}]MONOREPO & WORKSPACE ANALYSIS[/]",
                    border_style=COLOR_PRIMARY,
                    box=ROUNDED,
                )
            )
            self.console.print()
            return

        pkg_table = Table(box=SIMPLE, expand=True)
        pkg_table.add_column("Package Name", style=f"bold {COLOR_PRIMARY}")
        pkg_table.add_column("Path", style=COLOR_WHITE)
        pkg_table.add_column("Ecosystem", style=COLOR_SECONDARY)
        pkg_table.add_column("Primary Lang", style=COLOR_ACCENT)
        pkg_table.add_column("Files", justify="right", style=COLOR_WHITE)
        pkg_table.add_column("Code Lines", justify="right", style=f"bold {COLOR_SUCCESS}")
        pkg_table.add_column("Internal Deps", style=COLOR_WARNING)

        for wp in mono.packages:
            pkg_table.add_row(
                wp.name,
                wp.path,
                wp.ecosystem,
                wp.primary_language or "—",
                format_number(wp.file_count),
                format_number(wp.code_lines),
                ", ".join(wp.internal_dependencies) or "[dim]None[/dim]",
            )

        self.console.print(
            Panel(
                Group(info, pkg_table),
                title=f"[bold {COLOR_PRIMARY}]MONOREPO & WORKSPACE ANALYSIS[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_git_panel(self, result: ScanResult) -> None:
        """Render Git analytics, status, activity timelines, and recent commits."""
        git = result.git

        left_table = Table(box=SIMPLE, show_header=False, expand=True)
        left_table.add_column("Property", style=f"bold {COLOR_MUTED}")
        left_table.add_column("Value", style=COLOR_WHITE)

        left_table.add_row("Current Branch", f"[bold {COLOR_PRIMARY}]{git.branch}[/]")
        left_table.add_row("HEAD Commit", git.commit_hash or "None")
        left_table.add_row("Total Commits", format_number(git.total_commits))
        left_table.add_row("Commit Velocity", f"{git.commit_frequency_per_week:.2f} commits/week")
        left_table.add_row("Total Branches", str(git.total_branches))
        left_table.add_row("Tags", str(git.tags_count))
        left_table.add_row("Contributors", str(git.contributors_count))
        if git.is_shallow:
            left_table.add_row("Clone Type", f"[{COLOR_WARNING}]Shallow Clone[/]")
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

        recent_table = Table(box=SIMPLE, expand=True)
        recent_table.add_column("Hash", style=f"bold {COLOR_PRIMARY}", width=8)
        recent_table.add_column("Author", style=COLOR_MUTED, width=14)
        recent_table.add_column("Date", style=COLOR_MUTED, width=10)
        recent_table.add_column("Message", style=COLOR_WHITE)

        for c in git.recent_commits[:7]:
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
                    recent_table, title="[bold]Recent Commits[/]", box=ROUNDED, border_style="dim"
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

    def render_git_contributors(self, result: ScanResult) -> None:
        """Render Git contributors table."""
        git = result.git
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Rank", justify="right", style=COLOR_MUTED, width=6)
        table.add_column("Contributor", style=f"bold {COLOR_WHITE}")
        table.add_column("Commits", justify="right", style=f"bold {COLOR_PRIMARY}")
        table.add_column("Share", justify="right", style=COLOR_SECONDARY)

        tot = max(1, sum(cnt for _, cnt in git.contributors))
        for idx, (author, cnt) in enumerate(git.contributors[:25], start=1):
            pct = (cnt / tot) * 100.0
            table.add_row(str(idx), author, format_number(cnt), format_percentage(pct))

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_PRIMARY}]GIT CONTRIBUTORS ({git.contributors_count})[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_git_churn(self, result: ScanResult) -> None:
        """Render Git file modification frequency and line churn table."""
        git = result.git
        table = Table(box=SIMPLE, expand=True)
        table.add_column("File Path", style=f"bold {COLOR_PRIMARY}")
        table.add_column("Commits", justify="right", style=COLOR_WHITE)
        table.add_column("Insertions (+)", justify="right", style=COLOR_SUCCESS)
        table.add_column("Deletions (-)", justify="right", style=COLOR_ERROR)
        table.add_column("Churn Score", justify="right", style=f"bold {COLOR_WARNING}")

        for ch in git.file_churn[:25]:
            table.add_row(
                ch.path,
                str(ch.commits),
                f"+{format_number(ch.insertions)}",
                f"-{format_number(ch.deletions)}",
                str(ch.churn_score),
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_WARNING}]GIT FILE CHURN & MODIFICATION FREQUENCY[/]",
                border_style=COLOR_WARNING,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_git_hotspots(self, result: ScanResult) -> None:
        """Render Git hotspots combining high churn and code complexity."""
        git = result.git
        table = Table(box=SIMPLE, expand=True)
        table.add_column("File Path", style=f"bold {COLOR_PRIMARY}")
        table.add_column("Commits", justify="right", style=COLOR_WHITE)
        table.add_column("Churn Lines", justify="right", style=COLOR_SECONDARY)
        table.add_column("Max CC", justify="right", style=COLOR_WARNING)
        table.add_column("LOC", justify="right", style=COLOR_MUTED)
        table.add_column("Risk Score", justify="right", style=f"bold {COLOR_ERROR}")

        for hs in git.hotspots[:20]:
            table.add_row(
                hs.path,
                str(hs.commits),
                format_number(hs.churn_lines),
                str(hs.max_complexity),
                format_number(hs.line_count),
                f"{hs.risk_score:.1f}",
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_ERROR}]GIT ENGINEERING HOTSPOTS (CHURN × COMPLEXITY)[/]",
                border_style=COLOR_ERROR,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_git_branches(self, result: ScanResult) -> None:
        """Render Git branches and staleness status."""
        git = result.git
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Branch", style=f"bold {COLOR_PRIMARY}")
        table.add_column("HEAD", style=COLOR_MUTED)
        table.add_column("Last Commit Date", style=COLOR_WHITE)
        table.add_column("Days Inactive", justify="right", style=COLOR_SECONDARY)
        table.add_column("Status", justify="center")

        for b in git.branches:
            if b.is_current:
                status = f"[bold {COLOR_SUCCESS}]CURRENT[/]"
            elif b.is_stale:
                status = f"[bold {COLOR_WARNING}]STALE (>90d)[/]"
            else:
                status = f"[{COLOR_PRIMARY}]ACTIVE[/]"
            table.add_row(
                f"* {b.name}" if b.is_current else b.name,
                b.last_commit_hash,
                b.last_commit_date,
                str(b.days_since_commit),
                status,
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_PRIMARY}]GIT BRANCHES ({len(git.branches)} local, {git.total_branches} total)[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_health_panel(self, result: ScanResult) -> None:
        """Render 9-category project health score, explainable deductions, and recommendations."""
        h = result.health

        score_color = (
            COLOR_SUCCESS if h.score >= 80 else (COLOR_WARNING if h.score >= 50 else COLOR_ERROR)
        )
        score_bar = render_horizontal_bar(h.score, width=25)

        score_text = Text()
        score_text.append("Repository Health Score: ", style=f"bold {COLOR_WHITE}")
        score_text.append(f"{h.score}/100 ", style=f"bold {score_color}")
        score_text.append(f"[{score_color}]{score_bar}[/]\n")
        score_text.append(
            "[dim]Evaluated across 9 categories. Deductions distinguish missing evidence from defects.[/dim]\n"
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

        # Right: 9-category breakdown
        ind_table = Table(box=SIMPLE, show_header=False, expand=True)
        ind_table.add_column("Category / Metric", style=f"bold {COLOR_MUTED}")
        ind_table.add_column("Score / Count", justify="right", style=f"bold {COLOR_WHITE}")

        for category, pts in h.score_breakdown.items():
            max_pts = h.category_max_scores.get(category, 15)
            ind_table.add_row(category, f"{pts}/{max_pts} pts")

        ind_table.add_row("─────────────────────", "──────")
        ind_table.add_row(
            "TODO / FIXME / HACK", f"{h.todo_count} / {h.fixme_count} / {h.hack_count}"
        )
        ind_table.add_row("Duplicate Files", str(len(h.duplicate_files)))

        cols = Columns(
            [
                Panel(
                    check_table, title="[bold]Hygiene Checklist[/]", box=ROUNDED, border_style="dim"
                ),
                Panel(
                    ind_table,
                    title="[bold]9-Category Score Breakdown[/]",
                    box=ROUNDED,
                    border_style="dim",
                ),
            ],
            expand=True,
        )

        elements: list[Any] = [
            Text.from_markup(
                f"[bold {COLOR_WHITE}]Repository Health Score:[/] [bold {score_color}]{h.score}/100[/] [{score_color}]{score_bar}[/]\n"
                f"[dim]Evaluated across 9 categories. Deductions distinguish missing evidence from defects.[/dim]\n"
            ),
            cols,
        ]

        if h.deductions:
            ded_table = Table(box=SIMPLE, expand=True)
            ded_table.add_column("Category", style=f"bold {COLOR_PRIMARY}", width=20)
            ded_table.add_column("Pts", justify="right", style=f"bold {COLOR_ERROR}", width=5)
            ded_table.add_column("Type", style=COLOR_SECONDARY, width=16)
            ded_table.add_column("Reason", style=COLOR_WHITE)
            ded_table.add_column("Recommendation", style=COLOR_SUCCESS)

            for d in h.deductions[:10]:
                dtype = "Missing Evidence" if d.is_missing_evidence else "Defect"
                ded_table.add_row(
                    d.category,
                    f"-{d.points_deducted}",
                    dtype,
                    d.reason,
                    d.recommendation,
                )
            elements.append(
                Panel(
                    ded_table,
                    title="[bold]Explainable Deductions & Linked Recommendations[/]",
                    box=ROUNDED,
                    border_style="dim",
                )
            )

        self.console.print(
            Panel(
                Group(*elements),
                title=f"[bold {score_color}]PROJECT HEALTH & CODE QUALITY[/]",
                border_style=score_color,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_storage_panel(self, result: ScanResult, ranking_limit: int = 10) -> None:
        """Render storage breakdown by category and largest files."""
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

    def render_coverage_panel(self, result: ScanResult) -> None:
        """Render analysis coverage report showing discovered, analyzed, and omitted files."""
        cov = result.coverage
        line = Text.from_markup(
            f"Discovered: [bold {COLOR_WHITE}]{format_number(cov.files_discovered)}[/]  •  "
            f"Source Analyzed: [bold {COLOR_SUCCESS}]{format_number(cov.files_analyzed)}[/]  •  "
            f"Ignored: [bold {COLOR_MUTED}]{format_number(cov.files_ignored)}[/]  •  "
            f"Binary Skipped: [bold {COLOR_SECONDARY}]{format_number(cov.files_skipped_binary)}[/]  •  "
            f"Non-Code/Config/Docs: [bold {COLOR_ACCENT}]{format_number(cov.unsupported_file_types)}[/]  •  "
            f"Parse Failures: [bold {COLOR_ERROR if cov.parsing_failures else COLOR_MUTED}]{cov.parsing_failures}[/]"
        )
        self.console.print(
            Panel(
                line,
                title=f"[bold {COLOR_ACCENT}]ANALYSIS COVERAGE REPORT[/]",
                border_style=COLOR_ACCENT,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_ignored_items(self, result: ScanResult) -> None:
        """Render explainable ignore rules report (--explain-ignored)."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Ignored Path", style=f"bold {COLOR_PRIMARY}")
        table.add_column("Type", style=COLOR_MUTED, width=8)
        table.add_column("Source", style=COLOR_SECONDARY, width=16)
        table.add_column("Pattern", style=COLOR_WARNING, width=20)
        table.add_column("Explanation", style=COLOR_WHITE)

        for item in result.ignored_items[:50]:
            table.add_row(
                item.path,
                "dir" if item.is_dir else "file",
                item.source,
                item.pattern,
                item.reason,
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_WARNING}]EXPLAIN IGNORED PATHS ({len(result.ignored_items)} matched)[/]",
                border_style=COLOR_WARNING,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_comparison(self, diff: ComparisonDiff) -> None:
        """Render snapshot-to-snapshot or project-to-project comparison diff."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("Metric", style=f"bold {COLOR_MUTED}")
        table.add_column(diff.label_a, justify="right", style=COLOR_WHITE)
        table.add_column(diff.label_b, justify="right", style=f"bold {COLOR_WHITE}")
        table.add_column("Delta", justify="right")

        for k, vals in diff.metrics.items():
            va = vals.get("before", 0)
            vb = vals.get("after", 0)
            d = vals.get("delta", 0)
            if d > 0:
                d_str = f"[bold {COLOR_SUCCESS}]+{d}[/]"
            elif d < 0:
                d_str = f"[bold {COLOR_ERROR}]{d}[/]"
            else:
                d_str = "[dim]0[/dim]"
            table.add_row(k.replace("_", " ").title(), str(va), str(vb), d_str)

        elements: list[Any] = [table]

        if diff.language_deltas:
            lg_table = Table(box=SIMPLE, expand=True)
            lg_table.add_column("Language", style=f"bold {COLOR_PRIMARY}")
            lg_table.add_column("Before LOC", justify="right", style=COLOR_MUTED)
            lg_table.add_column("After LOC", justify="right", style=COLOR_WHITE)
            lg_table.add_column("Delta LOC", justify="right")

            for lg, lvals in diff.language_deltas.items():
                dc = lvals.get("delta_code", 0)
                dc_str = (
                    f"[{COLOR_SUCCESS}]+{dc}[/]"
                    if dc > 0
                    else (f"[{COLOR_ERROR}]{dc}[/]" if dc < 0 else "0")
                )
                lg_table.add_row(
                    lg,
                    str(lvals.get("before_code", 0)),
                    str(lvals.get("after_code", 0)),
                    dc_str,
                )
            elements.append(
                Panel(lg_table, title="[bold]Language Deltas[/]", box=ROUNDED, border_style="dim")
            )

        if diff.dependencies_added or diff.dependencies_removed:
            dep_text = Text()
            if diff.dependencies_added:
                dep_text.append(
                    f"Added Dependencies (+{len(diff.dependencies_added)}): {', '.join(diff.dependencies_added)}\n",
                    style=COLOR_SUCCESS,
                )
            if diff.dependencies_removed:
                dep_text.append(
                    f"Removed Dependencies (-{len(diff.dependencies_removed)}): {', '.join(diff.dependencies_removed)}\n",
                    style=COLOR_ERROR,
                )
            elements.append(dep_text)

        self.console.print(
            Panel(
                Group(*elements),
                title=f"[bold {COLOR_PRIMARY}]COMPARISON: {diff.label_a} vs {diff.label_b}[/]",
                border_style=COLOR_PRIMARY,
                box=ROUNDED,
            )
        )
        self.console.print()

    def render_history(self, snapshots: Sequence[dict[str, Any]]) -> None:
        """Render saved repository snapshots timeline."""
        if not snapshots:
            self.console.print(
                f"[{COLOR_WARNING}]No snapshots recorded yet. Run `rpx snapshot` to save a snapshot.[/]"
            )
            return

        table = Table(box=SIMPLE, expand=True)
        table.add_column("Snapshot ID", style=f"bold {COLOR_PRIMARY}")
        table.add_column("Label", style=COLOR_SECONDARY)
        table.add_column("Created At", style=COLOR_MUTED)
        table.add_column("Git Commit", style=COLOR_ACCENT)
        table.add_column("Files", justify="right", style=COLOR_WHITE)
        table.add_column("Code LOC", justify="right", style=f"bold {COLOR_SUCCESS}")
        table.add_column("Debt", justify="right", style=COLOR_WARNING)
        table.add_column("Health", justify="right", style=f"bold {COLOR_WHITE}")

        for s in snapshots:
            m = s.get("metrics", {})
            table.add_row(
                str(s.get("snapshot_id", "")),
                str(s.get("label", "")),
                str(s.get("created_at", ""))[:19].replace("T", " "),
                str(s.get("git_commit") or "—"),
                format_number(int(m.get("total_files", 0))),
                format_number(int(m.get("code_lines", 0))),
                str(m.get("debt_total", 0)),
                f"{m.get('health_score', 0)}/100",
            )

        self.console.print(
            Panel(
                table,
                title=f"[bold {COLOR_PRIMARY}]REPOSITORY SNAPSHOT HISTORY ({len(snapshots)})[/]",
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

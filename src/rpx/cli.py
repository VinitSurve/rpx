"""Command-line interface (CLI) for RPX using Typer and Rich."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from rpx import __product_name__, __version__
from rpx.ai import run_ai_insights
from rpx.analyzers.compare import compare_scan_results, compare_snapshot_dicts
from rpx.cache import clear_cache, get_cache_status
from rpx.ci import evaluate_ci_gates, format_ci_report
from rpx.config import (
    check_config,
    find_config_file,
    get_config_paths,
    init_config,
    load_config,
)
from rpx.constants import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
)
from rpx.exceptions import (
    AIProviderError,
    ConfigError,
    ExportError,
    PathNotFoundError,
    RPXError,
    SnapshotError,
)
from rpx.explore import run_interactive_explorer
from rpx.models import ScanResult
from rpx.reporters.context_report import (
    export_context_report,
    generate_context_json,
    generate_context_markdown,
)
from rpx.reporters.csv_report import (
    export_comparison_csv,
    export_complexity_csv,
    export_debt_csv,
    export_dependencies_csv,
    export_files_csv,
    export_languages_csv,
    export_security_csv,
    save_csv_report,
)
from rpx.reporters.html_report import export_html_report, generate_html_string
from rpx.reporters.json_report import export_to_json, save_json_report
from rpx.reporters.mermaid_report import export_mermaid_report, generate_mermaid_graph
from rpx.reporters.terminal import TerminalReporter
from rpx.scanner import ProjectScanner
from rpx.snapshots import (
    clean_snapshots,
    extract_snapshot_summary,
    get_snapshot,
    list_snapshots,
    save_snapshot,
)
from rpx.watch import run_watch_mode

KNOWN_SUBCOMMANDS = {
    "scan",
    "summary",
    "tree",
    "languages",
    "dependencies",
    "complexity",
    "graph",
    "debt",
    "security",
    "git",
    "health",
    "monorepo",
    "compare",
    "history",
    "snapshot",
    "report",
    "explore",
    "watch",
    "context",
    "ci",
    "cache",
    "config",
    "ai",
}

HELP_TEXT = f"""
[bold {COLOR_PRIMARY}]RPX (Repository Project Explorer) v{__version__}[/] — Local-First Repository Intelligence CLI

[bold]Usage:[/]
  rpx [OPTIONS] [PROJECT_PATH]
  rpx <COMMAND> [ARGS] [OPTIONS]

[bold]Core Commands:[/]
  scan [PATH]                     Scan repository (supports --full, --no-cache, --explain-ignored, --package).
  summary [PATH]                  Display concise executive summary of the repository.
  tree [PATH]                     Render directory structure tree (--depth).
  languages [PATH]                Show programming language distribution.
  dependencies [PATH]             Analyze declared, locked, and installed dependencies.
  complexity [PATH]               Analyze function/class cyclomatic complexity (--threshold, --file).
  graph [PATH]                    Analyze internal module dependency graph & layers (--format mermaid|json).
  debt [PATH]                     Consolidate technical debt & dead-code heuristics (--severity, --export).
  security [PATH]                 Run local security hygiene & redacted secret scan (--severity).
  git [SUBCOMMAND] [PATH]         Git intelligence: status, contributors, churn, hotspots, branches.
  health [PATH]                   9-category explainable project health score & recommendations.
  monorepo [PATH]                 Detect multi-package workspaces and inter-package relationships.

[bold]Snapshots, Comparison & Reporting:[/]
  compare [A] [B]                 Compare snapshots (--against <id>) or two project directories.
  history [PATH]                  View historical repository snapshots (--limit).
  snapshot [create|list|clean]    Create, list, or clean local repository snapshots.
  report [PATH]                   Export reports (--format html|json|csv|mermaid, --output).
  context [PATH]                  Export AI-ready repository context (--format markdown|json).

[bold]Interactive, Watch, CI & Utility Commands:[/]
  explore [PATH]                  Interactive terminal repository explorer.
  watch [PATH]                    Watch repository for changes with debounced incremental re-analysis.
  ci [PATH]                       Non-interactive CI quality gate runner with deterministic exit codes.
  cache [status|clear]            Inspect or clear incremental scan cache.
  config [show|init|check|path]   Manage global and per-project TOML configuration.
  ai [PATH]                       Optional AI-assisted architectural & refactoring insights.

[bold]Display & Export Flags (for `rpx` / `rpx scan`):[/]
  --files                         Show only file & directory statistics.
  --loc                           Show only lines of code analytics.
  --languages                     Show only programming language distribution.
  --deps                          Show only dependency analytics.
  --git                           Show only Git analytics.
  --health                        Show only project health and quality findings.
  --tree                          Show directory structure tree.
  --storage                       Show storage analytics.
  --complexity                    Show code complexity analytics.
  --debt                          Show technical debt & dead-code findings.
  --security                      Show local security hygiene indicators.
  --graph                         Show internal module dependency graph.
  --monorepo                      Show workspace & monorepo packages.
  --json                          Export structured report as JSON.
  --csv                           Export statistics as CSV.
  --html                          Export self-contained offline HTML report.
  --save                          Save report to default file.
  --output, -o PATH               Save report to specified file path.
  --force, -f                     Overwrite existing output file.

[bold]Scan & Filtering Flags:[/]
  --full                          Force full re-scan (bypass incremental cache).
  --no-cache                      Disable reading/writing incremental scan cache.
  --explain-ignored               Explain why ignored files/directories were excluded.
  --workspace                     Analyze workspace/monorepo boundaries.
  --package NAME                  Scope analysis to a specific workspace package.
  --top INTEGER                   Number of items to show in rankings (default: 10).
  --depth, -d INTEGER             Maximum directory tree depth (default: 3).
  --exclude, -e PATTERN           Additional patterns to exclude (can be repeated).
  --include-ignored               Include normally ignored directories.
  --no-git                        Skip Git analytics.
  --no-deps                       Skip dependency parsing.
  --no-color                      Disable colored terminal output.
  --quiet, -q                     Suppress visual spinner and print minimal output.
  --verbose, -v                   Verbose logging during scan.
  --version, -V                   Show RPX version and exit.
  --help, -h                      Show this help message and exit.
"""

app = typer.Typer(
    name="rpx",
    add_completion=False,
    no_args_is_help=False,
)

config_app = typer.Typer(
    help="Inspect, validate, and manage RPX configuration files.", no_args_is_help=False
)
cache_app = typer.Typer(
    help="Inspect and clear the RPX incremental scan cache.", no_args_is_help=False
)
snapshot_app = typer.Typer(
    help="Create, list, and manage local repository snapshots.", no_args_is_help=False
)

app.add_typer(config_app, name="config")
app.add_typer(cache_app, name="cache")
app.add_typer(snapshot_app, name="snapshot")


def _run_quick_scan(
    path_str: str = ".",
    no_color: bool = False,
    quiet: bool = False,
    force_full: bool = False,
    use_cache: bool = True,
    explain_ignored: bool = False,
    package_filter: str | None = None,
) -> tuple[ScanResult, Console, TerminalReporter]:
    target_dir = Path(path_str or ".").resolve()
    console = Console(no_color=no_color or "NO_COLOR" in os.environ)
    reporter = TerminalReporter(console=console, no_color=no_color)
    try:
        scanner = ProjectScanner(
            target_path=target_dir,
            use_cache=use_cache,
            force_full=force_full,
            explain_ignored=explain_ignored,
            package_filter=package_filter,
        )
        if not quiet:
            with console.status(f"[bold {COLOR_PRIMARY}]Analyzing {target_dir.name}...[/]"):
                result = scanner.scan()
        else:
            result = scanner.scan()
        return result, console, reporter
    except PathNotFoundError as e:
        console.print(f"[{COLOR_ERROR}]Error:[/] {e}")
        raise typer.Exit(code=1) from e
    except RPXError as e:
        console.print(f"[{COLOR_ERROR}]RPX Error:[/] {e}")
        raise typer.Exit(code=1) from e


# =====================================================================
# CONFIG SUBCOMMANDS
# =====================================================================
@config_app.callback(invoke_without_command=True)
def config_default(ctx: typer.Context) -> None:
    """Default handler for 'rpx config', alias for 'rpx config show'."""
    if ctx.invoked_subcommand is None:
        target = ctx.args[0] if ctx.args else "."
        show_config(target)


@config_app.command("show")
def show_config(
    path: Annotated[
        Optional[str],
        typer.Argument(help="Path to project directory (default: current directory)."),
    ] = None,
) -> None:
    """Display the active RPX configuration."""
    console = Console()
    target_path = Path(path or ".").resolve()
    cfg_file = find_config_file(target_path)
    cfg = load_config(target_path)

    console.print(f"[bold {COLOR_PRIMARY}]RPX Configuration[/]")
    if cfg_file:
        console.print(f"Loaded from: [bold]{cfg_file}[/]")
    else:
        console.print("[dim]Using default built-in configuration (no .rpx.toml found)[/dim]")

    console.print()
    for k, v in cfg.to_dict().items():
        console.print(f" • [bold]{k}[/]: {v}")


@config_app.command("init")
def initialize_config(
    path: Annotated[
        Optional[str],
        typer.Argument(help="Directory where .rpx.toml should be created."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing configuration file."),
    ] = False,
) -> None:
    """Create a default .rpx.toml template in the specified project directory."""
    console = Console()
    target_dir = Path(path or ".").resolve()
    try:
        cfg_path = init_config(target_dir, force=force)
        console.print(f"[{COLOR_SUCCESS}]✔ Created configuration file:[/] [bold]{cfg_path}[/]")
    except ConfigError as e:
        console.print(f"[{COLOR_ERROR}]✘ Error:[/] {e}")
        raise typer.Exit(code=1) from e


@config_app.command("check")
def validate_config_cmd(
    path: Annotated[
        Optional[str],
        typer.Argument(help="Project directory to validate configuration for."),
    ] = None,
) -> None:
    """Validate global and project RPX configuration files."""
    console = Console()
    target_dir = Path(path or ".").resolve()
    ok, messages, _ = check_config(target_dir)
    for msg in messages:
        console.print(f" • {msg}")
    if ok:
        console.print(f"[{COLOR_SUCCESS}]✔ Configuration is valid.[/]")
    else:
        console.print(f"[{COLOR_ERROR}]✘ Configuration validation failed.[/]")
        raise typer.Exit(code=1)


@config_app.command("path")
def config_paths_cmd(
    path: Annotated[
        Optional[str],
        typer.Argument(help="Project directory to inspect config paths for."),
    ] = None,
) -> None:
    """Display resolved configuration and cache directory paths."""
    console = Console()
    target_dir = Path(path or ".").resolve()
    paths = get_config_paths(target_dir)
    console.print(f"[bold {COLOR_PRIMARY}]RPX Configuration & Data Paths[/]")
    for k, v in paths.items():
        console.print(f" • [bold]{k}[/]: {v or '[dim]not present[/dim]'}")


# =====================================================================
# CACHE SUBCOMMANDS
# =====================================================================
@cache_app.callback(invoke_without_command=True)
def cache_default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        cache_status_cmd(".")


@cache_app.command("status")
def cache_status_cmd(
    path: Annotated[Optional[str], typer.Argument(help="Project path.")] = ".",
) -> None:
    """Show incremental scan cache status and storage usage."""
    console = Console()
    target_dir = Path(path or ".").resolve()
    st = get_cache_status(target_dir)
    console.print(f"[bold {COLOR_PRIMARY}]RPX Incremental Scan Cache Status[/]")
    console.print(f" • Cache Directory: [bold]{st['cache_dir']}[/]")
    console.print(f" • Cached Projects: [bold]{st['total_cache_files']}[/]")
    console.print(f" • Total Cache Size: [bold]{st['total_size_bytes']} B[/]")
    console.print(
        f" • Current Project Cached: [bold]{'Yes' if st['current_project_cached'] else 'No'}[/]"
    )


@cache_app.command("clear")
def cache_clear_cmd(
    path: Annotated[Optional[str], typer.Argument(help="Project path.")] = None,
    all_projects: Annotated[
        bool, typer.Option("--all", help="Clear caches for all projects.")
    ] = False,
) -> None:
    """Clear incremental scan cache for the current project or all projects."""
    console = Console()
    target = None if all_projects or path is None else Path(path).resolve()
    removed = clear_cache(project_root=target)
    console.print(f"[{COLOR_SUCCESS}]✔ Cleared {removed} cache file(s).[/]")


# =====================================================================
# SNAPSHOT SUBCOMMANDS
# =====================================================================
@snapshot_app.callback(invoke_without_command=True)
def snapshot_default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        snapshot_create_cmd(".")


@snapshot_app.command("create")
def snapshot_create_cmd(
    path: Annotated[str, typer.Argument(help="Project path to snapshot.")] = ".",
    label: Annotated[str, typer.Option("--label", "-l", help="Snapshot label/tag.")] = "manual",
) -> None:
    """Create and save a repository snapshot for historical tracking and comparison."""
    result, console, _ = _run_quick_scan(path)
    snap = save_snapshot(result, label=label, project_root=Path(result.metadata.path))
    console.print(
        f"[{COLOR_SUCCESS}]✔ Saved snapshot[/] [bold {COLOR_PRIMARY}]{snap['snapshot_id']}[/] "
        f"(label={snap['label']}, files={snap['metrics']['total_files']}, health={snap['metrics']['health_score']}/100)"
    )


@snapshot_app.command("list")
def snapshot_list_cmd(
    path: Annotated[str, typer.Argument(help="Project path.")] = ".",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max snapshots to list.")] = 20,
) -> None:
    """List saved repository snapshots."""
    target_dir = Path(path or ".").resolve()
    snaps = list_snapshots(target_dir, limit=limit)
    reporter = TerminalReporter()
    reporter.render_history(snaps)


@snapshot_app.command("clean")
def snapshot_clean_cmd(
    path: Annotated[str, typer.Argument(help="Project path.")] = ".",
    keep: Annotated[
        int, typer.Option("--keep", "-k", help="Number of newest snapshots to keep.")
    ] = 0,
) -> None:
    """Delete saved snapshots for the project."""
    console = Console()
    target_dir = Path(path or ".").resolve()
    removed = clean_snapshots(target_dir, keep_last=keep)
    console.print(f"[{COLOR_SUCCESS}]✔ Removed {removed} snapshot(s).[/]")


# =====================================================================
# TOP-LEVEL SPECIALIZED COMMANDS
# =====================================================================
@app.command("summary")
def summary_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    json_out: Annotated[bool, typer.Option("--json", help="Output summary as JSON.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Display a concise executive summary of the repository."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out)
    if json_out:
        print(json.dumps(extract_snapshot_summary(result, label="summary"), indent=2))
        return
    reporter.render_summary(result)


@app.command("tree")
def tree_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    depth: Annotated[int, typer.Option("--depth", "-d", help="Maximum tree depth.")] = 3,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Render the repository directory structure tree."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color)
    reporter.render_tree_panel(result, depth=depth)


@app.command("languages")
def languages_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    csv_out: Annotated[bool, typer.Option("--csv", help="Output as CSV.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Analyze programming and markup language distribution."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out or csv_out)
    if json_out:
        print(json.dumps(result.languages.to_dict(), indent=2))
        return
    if csv_out:
        print(export_languages_csv(result))
        return
    reporter.render_language_panel(result)


@app.command("dependencies")
def dependencies_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    csv_out: Annotated[bool, typer.Option("--csv", help="Output as CSV.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Inspect declared, locked, and installed package dependencies."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out or csv_out)
    if json_out:
        print(json.dumps(result.dependencies.to_dict(), indent=2))
        return
    if csv_out:
        print(export_dependencies_csv(result))
        return
    reporter.render_dependency_panel(result)


@app.command("complexity")
def complexity_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    threshold: Annotated[
        Optional[str],
        typer.Option("--threshold", "-t", help="Filter by severity: low, medium, high, critical."),
    ] = None,
    file: Annotated[
        Optional[str],
        typer.Option("--file", "-f", help="Inspect functions in a specific source file."),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    csv_out: Annotated[bool, typer.Option("--csv", help="Output as CSV.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Analyze function/class cyclomatic complexity, nesting depth, and size."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out or csv_out)
    if json_out:
        print(json.dumps(result.complexity.to_dict(), indent=2))
        return
    if csv_out:
        print(export_complexity_csv(result))
        return
    reporter.render_complexity_panel(result, threshold_filter=threshold, file_filter=file)


@app.command("graph")
def graph_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: terminal, json, mermaid."),
    ] = "terminal",
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Write graph output to file.")
    ] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Analyze internal module import graph, coupling, layers, and circular dependencies."""
    quiet = fmt.lower() in ("json", "mermaid") and not output
    result, console, reporter = _run_quick_scan(path, no_color=no_color, quiet=quiet)
    f_lower = fmt.lower()
    if f_lower == "json":
        payload = json.dumps(result.graph.to_dict(), indent=2)
        if output:
            Path(output).write_text(payload, encoding="utf-8")
            console.print(f"[{COLOR_SUCCESS}]✔ Saved dependency graph JSON to {output}[/]")
        else:
            print(payload)
        return
    if f_lower == "mermaid":
        if output:
            export_mermaid_report(result, Path(output))
            console.print(f"[{COLOR_SUCCESS}]✔ Saved Mermaid graph to {output}[/]")
        else:
            print(generate_mermaid_graph(result.graph))
        return
    reporter.render_graph_panel(result)


@app.command("debt")
def debt_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    severity: Annotated[
        Optional[str],
        typer.Option("--severity", "-s", help="Filter by severity: low, medium, high."),
    ] = None,
    category: Annotated[
        Optional[str],
        typer.Option("--category", "-c", help="Filter by debt category substring."),
    ] = None,
    export_fmt: Annotated[
        Optional[str],
        typer.Option("--export", help="Export format: json or csv."),
    ] = None,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Output file path.")
    ] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Inspect technical debt items, hotspots, and dead-code heuristic indicators."""
    quiet = bool(export_fmt and not output)
    result, console, reporter = _run_quick_scan(path, no_color=no_color, quiet=quiet)
    if export_fmt:
        ef = export_fmt.lower()
        content = (
            export_debt_csv(result) if ef == "csv" else json.dumps(result.debt.to_dict(), indent=2)
        )
        if output:
            Path(output).write_text(content, encoding="utf-8")
            console.print(f"[{COLOR_SUCCESS}]✔ Exported technical debt report to {output}[/]")
        else:
            print(content)
        return
    reporter.render_debt_panel(result, severity_filter=severity, category_filter=category)


@app.command("security")
def security_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    severity: Annotated[
        Optional[str],
        typer.Option("--severity", "-s", help="Filter by severity: low, medium, high."),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    csv_out: Annotated[bool, typer.Option("--csv", help="Output as CSV.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Run local security hygiene and risk indicator checks (secrets are redacted)."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out or csv_out)
    if json_out:
        print(json.dumps(result.security.to_dict(), indent=2))
        return
    if csv_out:
        print(export_security_csv(result))
        return
    reporter.render_security_panel(result, severity_filter=severity)


@app.command("git")
def git_command(
    target_or_subcommand: Annotated[
        str,
        typer.Argument(
            help="Subcommand (contributors, churn, hotspots, branches) or project path."
        ),
    ] = ".",
    path: Annotated[
        Optional[str],
        typer.Argument(help="Optional project path when a subcommand is specified."),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Analyze Git history, contributors, file churn, hotspots, and branches."""
    subcommands = {"contributors", "churn", "hotspots", "branches", "status"}
    if target_or_subcommand.lower() in subcommands:
        sub = target_or_subcommand.lower()
        target_path = path or "."
    else:
        sub = "overview"
        target_path = target_or_subcommand

    result, console, reporter = _run_quick_scan(target_path, no_color=no_color, quiet=json_out)
    if json_out:
        print(json.dumps(result.git.to_dict(), indent=2))
        return
    if not result.git.git_available or not result.git.is_git_repo:
        console.print(f"[{COLOR_WARNING}]Not a Git repository: {result.metadata.path}[/]")
        return

    if sub == "contributors":
        reporter.render_git_contributors(result)
    elif sub == "churn":
        reporter.render_git_churn(result)
    elif sub == "hotspots":
        reporter.render_git_hotspots(result)
    elif sub == "branches":
        reporter.render_git_branches(result)
    else:
        reporter.render_git_panel(result)
        if result.git.hotspots:
            reporter.render_git_hotspots(result)


@app.command("health")
def health_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Evaluate 9-category explainable project health score and recommendations."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out)
    if json_out:
        print(json.dumps(result.health.to_dict(), indent=2))
        return
    reporter.render_health_panel(result)


@app.command("monorepo")
def monorepo_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Detect monorepo workspace managers, sub-packages, and package relationships."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color, quiet=json_out)
    if json_out:
        print(json.dumps(result.monorepo.to_dict(), indent=2))
        return
    reporter.render_monorepo_panel(result)


@app.command("compare")
def compare_command(
    target_a: Annotated[
        str, typer.Argument(help="First project path (or current directory).")
    ] = ".",
    target_b: Annotated[
        Optional[str],
        typer.Argument(help="Second project path for directory-to-directory comparison."),
    ] = None,
    against: Annotated[
        Optional[str],
        typer.Option(
            "--against",
            "-a",
            help="Snapshot ID, label, 'latest', 'previous', or JSON report file to compare against.",
        ),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: terminal, json, csv."),
    ] = "terminal",
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Save comparison report to file.")
    ] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Compare current repository against a saved snapshot or compare two project directories."""
    quiet = fmt.lower() in ("json", "csv") and not output
    res_a, console, reporter = _run_quick_scan(target_a, no_color=no_color, quiet=quiet)

    try:
        if target_b:
            res_b, _, _ = _run_quick_scan(target_b, no_color=no_color, quiet=quiet)
            diff = compare_scan_results(res_a, res_b, label_a=target_a, label_b=target_b)
        else:
            snap_id = against or "latest"
            baseline_snap = get_snapshot(Path(res_a.metadata.path), snap_id)
            current_snap = extract_snapshot_summary(res_a, label="working-tree")
            diff = compare_snapshot_dicts(baseline_snap, current_snap)
    except SnapshotError as e:
        console.print(f"[{COLOR_ERROR}]Comparison Error:[/] {e}")
        raise typer.Exit(code=1) from e

    f_lower = fmt.lower()
    if f_lower == "json":
        payload = json.dumps(diff.to_dict(), indent=2)
        if output:
            Path(output).write_text(payload, encoding="utf-8")
            console.print(f"[{COLOR_SUCCESS}]✔ Saved comparison JSON to {output}[/]")
        else:
            print(payload)
        return
    if f_lower == "csv":
        payload = export_comparison_csv(diff)
        if output:
            Path(output).write_text(payload, encoding="utf-8")
            console.print(f"[{COLOR_SUCCESS}]✔ Saved comparison CSV to {output}[/]")
        else:
            print(payload)
        return

    reporter.render_comparison(diff)


@app.command("history")
def history_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum snapshots to show.")] = 10,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Display historical repository snapshots and metric evolution."""
    target_dir = Path(path or ".").resolve()
    snaps = list_snapshots(target_dir, limit=limit)
    if json_out:
        print(json.dumps(snaps, indent=2))
        return
    reporter = TerminalReporter(no_color=no_color)
    reporter.render_history(snaps)


@app.command("report")
def report_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="Report format: html, json, csv, mermaid."),
    ] = "html",
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Output file path.")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing output file.")] = True,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Generate and export standalone repository reports (HTML, JSON, CSV, Mermaid)."""
    f_lower = fmt.lower()
    result, console, _ = _run_quick_scan(path, no_color=no_color)

    default_ext = {
        "html": "rpx-report.html",
        "json": "rpx-report.json",
        "csv": "rpx-report.csv",
        "mermaid": "rpx-graph.mmd",
    }.get(f_lower, "rpx-report.html")
    dest = Path(output or default_ext)

    try:
        if f_lower == "html":
            saved = export_html_report(result, dest)
            console.print(
                f"[{COLOR_SUCCESS}]✔ Self-contained HTML report saved to:[/] [bold]{saved}[/]"
            )
        elif f_lower == "json":
            save_json_report(result, dest, force=force)
            console.print(f"[{COLOR_SUCCESS}]✔ JSON report saved to:[/] [bold]{dest.resolve()}[/]")
        elif f_lower == "csv":
            save_csv_report(result, dest, table_type="files", force=force)
            console.print(f"[{COLOR_SUCCESS}]✔ CSV report saved to:[/] [bold]{dest.resolve()}[/]")
        elif f_lower == "mermaid":
            saved = export_mermaid_report(result, dest)
            console.print(f"[{COLOR_SUCCESS}]✔ Mermaid diagram saved to:[/] [bold]{saved}[/]")
        else:
            console.print(
                f"[{COLOR_ERROR}]Unsupported report format '{fmt}'. Choose html, json, csv, or mermaid.[/]"
            )
            raise typer.Exit(code=1)
    except ExportError as e:
        console.print(f"[{COLOR_ERROR}]Export Error:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command("explore")
def explore_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", help="Render views sequentially without prompting."),
    ] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Launch interactive terminal explorer to navigate repository intelligence."""
    result, _, reporter = _run_quick_scan(path, no_color=no_color)
    run_interactive_explorer(result, reporter, non_interactive=non_interactive)


@app.command("watch")
def watch_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    interval: Annotated[
        float, typer.Option("--interval", "-i", help="Polling interval in seconds.")
    ] = 1.5,
    debounce: Annotated[
        float, typer.Option("--debounce", help="Debounce quiet window in seconds.")
    ] = 0.5,
    cycles: Annotated[
        Optional[int],
        typer.Option("--cycles", help="Stop after N polling cycles (for testing/automation)."),
    ] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Monitor repository for file changes and trigger debounced incremental analysis."""
    target_dir = Path(path or ".").resolve()
    console = Console(no_color=no_color or "NO_COLOR" in os.environ)
    reporter = TerminalReporter(console=console, no_color=no_color)
    run_watch_mode(
        target_path=target_dir,
        reporter=reporter,
        interval_seconds=interval,
        debounce_seconds=debounce,
        max_cycles=cycles,
    )


@app.command("context")
def context_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="Context format: markdown or json."),
    ] = "markdown",
    max_chars: Annotated[
        int, typer.Option("--max-chars", help="Maximum character length for Markdown output.")
    ] = 32000,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Write context to file.")
    ] = None,
) -> None:
    """Generate deterministic, secret-redacted repository context for coding agents."""
    result, console, _ = _run_quick_scan(path, quiet=not bool(output))
    if output:
        saved = export_context_report(result, Path(output), fmt=fmt, max_chars=max_chars)
        console.print(f"[{COLOR_SUCCESS}]✔ AI context written to:[/] [bold]{saved}[/]")
        return
    if fmt.lower() == "json":
        print(generate_context_json(result))
    else:
        print(generate_context_markdown(result, max_chars=max_chars))


@app.command("ci")
def ci_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    min_health: Annotated[
        int, typer.Option("--min-health", help="Minimum required health score (0-100).")
    ] = 50,
    max_high_security: Annotated[
        int,
        typer.Option(
            "--max-high-security", help="Maximum allowed high-severity security findings."
        ),
    ] = 0,
    max_high_debt: Annotated[
        Optional[int],
        typer.Option("--max-high-debt", help="Maximum allowed high-severity debt items."),
    ] = None,
    max_complexity: Annotated[
        Optional[int],
        typer.Option("--max-complexity", help="Maximum allowed function cyclomatic complexity."),
    ] = None,
    fail_on_cycles: Annotated[
        bool,
        typer.Option("--fail-on-cycles", help="Fail if circular module dependencies exist."),
    ] = False,
    fmt: Annotated[
        str, typer.Option("--format", "-f", help="Output format: text or json.")
    ] = "text",
) -> None:
    """Run non-interactive CI quality gates with deterministic exit codes."""
    result, _, _ = _run_quick_scan(path, no_color=True, quiet=True)
    ci_data = evaluate_ci_gates(
        result=result,
        min_health_score=min_health,
        max_high_security=max_high_security,
        max_high_debt=max_high_debt,
        max_complexity=max_complexity,
        fail_on_cycles=fail_on_cycles,
    )
    print(format_ci_report(ci_data, fmt=fmt))
    if not ci_data["passed"]:
        raise typer.Exit(code=1)


@app.command("ai")
def ai_command(
    path: Annotated[str, typer.Argument(help="Path to project directory.")] = ".",
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="AI provider: auto, groq, gemini."),
    ] = "auto",
    model: Annotated[str, typer.Option("--model", "-m", help="Override model name.")] = "",
    focus: Annotated[
        str,
        typer.Option(
            "--focus", help="Analysis focus: architecture, refactoring, onboarding, debt."
        ),
    ] = "architecture",
    offline: Annotated[
        bool,
        typer.Option(
            "--offline", help="Force local deterministic synthesis without network calls."
        ),
    ] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color.")] = False,
) -> None:
    """Generate optional AI-assisted architectural, onboarding, and refactoring insights."""
    result, console, _ = _run_quick_scan(path, no_color=no_color)
    try:
        prov_used, md_text = run_ai_insights(
            result=result,
            provider_pref=provider
            or result.metadata.name
            and load_config(Path(result.metadata.path)).ai_provider,
            model=model,
            focus=focus,
            offline=offline,
        )
    except AIProviderError as e:
        console.print(f"[{COLOR_ERROR}]AI Provider Error:[/] {e}")
        raise typer.Exit(code=1) from e

    console.print(
        Panel(
            Markdown(md_text),
            title=f"[bold {COLOR_SECONDARY}]RPX AI INTELLIGENCE ({prov_used.upper()})[/]",
            border_style=COLOR_SECONDARY,
            box=ROUNDED,
        )
    )


# =====================================================================
# MAIN SCAN COMMAND (DEFAULT FOR `rpx` AND `rpx scan`)
# =====================================================================
@app.command("scan", context_settings={"allow_interspersed_args": True})
def scan_command(
    project_path: Annotated[
        str,
        typer.Argument(help="Path to project directory to scan."),
    ] = ".",
    # Section filters
    files_only: Annotated[
        bool, typer.Option("--files", help="Show only file & directory statistics.")
    ] = False,
    loc_only: Annotated[
        bool, typer.Option("--loc", help="Show only lines of code analytics.")
    ] = False,
    languages_only: Annotated[
        bool, typer.Option("--languages", help="Show only programming language distribution.")
    ] = False,
    deps_only: Annotated[
        bool, typer.Option("--deps", help="Show only dependency analytics.")
    ] = False,
    git_only: Annotated[bool, typer.Option("--git", help="Show only Git analytics.")] = False,
    health_only: Annotated[
        bool, typer.Option("--health", help="Show only project health and quality findings.")
    ] = False,
    tree_only: Annotated[
        bool, typer.Option("--tree", help="Show directory structure tree.")
    ] = False,
    storage_only: Annotated[
        bool, typer.Option("--storage", help="Show storage analytics.")
    ] = False,
    complexity_only: Annotated[
        bool, typer.Option("--complexity", help="Show code complexity analytics.")
    ] = False,
    debt_only: Annotated[
        bool, typer.Option("--debt", help="Show technical debt and dead-code findings.")
    ] = False,
    security_only: Annotated[
        bool, typer.Option("--security", help="Show local security hygiene indicators.")
    ] = False,
    graph_only: Annotated[
        bool, typer.Option("--graph", help="Show internal module dependency graph.")
    ] = False,
    monorepo_only: Annotated[
        bool, typer.Option("--monorepo", "--workspace", help="Show monorepo & workspace packages.")
    ] = False,
    # Export options
    json_export: Annotated[
        bool, typer.Option("--json", help="Export structured report as JSON.")
    ] = False,
    csv_export: Annotated[bool, typer.Option("--csv", help="Export statistics as CSV.")] = False,
    html_export: Annotated[
        bool, typer.Option("--html", help="Export self-contained offline HTML report.")
    ] = False,
    save: Annotated[
        bool,
        typer.Option("--save", help="Save report to default file (rpx-report.json/csv/html)."),
    ] = False,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Save report to specified file path.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing output file.")
    ] = False,
    # Incremental & explainability options
    full_scan: Annotated[
        bool, typer.Option("--full", help="Force full scan, bypassing incremental cache.")
    ] = False,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Disable incremental scan cache.")
    ] = False,
    explain_ignored: Annotated[
        bool,
        typer.Option(
            "--explain-ignored", help="Explain why ignored files/directories were excluded."
        ),
    ] = False,
    package: Annotated[
        Optional[str],
        typer.Option("--package", help="Filter analysis to a specific workspace package."),
    ] = None,
    # Scan options
    top: Annotated[
        Optional[int], typer.Option("--top", help="Number of items to show in rankings.")
    ] = None,
    depth: Annotated[
        Optional[int], typer.Option("--depth", "-d", help="Maximum directory tree depth.")
    ] = None,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option("--exclude", "-e", help="Additional patterns to exclude (can be repeated)."),
    ] = None,
    include_ignored: Annotated[
        bool, typer.Option("--include-ignored", help="Include normally ignored directories.")
    ] = False,
    no_git: Annotated[bool, typer.Option("--no-git", help="Skip Git analytics.")] = False,
    no_deps: Annotated[bool, typer.Option("--no-deps", help="Skip dependency parsing.")] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable colored terminal output.")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress visual dashboard and print minimal output."),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose logging during scan.")
    ] = False,
) -> None:
    """Scan and analyze a repository project, rendering a comprehensive dashboard or export."""
    target_dir = Path(project_path or ".").resolve()
    console = Console(no_color=no_color or "NO_COLOR" in os.environ)

    # 1. Load config defaults if present
    cfg = load_config(target_dir)
    ranking_limit = top if top is not None else cfg.ranking_limit
    tree_depth = depth if depth is not None else cfg.max_depth
    effective_exclude = list(cfg.exclude)
    if exclude:
        effective_exclude.extend(exclude)
    effective_include_ignored = include_ignored or cfg.include_ignored
    effective_no_git = no_git or cfg.no_git
    effective_no_deps = no_deps or cfg.no_deps

    # 2. Run Scanner
    try:
        scanner = ProjectScanner(
            target_path=target_dir,
            ranking_limit=ranking_limit,
            max_depth=tree_depth,
            cli_exclusions=effective_exclude,
            include_ignored=effective_include_ignored,
            enable_git=not effective_no_git,
            enable_deps=not effective_no_deps,
            use_cache=not no_cache,
            force_full=full_scan,
            explain_ignored=explain_ignored,
            package_filter=package,
            config=cfg,
        )

        raw_stdout_export = (json_export or csv_export or html_export) and not output and not save
        if not quiet and not raw_stdout_export:
            with console.status(
                f"[bold {COLOR_PRIMARY}]Scanning repository at {target_dir.name}...[/]"
            ):
                result = scanner.scan()
        else:
            result = scanner.scan()

    except PathNotFoundError as e:
        console.print(f"[{COLOR_ERROR}]Error:[/] {e}")
        raise typer.Exit(code=1) from e
    except RPXError as e:
        console.print(f"[{COLOR_ERROR}]Scan Error:[/] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[{COLOR_ERROR}]Unexpected Error:[/] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1) from e

    # 3. Handle Exports (JSON / CSV / HTML)
    dest_path: Path | None = None
    if output:
        dest_path = Path(output)
    elif save:
        if csv_export:
            dest_path = Path("rpx-report.csv")
        elif html_export:
            dest_path = Path("rpx-report.html")
        else:
            dest_path = Path("rpx-report.json")

    if html_export or (dest_path and dest_path.suffix.lower() in (".html", ".htm")):
        if dest_path:
            try:
                saved = export_html_report(result, dest_path)
                console.print(f"[{COLOR_SUCCESS}]✔ HTML report saved to:[/] [bold]{saved}[/]")
            except ExportError as e:
                console.print(f"[{COLOR_ERROR}]Export Error:[/] {e}")
                raise typer.Exit(code=1) from e
        else:
            print(generate_html_string(result))
        return

    if json_export or (dest_path and dest_path.suffix.lower() == ".json"):
        if dest_path:
            try:
                save_json_report(result, dest_path, force=force)
                console.print(f"[{COLOR_SUCCESS}]✔ JSON report saved to:[/] [bold]{dest_path}[/]")
            except ExportError as e:
                console.print(f"[{COLOR_ERROR}]Export Error:[/] {e}")
                raise typer.Exit(code=1) from e
        else:
            print(export_to_json(result))
        return

    if csv_export or (dest_path and dest_path.suffix.lower() == ".csv"):
        table_type = "files"
        if languages_only:
            table_type = "languages"
        elif deps_only:
            table_type = "deps"
        elif complexity_only:
            table_type = "complexity"
        elif debt_only:
            table_type = "debt"
        elif security_only:
            table_type = "security"

        if dest_path:
            try:
                save_csv_report(result, dest_path, table_type=table_type, force=force)
                console.print(f"[{COLOR_SUCCESS}]✔ CSV report saved to:[/] [bold]{dest_path}[/]")
            except ExportError as e:
                console.print(f"[{COLOR_ERROR}]Export Error:[/] {e}")
                raise typer.Exit(code=1) from e
        else:
            print(export_files_csv(result))
        return

    # 4. Render Terminal Dashboard or Individual Sections
    reporter = TerminalReporter(console=console, no_color=no_color)

    if explain_ignored:
        reporter.render_ignored_items(result)

    any_section_filter = (
        files_only
        or loc_only
        or languages_only
        or deps_only
        or git_only
        or health_only
        or tree_only
        or storage_only
        or complexity_only
        or debt_only
        or security_only
        or graph_only
        or monorepo_only
    )

    if any_section_filter:
        if files_only:
            reporter.render_file_stats_panel(result, ranking_limit=ranking_limit)
        if loc_only:
            reporter.render_loc_panel(result)
        if languages_only:
            reporter.render_language_panel(result)
        if deps_only:
            reporter.render_dependency_panel(result)
        if git_only:
            if result.git.git_available and result.git.is_git_repo:
                reporter.render_git_panel(result)
            else:
                console.print("[dim]Git repository analytics unavailable for this project.[/dim]")
        if health_only:
            reporter.render_health_panel(result)
        if tree_only:
            reporter.render_tree_panel(result, depth=tree_depth)
        if storage_only:
            reporter.render_storage_panel(result, ranking_limit=ranking_limit)
        if complexity_only:
            reporter.render_complexity_panel(result)
        if debt_only:
            reporter.render_debt_panel(result)
        if security_only:
            reporter.render_security_panel(result)
        if graph_only:
            reporter.render_graph_panel(result)
        if monorepo_only:
            reporter.render_monorepo_panel(result)
    elif not explain_ignored:
        reporter.render_dashboard(
            result,
            ranking_limit=ranking_limit,
            tree_depth=tree_depth,
            show_structure=False,
        )


def main(args: list[str] | None = None) -> None:
    """Entry point for CLI execution with preprocessing for seamless command routing."""
    argv = list(args if args is not None else sys.argv[1:])

    console = Console()

    # 1. Version check
    if any(a in ("--version", "-V") for a in argv):
        console.print(f"[bold {COLOR_PRIMARY}]{__product_name__}[/] version [bold]{__version__}[/]")
        return

    # 2. Help check
    if any(a in ("--help", "-h") for a in argv):
        if argv and argv[0] in KNOWN_SUBCOMMANDS:
            try:
                app(argv)
            except SystemExit:
                pass
            return
        console.print(HELP_TEXT.strip())
        return

    # 3. Route known subcommands directly to Typer app
    if argv and argv[0] in KNOWN_SUBCOMMANDS:
        try:
            app(argv)
        except SystemExit as e:
            if e.code != 0:
                sys.exit(e.code)
        return

    # 4. Otherwise, route to 'scan' command for default `rpx [OPTIONS] [PATH]` experience
    scan_argv = ["scan"] + argv
    try:
        app(scan_argv)
    except SystemExit as e:
        if e.code != 0:
            sys.exit(e.code)


if __name__ == "__main__":
    main()

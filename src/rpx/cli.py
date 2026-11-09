"""Command-line interface (CLI) for RPX using Typer and Rich."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from rpx import __product_name__, __version__
from rpx.config import find_config_file, init_config, load_config
from rpx.constants import COLOR_ERROR, COLOR_PRIMARY, COLOR_SUCCESS
from rpx.exceptions import ConfigError, ExportError, PathNotFoundError, RPXError
from rpx.reporters.csv_report import export_files_csv, save_csv_report
from rpx.reporters.json_report import export_to_json, save_json_report
from rpx.reporters.terminal import TerminalReporter
from rpx.scanner import ProjectScanner

HELP_TEXT = f"""
[bold {COLOR_PRIMARY}]RPX (Repository Project Explorer)[/] - Comprehensive developer utility for project analytics.

[bold]Usage:[/]
  rpx [OPTIONS] [PROJECT_PATH]
  rpx config [show|init] [PROJECT_PATH]

[bold]Arguments:[/]
  [PROJECT_PATH]                  Path to project directory to scan (default: current directory).

[bold]Display Options:[/]
  --files                         Show only file & directory statistics.
  --loc                           Show only lines of code analytics.
  --languages                     Show only programming language distribution.
  --deps                          Show only dependency analytics.
  --git                           Show only Git analytics.
  --health                        Show only project health and quality findings.
  --tree                          Show directory structure tree.
  --storage                       Show storage analytics.

[bold]Export Options:[/]
  --json                          Export structured report as JSON.
  --csv                           Export statistics as CSV.
  --save                          Save report to default file (rpx-report.json or rpx-report.csv).
  --output, -o PATH               Save report to specified file path.
  --force, -f                     Overwrite existing output file.

[bold]Filtering & Configuration:[/]
  --top INTEGER                   Number of items to show in rankings (default: 10).
  --depth, -d INTEGER             Maximum directory tree depth (default: 3).
  --exclude, -e PATTERN           Additional patterns to exclude (can be repeated).
  --include-ignored               Include normally ignored directories.
  --no-git                        Skip Git analytics.
  --no-deps                       Skip dependency parsing.
  --no-color                      Disable colored terminal output.
  --quiet, -q                     Suppress visual dashboard and print minimal output.
  --verbose, -v                   Verbose logging during scan.
  --version, -V                   Show RPX version and exit.
  --help, -h                      Show this help message and exit.

[bold]Utility Commands:[/]
  config show [PATH]              Display active configuration for project.
  config init [PATH]              Create a default .rpx.toml configuration file.

[bold]Examples:[/]
  rpx                             Scan current directory and display complete dashboard.
  rpx /path/to/project            Scan a specific project.
  rpx --loc                       Show only lines of code analysis.
  rpx --json --output report.json Export full analytics as JSON.
  rpx --csv --save                Export file statistics as CSV.
  rpx --tree --depth 2            Display project structure tree up to depth 2.
  rpx config init                 Initialize .rpx.toml template.
"""

app = typer.Typer(
    name="rpx",
    add_completion=False,
    no_args_is_help=False,
)

config_app = typer.Typer(help="Inspect and manage RPX configuration files.", no_args_is_help=False)
app.add_typer(config_app, name="config")


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


@app.command("scan", hidden=True, context_settings={"allow_interspersed_args": True})
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
    # Export options
    json_export: Annotated[
        bool, typer.Option("--json", help="Export structured report as JSON.")
    ] = False,
    csv_export: Annotated[bool, typer.Option("--csv", help="Export statistics as CSV.")] = False,
    save: Annotated[
        bool,
        typer.Option(
            "--save", help="Save report to default file (rpx-report.json or rpx-report.csv)."
        ),
    ] = False,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Save report to specified file path.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing output file.")
    ] = False,
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
        )

        if not quiet and not (json_export and not output) and not (csv_export and not output):
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

    # 3. Handle Exports (JSON / CSV)
    dest_path: Path | None = None
    if output:
        dest_path = Path(output)
    elif save:
        if csv_export:
            dest_path = Path("rpx-report.csv")
        else:
            dest_path = Path("rpx-report.json")

    # JSON export handling
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

    # CSV export handling
    if csv_export or (dest_path and dest_path.suffix.lower() == ".csv"):
        table_type = "files"
        if languages_only:
            table_type = "languages"
        elif deps_only:
            table_type = "deps"

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

    any_section_filter = (
        files_only
        or loc_only
        or languages_only
        or deps_only
        or git_only
        or health_only
        or tree_only
        or storage_only
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
    else:
        # Full dashboard
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
        # If user explicitly asked for 'rpx config --help'
        if argv and argv[0] == "config":
            try:
                app(argv)
            except SystemExit:
                pass
            return
        console.print(HELP_TEXT.strip())
        return

    # 3. Check if user is invoking 'config' subcommand
    if argv and argv[0] == "config":
        try:
            app(argv)
        except SystemExit as e:
            if e.code != 0:
                sys.exit(e.code)
        return

    # 4. Otherwise, route to 'scan' command
    scan_argv = ["scan"] + argv
    try:
        app(scan_argv)
    except SystemExit as e:
        if e.code != 0:
            sys.exit(e.code)


if __name__ == "__main__":
    main()

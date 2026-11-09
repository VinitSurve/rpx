"""Interactive terminal explorer for RPX with automatic non-interactive fallback."""

from __future__ import annotations

import sys

from rich.box import ROUNDED
from rich.panel import Panel
from rich.text import Text

from rpx.constants import (
    COLOR_ACCENT,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_WHITE,
)
from rpx.models import ScanResult
from rpx.reporters.terminal import TerminalReporter


def run_interactive_explorer(
    result: ScanResult,
    reporter: TerminalReporter,
    non_interactive: bool = False,
    max_iterations: int | None = None,
) -> None:
    """Launch an interactive terminal menu to explore repository intelligence views."""
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if non_interactive or not is_tty:
        reporter.render_summary(result)
        reporter.render_complexity_panel(result)
        reporter.render_debt_panel(result)
        reporter.render_health_panel(result)
        return

    reporter.render_summary(result)
    iteration = 0

    while True:
        if max_iterations is not None and iteration >= max_iterations:
            break
        iteration += 1

        menu = Text.from_markup(
            f"[bold {COLOR_PRIMARY}][1][/] Overview & Metadata    "
            f"[bold {COLOR_PRIMARY}][2][/] Directory Structure    "
            f"[bold {COLOR_PRIMARY}][3][/] Languages & LOC\n"
            f"[bold {COLOR_PRIMARY}][4][/] Dependencies & Graph   "
            f"[bold {COLOR_PRIMARY}][5][/] Code Complexity        "
            f"[bold {COLOR_PRIMARY}][6][/] Technical Debt\n"
            f"[bold {COLOR_PRIMARY}][7][/] Security Indicators    "
            f"[bold {COLOR_PRIMARY}][8][/] Git & Hotspots         "
            f"[bold {COLOR_PRIMARY}][9][/] Project Health\n"
            f"[bold {COLOR_SECONDARY}][q][/] Quit Interactive Explorer"
        )
        reporter.console.print(
            Panel(
                menu,
                title=f"[bold {COLOR_ACCENT}]RPX INTERACTIVE EXPLORER — {result.metadata.name}[/]",
                border_style=COLOR_ACCENT,
                box=ROUNDED,
            )
        )

        try:
            choice = (
                reporter.console.input(f"[bold {COLOR_WHITE}]Select view (1-9, q to quit): [/]")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            reporter.console.print(f"\n[dim {COLOR_MUTED}]Exiting RPX Explorer.[/]")
            break

        if choice in ("q", "quit", "exit"):
            reporter.console.print(f"[dim {COLOR_MUTED}]Exiting RPX Explorer.[/]")
            break
        if choice == "1":
            reporter.render_summary(result)
            reporter.render_metadata_panel(result)
        elif choice == "2":
            reporter.render_tree_panel(result, depth=4)
        elif choice == "3":
            reporter.render_language_panel(result)
            reporter.render_loc_panel(result)
        elif choice == "4":
            reporter.render_dependency_panel(result)
            reporter.render_graph_panel(result)
        elif choice == "5":
            reporter.render_complexity_panel(result)
        elif choice == "6":
            reporter.render_debt_panel(result)
        elif choice == "7":
            reporter.render_security_panel(result)
        elif choice == "8":
            reporter.render_git_panel(result)
            reporter.render_git_hotspots(result)
        elif choice == "9":
            reporter.render_health_panel(result)
        else:
            reporter.console.print(
                f"[{COLOR_SECONDARY}]Invalid selection '{choice}'. Choose 1-9 or q.[/]"
            )

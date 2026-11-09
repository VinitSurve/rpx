"""Project structure and directory tree generator."""

from __future__ import annotations

from pathlib import Path

from rich.tree import Tree

from rpx.constants import COLOR_PRIMARY, COLOR_SECONDARY, COLOR_WHITE
from rpx.utils.formatting import format_bytes
from rpx.utils.ignore import IgnoreManager


def build_structure_tree(
    project_root: Path,
    ignore_manager: IgnoreManager,
    max_depth: int = 3,
    show_sizes: bool = True,
) -> Tree:
    """Construct a Rich Tree representing the project structure."""
    root_label = f"[bold {COLOR_PRIMARY}]{project_root.name}/[/]"
    root_tree = Tree(root_label)

    _add_tree_nodes(
        current_dir=project_root,
        current_tree=root_tree,
        ignore_manager=ignore_manager,
        current_depth=1,
        max_depth=max_depth,
        show_sizes=show_sizes,
    )
    return root_tree


def _add_tree_nodes(
    current_dir: Path,
    current_tree: Tree,
    ignore_manager: IgnoreManager,
    current_depth: int,
    max_depth: int,
    show_sizes: bool,
) -> None:
    """Recursively add directories and files to the Rich Tree up to max_depth."""
    if current_depth > max_depth:
        return

    try:
        entries = sorted(
            list(current_dir.iterdir()),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except (OSError, PermissionError):
        return

    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]

    # Add directories
    for d in dirs:
        if ignore_manager.is_ignored(d, is_dir=True):
            continue

        dir_label = f"[bold {COLOR_SECONDARY}]{d.name}/[/]"
        branch = current_tree.add(dir_label)
        _add_tree_nodes(
            current_dir=d,
            current_tree=branch,
            ignore_manager=ignore_manager,
            current_depth=current_depth + 1,
            max_depth=max_depth,
            show_sizes=show_sizes,
        )

    # Add files
    for f in files:
        if ignore_manager.is_ignored(f, is_dir=False):
            continue

        if show_sizes:
            try:
                size_str = format_bytes(f.stat(follow_symlinks=False).st_size)
                file_label = f"[{COLOR_WHITE}]{f.name}[/] [dim]({size_str})[/]"
            except (OSError, PermissionError):
                file_label = f"[{COLOR_WHITE}]{f.name}[/]"
        else:
            file_label = f"[{COLOR_WHITE}]{f.name}[/]"

        current_tree.add(file_label)

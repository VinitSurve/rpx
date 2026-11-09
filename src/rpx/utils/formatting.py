"""Formatting utilities for numbers, bytes, progress bars, and durations."""


def format_bytes(size_bytes: int | float) -> str:
    """Format bytes into human-readable B, KB, MB, GB, TB strings."""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(size_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    return f"{size:.1f} {units[unit_idx]}"


def format_number(n: int) -> str:
    """Format integer with thousands separator."""
    return f"{n:,}"


def format_percentage(pct: float) -> str:
    """Format float percentage."""
    return f"{pct:.1f}%"


def format_duration(seconds: float) -> str:
    """Format duration in seconds into human-friendly milliseconds or seconds."""
    if seconds < 0.001:
        return "<1 ms"
    elif seconds < 1.0:
        return f"{int(seconds * 1000)} ms"
    elif seconds < 60.0:
        return f"{seconds:.2f} s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"


def render_horizontal_bar(percentage: float, width: int = 15) -> str:
    """Render a horizontal text bar using unicode blocks."""
    if percentage <= 0:
        return "░" * width
    if percentage >= 100:
        return "█" * width

    fill_float = (percentage / 100.0) * width
    full_blocks = int(fill_float)
    remainder = fill_float - full_blocks

    # Sub-block unicode characters: 1/8 to 7/8
    sub_blocks = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
    sub_idx = int(remainder * 8)
    sub_char = sub_blocks[min(sub_idx, len(sub_blocks) - 1)]

    bar = "█" * full_blocks
    if len(bar) < width and sub_char:
        bar += sub_char
    empty_count = width - len(bar)
    if empty_count > 0:
        bar += "░" * empty_count
    return bar[:width]


def truncate_string(s: str, max_length: int = 50, trailing: str = "...") -> str:
    """Truncate string with trailing ellipsis if it exceeds max_length."""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(trailing)] + trailing

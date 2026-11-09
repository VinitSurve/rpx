"""Filesystem inspection, safe file reading, and metadata retrieval."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from rpx.constants import BINARY_EXTENSIONS


def get_safe_stat(path: Path) -> os.stat_result | None:
    """Get os.stat_result without raising on missing or unreadable files."""
    try:
        return path.stat(follow_symlinks=False)
    except (OSError, PermissionError):
        return None


def get_creation_time(stat_res: os.stat_result | None) -> str | None:
    """Extract filesystem creation/birth time if reliably supported by the OS."""
    if not stat_res:
        return None
    # macOS and BSD support st_birthtime
    if hasattr(stat_res, "st_birthtime") and stat_res.st_birthtime > 0:
        try:
            dt = datetime.fromtimestamp(stat_res.st_birthtime, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OSError):
            return None
    # Windows supports st_ctime as file creation time
    if os.name == "nt" and hasattr(stat_res, "st_ctime") and stat_res.st_ctime > 0:
        try:
            dt = datetime.fromtimestamp(stat_res.st_ctime, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OSError):
            return None
    return None


def get_modification_time(stat_res: os.stat_result | None) -> str | None:
    """Extract last modification time as formatted string."""
    if not stat_res:
        return None
    try:
        dt = datetime.fromtimestamp(stat_res.st_mtime, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OSError):
        return None


def is_binary_file(path: Path, sample_size: int = 8192) -> bool:
    """Check if a file is binary using extension heuristics and null byte inspection."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
            if not chunk:
                return False
            # Null bytes strongly indicate binary content
            if b"\x00" in chunk:
                return True
            # Check for non-text characters
            text_characters = b"".join([bytes([i]) for i in range(32, 127)]) + b"\n\r\t\b\x0c"
            non_text = chunk.translate(None, text_characters)
            # If more than 30% are non-text control characters, consider binary
            if len(non_text) / len(chunk) > 0.30:
                return True
    except (OSError, PermissionError):
        return False

    return False


def compute_file_hash(path: Path, max_size_bytes: int = 50 * 1024 * 1024) -> str | None:
    """Compute SHA-256 hash of a file for duplicate detection.

    Skips files larger than max_size_bytes to prevent high memory/CPU usage.
    """
    try:
        stat_res = path.stat(follow_symlinks=False)
        if stat_res.st_size == 0 or stat_res.st_size > max_size_bytes:
            return None

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def read_text_lines_safely(
    path: Path, max_file_size: int = 10 * 1024 * 1024
) -> Generator[str, None, None]:
    """Read a text file line-by-line using safe decoding fallback (UTF-8, Latin-1).

    Yields lines without trailing newlines. Skips files exceeding max_file_size.
    """
    try:
        stat_res = path.stat(follow_symlinks=False)
        if stat_res.st_size > max_file_size:
            return

        # Attempt UTF-8 with errors replaced, fallback to latin-1
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line.rstrip("\r\n")
    except (OSError, PermissionError):
        return

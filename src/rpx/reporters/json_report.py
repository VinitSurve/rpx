"""Structured JSON export system for RPX scan results."""

from __future__ import annotations

import json
from pathlib import Path

from rpx import __product_name__, __version__
from rpx.exceptions import ExportError
from rpx.models import ScanResult


def export_to_json(result: ScanResult, indent: int = 2) -> str:
    """Serialize the scan result to a JSON string adhering to the RPX schema."""
    data = result.to_dict()
    data["app"] = {
        "name": __product_name__,
        "version": __version__,
    }
    return json.dumps(data, indent=indent, default=str)


def save_json_report(result: ScanResult, destination_path: Path, force: bool = False) -> None:
    """Write the JSON report to the specified file path.

    Raises ExportError if destination_path exists and force is False.
    """
    dest = destination_path.resolve()
    if dest.exists() and not force:
        raise ExportError(f"Destination file already exists: {dest}. Use --force to overwrite.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    json_str = export_to_json(result)

    try:
        with open(dest, "w", encoding="utf-8") as f:
            f.write(json_str)
    except OSError as e:
        raise ExportError(f"Failed to write JSON report to {dest}: {e}") from e

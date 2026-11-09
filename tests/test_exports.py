"""Tests for JSON and CSV export capabilities."""

import json
from pathlib import Path

import pytest

from rpx.exceptions import ExportError
from rpx.models import (
    ScanResult,
)
from rpx.reporters.csv_report import export_files_csv, save_csv_report
from rpx.reporters.json_report import export_to_json, save_json_report

# Using shared mock_scan_result fixture from conftest.py


def test_json_export(mock_scan_result: ScanResult):
    json_str = export_to_json(mock_scan_result)
    data = json.loads(json_str)

    assert data["schema_version"] == "1.0.0"
    assert data["app"]["name"] == "RPX"
    assert data["metadata"]["name"] == "test-repo"
    assert data["loc"]["total_physical"] == 50
    assert data["health"]["score"] == 85


def test_save_json_overwrite_protection(tmp_path: Path, mock_scan_result: ScanResult):
    target_file = tmp_path / "report.json"
    target_file.write_text("existing content", encoding="utf-8")

    # Without force, must raise ExportError
    with pytest.raises(ExportError):
        save_json_report(mock_scan_result, target_file, force=False)

    # With force, succeeds
    save_json_report(mock_scan_result, target_file, force=True)
    assert target_file.read_text().startswith('{\n  "schema_version"')


def test_csv_export(mock_scan_result: ScanResult):
    files_csv = export_files_csv(mock_scan_result)
    assert "File,Language,Total Physical Lines" in files_csv
    assert "app.py,Python,50,40,5,5,0" in files_csv


def test_save_csv_overwrite_protection(tmp_path: Path, mock_scan_result: ScanResult):
    target_file = tmp_path / "report.csv"
    target_file.write_text("existing", encoding="utf-8")

    with pytest.raises(ExportError):
        save_csv_report(mock_scan_result, target_file, force=False)

    save_csv_report(mock_scan_result, target_file, force=True)
    assert "File,Language" in target_file.read_text()

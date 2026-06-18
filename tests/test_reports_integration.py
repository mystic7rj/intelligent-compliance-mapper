# -*- coding: utf-8 -*-
"""Integration smoke tests for all report generators."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.reports.excel_reporter import ExcelReporter
from src.reports.html_reporter import HTMLReporter
from src.reports.pdf_reporter import PDFReporter

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_html_reporter_generates_valid_file(
    mock_gap_result,
    mock_risk_report,
    tmp_path: Path,
) -> None:
    reporter = HTMLReporter(template_dir=TEMPLATES_DIR)
    tmp_output_dir = tmp_path

    output_file = reporter.generate(mock_gap_result, mock_risk_report, tmp_output_dir)
    try:
        assert output_file.exists()
        assert output_file.stat().st_size > 0

        content = output_file.read_text(encoding="utf-8").lower()
        assert "<html" in content or "<!doctype" in content
    finally:
        if output_file.exists():
            output_file.unlink()


def test_excel_reporter_generates_valid_file(
    mock_gap_result,
    mock_risk_report,
    tmp_path: Path,
) -> None:
    reporter = ExcelReporter(template_dir=TEMPLATES_DIR)
    tmp_output_dir = tmp_path

    output_file = reporter.generate(mock_gap_result, mock_risk_report, tmp_output_dir)
    try:
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert output_file.suffix == ".xlsx"
    finally:
        if output_file.exists():
            output_file.unlink()


def test_pdf_reporter_generates_valid_file(
    mock_gap_result,
    mock_risk_report,
    tmp_path: Path,
) -> None:
    reporter = PDFReporter(template_dir=TEMPLATES_DIR)
    tmp_output_dir = tmp_path

    output_file = reporter.generate(mock_gap_result, mock_risk_report, tmp_output_dir)
    try:
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert output_file.read_bytes()[:4] == b"%PDF"
    finally:
        if output_file.exists():
            output_file.unlink()

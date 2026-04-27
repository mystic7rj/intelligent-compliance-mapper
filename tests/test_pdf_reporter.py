"""Tests for PDFReporter — output, sanitization, path traversal, errors.

Uses ``tmp_path`` pytest fixture for all file I/O.  Mock data classes
replace real Pydantic models to keep tests independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.core.exceptions import ReportGenerationError
from src.reports.pdf_reporter import PDFReporter
from src.utils.security import SecurityError

# ---------------------------------------------------------------------------
# Lightweight mock data (mirrors GapAnalysisResult / RiskReport shapes)
# ---------------------------------------------------------------------------


@dataclass
class MockControl:
    """Mock control object matching the Control model interface."""

    control_id: str
    title: str
    description: str = ""
    priority: str = "medium"


@dataclass
class MockGapResult:
    """Mock gap analysis result with sensible defaults."""

    framework_name: str = "NIST_CSF"
    total_controls: int = 5
    implemented_count: int = 2
    missing_controls: list[Any] = field(default_factory=list)
    compliance_percentage: float = 40.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class MockFinding:
    """Mock risk finding matching the RiskFinding model interface."""

    control_id: str
    control_name: str
    severity: str = "HIGH"
    likelihood: float = 0.8
    impact: float = 0.8
    risk_score: float = 64.0


@dataclass
class MockRiskReport:
    """Mock risk report matching the RiskReport model interface."""

    overall_risk_level: str = "HIGH"
    risk_score: float = 64.0
    findings: list[Any] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    scored_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gap_result() -> MockGapResult:
    """Realistic gap analysis result with 3 missing controls."""
    return MockGapResult(
        missing_controls=[
            MockControl(
                control_id="ID.AM-1",
                title="Asset Inventory",
                description="Maintain asset inventory",
                priority="high",
            ),
            MockControl(
                control_id="PR.AC-1",
                title="Access Control",
                description="Manage access permissions",
                priority="critical",
            ),
            MockControl(
                control_id="DE.CM-1",
                title="Monitoring",
                description="Continuous monitoring",
                priority="medium",
            ),
        ],
    )


@pytest.fixture()
def risk_report() -> MockRiskReport:
    """Realistic risk report with findings and recommendations."""
    return MockRiskReport(
        findings=[
            MockFinding(
                control_id="ID.AM-1",
                control_name="Asset Inventory",
                severity="HIGH",
                risk_score=64.0,
            ),
            MockFinding(
                control_id="PR.AC-1",
                control_name="Access Control",
                severity="CRITICAL",
                risk_score=90.25,
            ),
            MockFinding(
                control_id="DE.CM-1",
                control_name="Monitoring",
                severity="MEDIUM",
                risk_score=27.0,
            ),
        ],
        recommendations=[
            "1. Prioritise implementation of control PR.AC-1 (Access Control)",
            "2. Prioritise implementation of control ID.AM-1 (Asset Inventory)",
            "3. Prioritise implementation of control DE.CM-1 (Monitoring)",
        ],
    )


@pytest.fixture()
def reporter(tmp_path: Path) -> PDFReporter:
    """PDFReporter with template_dir set to a temp directory."""
    return PDFReporter(template_dir=tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateReturnsValidPath:
    """generate() should return a .pdf path and write a non-empty file."""

    # Verify that generate() returns a path ending in .pdf
    def test_returns_pdf_path(
        self,
        reporter: PDFReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        assert result.suffix == ".pdf"

    # Verify that the output file exists and has content
    def test_output_file_exists_and_is_nonempty(
        self,
        reporter: PDFReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        assert result.exists()
        assert result.stat().st_size > 0


class TestPathTraversal:
    """Output path with traversal must raise SecurityError."""

    # Verify that a path traversal attempt is rejected
    def test_traversal_raises_security_error(
        self,
        reporter: PDFReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        malicious_path = tmp_path / ".." / ".." / "etc"
        with pytest.raises(SecurityError):
            reporter.generate(gap_result, risk_report, malicious_path)  # type: ignore[arg-type]


class TestXSSPrevention:
    """XSS/script content in control names must be sanitized before PDF."""

    # Verify that <script> tags are stripped from the PDF output bytes
    def test_script_tag_is_sanitized(
        self,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        reporter = PDFReporter(template_dir=tmp_path)
        xss_gap = MockGapResult(
            missing_controls=[
                MockControl(
                    control_id="ID.AM-1",
                    title="<script>alert('xss')</script>",
                    description="<img onerror=alert(1) src=x>",
                    priority="high",
                ),
            ],
        )
        result = reporter.generate(xss_gap, risk_report, tmp_path)  # type: ignore[arg-type]

        # Read raw PDF bytes and check that no script tag survives
        pdf_bytes = result.read_bytes()
        assert b"<script>" not in pdf_bytes
        assert b"alert('xss')" not in pdf_bytes


class TestInvalidOutputDir:
    """Invalid output directory must raise ReportGenerationError."""

    # Verify that a non-writable/invalid path triggers the correct error
    def test_invalid_dir_raises_report_error(
        self,
        reporter: PDFReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        # Use a file path (not a directory) as the output — this should fail
        fake_file = tmp_path / "not_a_dir.txt"
        fake_file.write_text("block", encoding="utf-8")

        # Attempting to write into a file-path should raise an error
        with pytest.raises((ReportGenerationError, OSError)):
            reporter.generate(gap_result, risk_report, fake_file)  # type: ignore[arg-type]

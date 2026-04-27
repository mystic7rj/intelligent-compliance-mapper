"""Tests for HTMLReporter — output, content, XSS, path traversal, errors.

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
from src.reports.base_reporter import BaseReporter
from src.reports.html_reporter import HTMLReporter
from src.utils.security import SecurityError

# ---------------------------------------------------------------------------
# Lightweight mock data (mirrors GapAnalysisResult / RiskReport shapes)
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass
class MockControl:
    control_id: str
    title: str
    description: str = ""
    priority: str = "medium"


@dataclass
class MockGapResult:
    framework_name: str = "NIST_CSF"
    total_controls: int = 5
    implemented_count: int = 2
    missing_controls: list[Any] = field(default_factory=list)
    compliance_percentage: float = 40.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class MockFinding:
    control_id: str
    control_name: str
    severity: str = "HIGH"
    likelihood: float = 0.8
    impact: float = 0.8
    risk_score: float = 64.0


@dataclass
class MockRiskReport:
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
    """A realistic gap analysis result with 3 missing controls."""
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
    """A realistic risk report with findings and recommendations."""
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
def reporter() -> HTMLReporter:
    """HTMLReporter wired to the project's templates directory."""
    return HTMLReporter(template_dir=TEMPLATES_DIR)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateReturnsValidPath:
    """generate() should return a .html path and write a non-empty file."""

    def test_returns_html_path(
        self,
        reporter: HTMLReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        assert result.suffix == ".html"

    def test_output_file_exists_and_is_nonempty(
        self,
        reporter: HTMLReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        assert result.exists()
        assert result.stat().st_size > 0


class TestOutputContent:
    """Generated HTML must contain key data from the inputs."""

    def test_contains_framework_name(
        self,
        reporter: HTMLReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        html = result.read_text(encoding="utf-8")
        assert "NIST_CSF" in html

    def test_contains_compliance_percentage(
        self,
        reporter: HTMLReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        result = reporter.generate(gap_result, risk_report, tmp_path)  # type: ignore[arg-type]
        html = result.read_text(encoding="utf-8")
        assert "40.0" in html


class TestXSSPrevention:
    """XSS payload in control names must be escaped in the output."""

    def test_script_tag_is_escaped(
        self,
        reporter: HTMLReporter,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
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
        html = result.read_text(encoding="utf-8")

        # Raw script tag must NOT appear anywhere
        assert "<script>" not in html
        assert "alert('xss')" not in html
        # Content is double-escaped (sanitize_text + autoescape) which is safe
        # The escaped entities (&lt; etc.) get entity-escaped again by Jinja2
        assert "&amp;lt;script&amp;gt;" in html


class TestPathTraversal:
    """Output path with traversal must raise SecurityError."""

    def test_traversal_raises_security_error(
        self,
        reporter: HTMLReporter,
        gap_result: MockGapResult,
        risk_report: MockRiskReport,
        tmp_path: Path,
    ) -> None:
        malicious_path = tmp_path / ".." / ".." / "etc"
        with pytest.raises(SecurityError):
            reporter.generate(gap_result, risk_report, malicious_path)  # type: ignore[arg-type]


class TestInvalidTemplateDir:
    """Non-existent template directory raises ReportGenerationError."""

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        fake_dir = tmp_path / "nonexistent_templates"
        # The dir does not exist, so HTMLReporter should raise
        with pytest.raises(ReportGenerationError, match="does not exist"):
            HTMLReporter(template_dir=fake_dir)


class TestSanitizeText:
    """sanitize_text() must escape all HTML special characters."""

    def test_escapes_angle_brackets(self) -> None:
        assert BaseReporter.sanitize_text("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"

    def test_escapes_ampersand(self) -> None:
        assert "&amp;" in BaseReporter.sanitize_text("AT&T")

    def test_escapes_quotes(self) -> None:
        result = BaseReporter.sanitize_text('He said "hello"')
        assert "&" in result  # contains &#34; or &quot;
        assert '"' not in result

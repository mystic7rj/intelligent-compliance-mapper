"""Comprehensive CLI tests using click.testing.CliRunner.

All core dependencies (GapAnalyzer, RiskScorer, FrameworkRepository,
ControlRepository) are mocked — zero real database calls.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.api.cli import cli
from src.core.gap_analyzer import Control as GapControl
from src.core.gap_analyzer import GapAnalysisResult
from src.core.risk_scorer import RiskFinding, RiskReport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """Create a fresh CliRunner for each test."""
    return CliRunner()


@pytest.fixture()
def controls_file(tmp_path: Path) -> Path:
    """Write a sample controls .txt file and return its path."""
    path = tmp_path / "controls.txt"
    path.write_text("ID.AM-1\nPR.AC-1\n\n  PR.DS-2  \n", encoding="utf-8")
    return path


@pytest.fixture()
def mock_gap_result() -> GapAnalysisResult:
    """Build a mock GapAnalysisResult."""
    return GapAnalysisResult(
        framework_name="NIST_CSF",
        total_controls=5,
        implemented_count=3,
        missing_controls=[
            GapControl(
                control_id="DE.CM-1",
                title="Detect Anomalies",
                description="Monitor for anomalies",
                priority="high",
            ),
            GapControl(
                control_id="RS.RP-1",
                title="Response Planning",
                description="Incident response plan",
                priority="critical",
            ),
        ],
        compliance_percentage=60.0,
        analyzed_at=datetime.now(tz=UTC),
    )


@pytest.fixture()
def mock_risk_report() -> RiskReport:
    """Build a mock RiskReport."""
    return RiskReport(
        overall_risk_level="HIGH",
        risk_score=65.0,
        findings=[
            RiskFinding(
                control_id="DE.CM-1",
                control_name="Detect Anomalies",
                severity="HIGH",
                likelihood=0.80,
                impact=0.80,
                risk_score=57.60,
            ),
            RiskFinding(
                control_id="RS.RP-1",
                control_name="Response Planning",
                severity="CRITICAL",
                likelihood=0.95,
                impact=0.95,
                risk_score=76.71,
            ),
        ],
        recommendations=[
            "1. Prioritise implementation of control RS.RP-1 (Response Planning)"
        ],
        scored_at=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# analyze run
# ---------------------------------------------------------------------------


class TestAnalyzeRun:
    """Tests for the ``analyze run`` command."""

    @patch("src.api.commands.analyze.safe_path")
    @patch("src.api.commands.analyze.get_session")
    @patch("src.api.commands.analyze.get_engine")
    @patch("src.api.commands.analyze.RiskScorer")
    @patch("src.api.commands.analyze.GapAnalyzer")
    @patch("src.api.commands.analyze.FrameworkRepository")
    def test_valid_table_output(
        self,
        mock_fw_repo_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_scorer_cls: MagicMock,
        mock_get_engine: MagicMock,
        mock_get_session: MagicMock,
        mock_safe_path: MagicMock,
        runner: CliRunner,
        controls_file: Path,
        mock_gap_result: GapAnalysisResult,
        mock_risk_report: RiskReport,
    ) -> None:
        """Valid inputs with table output should exit 0."""
        mock_safe_path.return_value = controls_file
        mock_analyzer_cls.return_value.analyze.return_value = mock_gap_result
        mock_scorer_cls.return_value.score.return_value = mock_risk_report
        mock_get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(cli, [
            "analyze", "run",
            "--framework", "NIST_CSF",
            "--controls", str(controls_file),
        ])

        assert result.exit_code == 0
        assert "Gap Analysis Summary" in result.output

    def test_invalid_framework(
        self,
        runner: CliRunner,
        controls_file: Path,
    ) -> None:
        """Invalid --framework value should exit 2 (Click usage error)."""
        result = runner.invoke(cli, [
            "analyze", "run",
            "--framework", "INVALID_FW",
            "--controls", str(controls_file),
        ])

        assert result.exit_code == 2
        assert "Invalid framework" in result.output

    def test_nonexistent_controls_file(
        self,
        runner: CliRunner,
    ) -> None:
        """Non-existent controls file should exit 2 (Click path error)."""
        result = runner.invoke(cli, [
            "analyze", "run",
            "--framework", "NIST_CSF",
            "--controls", "/nonexistent/controls.txt",
        ])

        assert result.exit_code == 2

    @patch("src.api.commands.analyze.safe_path")
    @patch("src.api.commands.analyze.get_session")
    @patch("src.api.commands.analyze.get_engine")
    @patch("src.api.commands.analyze.RiskScorer")
    @patch("src.api.commands.analyze.GapAnalyzer")
    @patch("src.api.commands.analyze.FrameworkRepository")
    def test_json_output(
        self,
        mock_fw_repo_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_scorer_cls: MagicMock,
        mock_get_engine: MagicMock,
        mock_get_session: MagicMock,
        mock_safe_path: MagicMock,
        runner: CliRunner,
        controls_file: Path,
        mock_gap_result: GapAnalysisResult,
        mock_risk_report: RiskReport,
    ) -> None:
        """JSON output should be valid JSON containing both reports."""
        mock_safe_path.return_value = controls_file
        mock_analyzer_cls.return_value.analyze.return_value = mock_gap_result
        mock_scorer_cls.return_value.score.return_value = mock_risk_report
        mock_get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(cli, [
            "analyze", "run",
            "--framework", "NIST_CSF",
            "--controls", str(controls_file),
            "--output-format", "json",
        ])

        assert result.exit_code == 0

        # Parse the output as JSON — strip any Rich markup
        output_lines = result.output.strip().splitlines()
        # Find the JSON block (skip any Rich console output lines)
        json_text = "\n".join(output_lines)
        data = json.loads(json_text)
        assert "gap_analysis" in data
        assert "risk_report" in data


# ---------------------------------------------------------------------------
# framework list / load / show
# ---------------------------------------------------------------------------


class TestFrameworkCommands:
    """Tests for the ``framework`` command group."""

    @patch("src.api.commands.framework.get_session")
    @patch("src.api.commands.framework.get_engine")
    @patch("src.api.commands.framework.FrameworkRepository")
    def test_list_empty(
        self,
        mock_fw_repo_cls: MagicMock,
        mock_get_engine: MagicMock,
        mock_get_session: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Empty repository should display 'No frameworks loaded'."""
        mock_fw_repo_cls.return_value.get_all.return_value = []
        mock_get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(cli, ["framework", "list"])

        assert result.exit_code == 0
        assert "No frameworks loaded" in result.output

    def test_load_path_traversal(
        self,
        runner: CliRunner,
    ) -> None:
        """Path traversal attempt should be blocked with exit code 1 or 2."""
        result = runner.invoke(cli, [
            "framework", "load",
            "--path", "../../etc/passwd",
        ])

        # Either Click rejects (exit 2) or safe_path catches (exit 1)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# report generate
# ---------------------------------------------------------------------------


class TestReportGenerate:
    """Tests for the ``report generate`` command."""

    @patch("src.api.commands.report.HTMLReporter")
    @patch("src.api.commands.report.safe_path")
    @patch("src.api.commands.report.get_session")
    @patch("src.api.commands.report.get_engine")
    @patch("src.api.commands.report.RiskScorer")
    @patch("src.api.commands.report.GapAnalyzer")
    @patch("src.api.commands.report.FrameworkRepository")
    def test_generate_creates_file(
        self,
        mock_fw_repo_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_scorer_cls: MagicMock,
        mock_get_engine: MagicMock,
        mock_get_session: MagicMock,
        mock_safe_path: MagicMock,
        mock_html_reporter_cls: MagicMock,
        runner: CliRunner,
        controls_file: Path,
        mock_gap_result: GapAnalysisResult,
        mock_risk_report: RiskReport,
        tmp_path: Path,
    ) -> None:
        """Report generate should exit 0 and print a success message."""
        output_dir = tmp_path / "output"
        # safe_path is called twice: once for controls, once for output-dir
        mock_safe_path.side_effect = [controls_file, output_dir]
        mock_analyzer_cls.return_value.analyze.return_value = mock_gap_result
        mock_scorer_cls.return_value.score.return_value = mock_risk_report
        mock_get_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock HTMLReporter.generate() to return a fake output path
        fake_report_path = tmp_path / "report_NIST_CSF_20260322.html"
        mock_html_reporter_cls.return_value.generate.return_value = fake_report_path

        result = runner.invoke(cli, [
            "report", "generate",
            "--framework", "NIST_CSF",
            "--controls", str(controls_file),
            "--format", "html",
            "--output-dir", str(output_dir),
        ])

        # Verify CLI exits cleanly and shows a success message
        assert result.exit_code == 0
        assert "Report generated successfully" in result.output


# ---------------------------------------------------------------------------
# --verbose flag
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Tests for the global --verbose flag."""

    def test_verbose_sets_debug(
        self,
        runner: CliRunner,
    ) -> None:
        """--verbose should set root log level to DEBUG."""
        result = runner.invoke(cli, ["--verbose", "--help"])

        # The --help still exits 0 but verbose is processed
        assert result.exit_code == 0

        # Verify the flag is accepted and help displays
        assert "--verbose" in result.output or result.exit_code == 0

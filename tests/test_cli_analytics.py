# -*- coding: utf-8 -*-
"""CLI tests for analytics command group with mocked dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.api.cli import cli
from src.core.analytics import AnalyticsSummary


# Verify `analytics summary` exits cleanly with valid mocked pipeline inputs.
@patch("src.api.commands.analytics.safe_path")
@patch("src.api.commands.analytics._build_pipeline")
@patch("src.api.commands.analytics._close_pipeline_session")
@patch("src.api.commands.analytics._trend_tracker")
def test_analytics_summary_valid_inputs_exit_zero(
    mock_tracker: MagicMock,
    _mock_close: MagicMock,
    mock_build_pipeline: MagicMock,
    mock_safe_path: MagicMock,
    tmp_path: Path,
    mock_gap_result,
    mock_risk_report,
) -> None:
    # Create controls input file required by click.Path(exists=True).
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\nDE.CM-1\n", encoding="utf-8")
    # Build a summary object returned by the mocked analytics engine.
    summary = AnalyticsSummary(
        framework_name="NIST_CSF",
        compliance_percentage=75.0,
        risk_score=82.4,
        maturity_level="DEFINED",
        total_controls=20,
        critical_gaps=1,
        high_gaps=2,
        medium_gaps=2,
        low_gaps=0,
        generated_at=datetime.now(tz=UTC),
    )
    # Configure pipeline components and safe path behavior.
    analytics_engine = MagicMock()
    gap_analyzer = MagicMock()
    risk_scorer = MagicMock()
    analytics_engine.summarize.return_value = summary
    gap_analyzer.analyze.return_value = mock_gap_result
    risk_scorer.score.return_value = mock_risk_report
    mock_build_pipeline.return_value = (analytics_engine, gap_analyzer, risk_scorer)
    mock_safe_path.return_value = controls_file
    # Invoke analytics summary command.
    result = CliRunner().invoke(
        cli,
        ["analytics", "summary", "--framework", "NIST_CSF", "--controls", str(controls_file)],
    )
    # Assert command succeeds and prints summary panel output.
    assert result.exit_code == 0
    assert "Analytics Summary" in result.output


# Verify `analytics summary` output includes maturity level details.
@patch("src.api.commands.analytics.safe_path")
@patch("src.api.commands.analytics._build_pipeline")
@patch("src.api.commands.analytics._close_pipeline_session")
@patch("src.api.commands.analytics._trend_tracker")
def test_analytics_summary_displays_maturity_level(
    mock_tracker: MagicMock,
    _mock_close: MagicMock,
    mock_build_pipeline: MagicMock,
    mock_safe_path: MagicMock,
    tmp_path: Path,
    mock_gap_result,
    mock_risk_report,
) -> None:
    # Create controls file to satisfy path validation.
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\n", encoding="utf-8")
    # Create summary with explicit maturity value.
    summary = AnalyticsSummary(
        framework_name="NIST_CSF",
        compliance_percentage=80.0,
        risk_score=55.0,
        maturity_level="MANAGED",
        total_controls=20,
        critical_gaps=0,
        high_gaps=1,
        medium_gaps=2,
        low_gaps=1,
        generated_at=datetime.now(tz=UTC),
    )
    # Configure mocked pipeline returns.
    analytics_engine = MagicMock()
    analytics_engine.summarize.return_value = summary
    gap_analyzer = MagicMock()
    gap_analyzer.analyze.return_value = mock_gap_result
    risk_scorer = MagicMock()
    risk_scorer.score.return_value = mock_risk_report
    mock_build_pipeline.return_value = (analytics_engine, gap_analyzer, risk_scorer)
    mock_safe_path.return_value = controls_file
    # Invoke summary command and capture output.
    result = CliRunner().invoke(
        cli,
        ["analytics", "summary", "--framework", "NIST_CSF", "--controls", str(controls_file)],
    )
    # Assert maturity level is surfaced in command output.
    assert result.exit_code == 0
    assert "MANAGED" in result.output


# Verify `analytics trend` shows no-data message when tracker has no history.
@patch("src.api.commands.analytics._trend_tracker")
def test_analytics_trend_no_recorded_data_shows_empty_message(mock_tracker: MagicMock) -> None:
    # Configure tracker to return no trend entries.
    mock_tracker.get_trend.return_value = []
    # Invoke trend command with valid framework option.
    result = CliRunner().invoke(cli, ["analytics", "trend", "--framework", "NIST_CSF"])
    # Assert command succeeds and shows empty-state message.
    assert result.exit_code == 0
    assert "No trend data recorded" in result.output


# Verify `analytics top-risks` renders ranked risk findings list.
@patch("src.api.commands.analytics.safe_path")
@patch("src.api.commands.analytics._build_pipeline")
@patch("src.api.commands.analytics._close_pipeline_session")
def test_analytics_top_risks_returns_ranked_list(
    _mock_close: MagicMock,
    mock_build_pipeline: MagicMock,
    mock_safe_path: MagicMock,
    tmp_path: Path,
    mock_gap_result,
    mock_risk_report,
) -> None:
    # Create controls file for click path argument.
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\nDE.CM-1\n", encoding="utf-8")
    # Build mocked top findings sorted by risk score.
    top_findings = [
        SimpleNamespace(
            control_id="PR.AC-1",
            control_name="Identity management",
            severity="CRITICAL",
            risk_score=90.25,
            likelihood=0.95,
            impact=0.95,
        ),
        SimpleNamespace(
            control_id="DE.CM-1",
            control_name="Continuous monitoring",
            severity="HIGH",
            risk_score=64.0,
            likelihood=0.8,
            impact=0.8,
        ),
    ]
    # Configure pipeline return values.
    analytics_engine = MagicMock()
    analytics_engine.top_priority_controls.return_value = top_findings
    gap_analyzer = MagicMock()
    gap_analyzer.analyze.return_value = mock_gap_result
    risk_scorer = MagicMock()
    risk_scorer.score.return_value = mock_risk_report
    mock_build_pipeline.return_value = (analytics_engine, gap_analyzer, risk_scorer)
    mock_safe_path.return_value = controls_file
    # Invoke top-risks command.
    result = CliRunner().invoke(
        cli,
        ["analytics", "top-risks", "--framework", "NIST_CSF", "--controls", str(controls_file), "--limit", "2"],
    )
    # Assert command succeeds and includes ranking rows.
    assert result.exit_code == 0
    assert "Top 2 Risk Findings" in result.output
    assert "PR.AC-1" in result.output


# Verify `analytics improvement` shows no-history message when unavailable.
@patch("src.api.commands.analytics._trend_tracker")
def test_analytics_improvement_no_history_shows_message(mock_tracker: MagicMock) -> None:
    # Force improvement call to fail with expected no-history text.
    mock_tracker.calculate_improvement.side_effect = ValueError("No history available")
    # Invoke improvement command.
    result = CliRunner().invoke(cli, ["analytics", "improvement", "--framework", "NIST_CSF"])
    # Assert command fails and displays expected error message text.
    assert result.exit_code == 1
    assert "No history available" in result.output

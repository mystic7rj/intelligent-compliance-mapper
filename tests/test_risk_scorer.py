# -*- coding: utf-8 -*-
"""Tests for the RiskScorer — scoring, classification, and edge cases.

Uses hand-crafted ``GapAnalysisResult`` objects — no database or
repository involvement.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.core.exceptions import RiskScoringError
from src.core.gap_analyzer import Control, GapAnalysisResult
from src.core.risk_scorer import RiskReport, RiskScorer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gap_result(
    missing: list[Control],
    total: int | None = None,
    implemented: int = 0,
    compliance_pct: float = 0.0,
) -> GapAnalysisResult:
    """Construct a GapAnalysisResult for testing."""
    t = total if total is not None else len(missing) + implemented
    return GapAnalysisResult(
        framework_name="NIST_CSF",
        total_controls=t,
        implemented_count=implemented,
        missing_controls=missing,
        compliance_percentage=compliance_pct,
        analyzed_at=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def scorer() -> RiskScorer:
    """Return a fresh RiskScorer instance."""
    return RiskScorer()


@pytest.fixture()
def high_gap_result() -> GapAnalysisResult:
    """Gap result with many critical/high missing controls → expect HIGH/CRITICAL."""
    missing = [
        Control(control_id="PR.AC-1", title="Access control", priority="critical"),
        Control(control_id="PR.DS-1", title="Data protection", priority="critical"),
        Control(control_id="DE.CM-1", title="Monitoring", priority="high"),
        Control(control_id="ID.AM-1", title="Asset inventory", priority="high"),
        Control(control_id="RS.RP-1", title="Response planning", priority="high"),
    ]
    return _make_gap_result(missing, total=6, implemented=1, compliance_pct=16.67)


@pytest.fixture()
def low_gap_result() -> GapAnalysisResult:
    """Gap result with one low-priority missing control → expect LOW."""
    missing = [
        Control(control_id="RC.CO-1", title="Recovery comms", priority="low"),
    ]
    return _make_gap_result(missing, total=10, implemented=9, compliance_pct=90.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHighGap:
    """High gap percentage should produce CRITICAL or HIGH risk."""

    def test_risk_level_is_high_or_critical(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        assert report.overall_risk_level in {"HIGH", "CRITICAL"}

    def test_report_is_risk_report(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        assert isinstance(report, RiskReport)


class TestLowGap:
    """Low gap percentage should produce LOW risk."""

    def test_risk_level_is_low(
        self, scorer: RiskScorer, low_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(low_gap_result)
        assert report.overall_risk_level == "LOW"


class TestRiskScoreBounds:
    """Risk score must always be between 0.0 and 100.0."""

    def test_score_within_bounds(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        assert 0.0 <= report.risk_score <= 100.0

    def test_individual_findings_within_bounds(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        for finding in report.findings:
            assert 0.0 <= finding.risk_score <= 100.0
            assert 0.0 <= finding.likelihood <= 1.0
            assert 0.0 <= finding.impact <= 1.0


class TestRecommendations:
    """RiskReport must always contain at least 1 recommendation."""

    def test_at_least_one_recommendation(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        assert len(report.recommendations) >= 1

    def test_max_three_recommendations(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        assert len(report.recommendations) <= 3

    def test_single_missing_produces_one_recommendation(
        self, scorer: RiskScorer, low_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(low_gap_result)
        assert len(report.recommendations) == 1


class TestEmptyGapRaises:
    """Empty gap result must raise RiskScoringError."""

    def test_no_missing_controls_raises(self, scorer: RiskScorer) -> None:
        empty_gap = _make_gap_result(
            missing=[],
            total=10,
            implemented=10,
            compliance_pct=100.0,
        )
        with pytest.raises(RiskScoringError, match="no missing controls"):
            scorer.score(empty_gap)


class TestReportImmutability:
    """RiskReport and RiskFinding are frozen Pydantic models."""

    def test_report_is_immutable(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        with pytest.raises(PydanticValidationError):
            report.risk_score = 0.0  # type: ignore[misc]

    def test_finding_is_immutable(
        self, scorer: RiskScorer, high_gap_result: GapAnalysisResult
    ) -> None:
        report = scorer.score(high_gap_result)
        with pytest.raises(PydanticValidationError):
            report.findings[0].risk_score = 0.0  # type: ignore[misc]

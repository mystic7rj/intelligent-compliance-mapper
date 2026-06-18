# -*- coding: utf-8 -*-
"""Tests for maturity model scoring and output guarantees."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.core.gap_analyzer import Control, GapAnalysisResult
from src.core.maturity_model import MaturityLevel, MaturityModel
from src.core.risk_scorer import RiskFinding, RiskReport


# Build a minimal gap result for a target compliance percentage.
def _make_gap_result(compliance_percentage: float) -> GapAnalysisResult:
    # Keep one missing control so dependent models remain realistic.
    missing_controls = [
        Control(
            control_id="PR.AC-1",
            title="Access control",
            description="",
            priority="high",
        )
    ]

    # Return immutable gap analysis input model.
    return GapAnalysisResult(
        framework_name="NIST_CSF",
        total_controls=10,
        implemented_count=0,
        missing_controls=missing_controls,
        compliance_percentage=compliance_percentage,
        analyzed_at=datetime.now(tz=UTC),
    )


# Build a minimal risk report input for maturity calculations.
def _make_risk_report() -> RiskReport:
    # Keep one risk finding to satisfy report structure.
    findings = [
        RiskFinding(
            control_id="PR.AC-1",
            control_name="Access control",
            severity="HIGH",
            likelihood=0.8,
            impact=0.8,
            risk_score=64.0,
        )
    ]

    # Return immutable risk report input model.
    return RiskReport(
        overall_risk_level="HIGH",
        risk_score=64.0,
        findings=findings,
        recommendations=["Prioritize access control remediation."],
        scored_at=datetime.now(tz=UTC),
    )


# Provide a fresh maturity model instance for each test.
@pytest.fixture()
def maturity_model() -> MaturityModel:
    # Return pure calculation model under test.
    return MaturityModel()


# Test that 0% compliance maps to INITIAL level.
def test_zero_percent_returns_initial(maturity_model: MaturityModel) -> None:
    # Calculate maturity for zero compliance input.
    result = maturity_model.calculate(_make_gap_result(0.0), _make_risk_report())

    # Verify the expected maturity level.
    assert result.level == MaturityLevel.INITIAL


# Test that 50% compliance maps to DEFINED level.
def test_fifty_percent_returns_defined(maturity_model: MaturityModel) -> None:
    # Calculate maturity for mid-range compliance input.
    result = maturity_model.calculate(_make_gap_result(50.0), _make_risk_report())

    # Verify the expected maturity level.
    assert result.level == MaturityLevel.DEFINED


# Test that 100% compliance maps to OPTIMIZING level.
def test_hundred_percent_returns_optimizing(maturity_model: MaturityModel) -> None:
    # Calculate maturity for full compliance input.
    result = maturity_model.calculate(_make_gap_result(100.0), _make_risk_report())

    # Verify the expected maturity level.
    assert result.level == MaturityLevel.OPTIMIZING


# Test that the returned MaturityScore object is immutable.
def test_maturity_score_is_immutable(maturity_model: MaturityModel) -> None:
    # Build one maturity result for mutation checks.
    result = maturity_model.calculate(_make_gap_result(60.0), _make_risk_report())

    # Verify mutation is blocked by frozen model config.
    with pytest.raises(PydanticValidationError):
        result.score = 10.0  # type: ignore[misc]


# Test that each maturity level provides at least one recommendation.
def test_recommendations_non_empty_for_every_level(maturity_model: MaturityModel) -> None:
    # Cover each maturity band using representative compliance values.
    compliance_values = [0.0, 30.0, 50.0, 70.0, 90.0]

    # Assert recommendations list is not empty for each computed level.
    for compliance in compliance_values:
        score = maturity_model.calculate(_make_gap_result(compliance), _make_risk_report())
        assert len(score.recommendations) > 0


# Test that calculated scores always stay within 0.0 to 100.0.
def test_score_is_between_zero_and_hundred(maturity_model: MaturityModel) -> None:
    # Exercise boundary and typical compliance inputs.
    compliance_values = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]

    # Verify each resulting maturity score remains in allowed bounds.
    for compliance in compliance_values:
        score = maturity_model.calculate(_make_gap_result(compliance), _make_risk_report())
        assert 0.0 <= score.score <= 100.0

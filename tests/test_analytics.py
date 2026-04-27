"""Tests for analytics summary, comparison, and prioritization."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from src.core.analytics import AnalyticsEngine, AnalyticsSummary
from src.core.gap_analyzer import Control, GapAnalysisResult
from src.core.risk_scorer import RiskFinding, RiskReport


# Mock maturity model dependency to avoid real maturity calculations.
class MockMaturityModel:
    # Return a fixed maturity object that exposes level.name.
    def calculate(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
    ) -> SimpleNamespace:
        # Keep behavior deterministic for analytics tests.
        _ = (gap_result, risk_report)
        return SimpleNamespace(level=SimpleNamespace(name="DEFINED"))


# Build a representative gap result used across tests.
def _make_gap_result() -> GapAnalysisResult:
    # Create four missing controls to align with four risk findings.
    missing_controls = [
        Control(control_id="PR.AC-1", title="Access control", priority="critical"),
        Control(control_id="DE.CM-1", title="Monitoring", priority="high"),
        Control(control_id="RS.RP-1", title="Response planning", priority="medium"),
        Control(control_id="RC.CO-1", title="Recovery", priority="low"),
    ]

    # Return immutable gap analysis model.
    return GapAnalysisResult(
        framework_name="NIST_CSF",
        total_controls=20,
        implemented_count=16,
        missing_controls=missing_controls,
        compliance_percentage=80.0,
        analyzed_at=datetime.now(tz=UTC),
    )


# Build a representative risk report used across tests.
def _make_risk_report() -> RiskReport:
    # Create findings with mixed severities and sortable scores.
    findings = [
        RiskFinding(
            control_id="PR.AC-1",
            control_name="Access control",
            severity="CRITICAL",
            likelihood=0.95,
            impact=0.95,
            risk_score=90.25,
        ),
        RiskFinding(
            control_id="DE.CM-1",
            control_name="Monitoring",
            severity="HIGH",
            likelihood=0.8,
            impact=0.8,
            risk_score=64.0,
        ),
        RiskFinding(
            control_id="RS.RP-1",
            control_name="Response planning",
            severity="MEDIUM",
            likelihood=0.5,
            impact=0.6,
            risk_score=30.0,
        ),
        RiskFinding(
            control_id="RC.CO-1",
            control_name="Recovery",
            severity="LOW",
            likelihood=0.3,
            impact=0.3,
            risk_score=9.0,
        ),
    ]

    # Return immutable risk report model.
    return RiskReport(
        overall_risk_level="HIGH",
        risk_score=48.31,
        findings=findings,
        recommendations=["Address critical controls first."],
        scored_at=datetime.now(tz=UTC),
    )


# Build analytics engine with injected mock maturity dependency.
def _make_engine() -> AnalyticsEngine:
    # Inject deterministic mock model into engine constructor.
    return AnalyticsEngine(maturity_model=MockMaturityModel())


# Test that summarize returns a populated AnalyticsSummary model.
def test_summarize_returns_full_summary() -> None:
    # Build engine and input models.
    engine = _make_engine()
    gap_result = _make_gap_result()
    risk_report = _make_risk_report()

    # Run summary generation under test.
    summary = engine.summarize(gap_result, risk_report)

    # Validate model type and required fields.
    assert isinstance(summary, AnalyticsSummary)
    assert summary.framework_name == "NIST_CSF"
    assert summary.compliance_percentage == 80.0
    assert summary.risk_score == 48.31
    assert summary.maturity_level == "DEFINED"
    assert summary.total_controls == 20
    assert summary.generated_at is not None


# Test that severity bucket counts match total missing controls.
def test_gap_counts_sum_to_total_missing_controls() -> None:
    # Generate summary from aligned gap and risk fixtures.
    engine = _make_engine()
    gap_result = _make_gap_result()
    summary = engine.summarize(gap_result, _make_risk_report())

    # Sum severity buckets present in summary.
    severity_total = (
        summary.critical_gaps
        + summary.high_gaps
        + summary.medium_gaps
        + summary.low_gaps
    )

    # Verify summed severity counts equal missing controls count.
    assert severity_total == len(gap_result.missing_controls)


# Test compare_summaries returns required delta keys.
def test_compare_summaries_returns_expected_delta_keys() -> None:
    # Build two analytics snapshots for comparison.
    a = AnalyticsSummary(
        framework_name="NIST_CSF",
        compliance_percentage=70.0,
        risk_score=55.0,
        maturity_level="DEVELOPING",
        total_controls=20,
        critical_gaps=2,
        high_gaps=2,
        medium_gaps=1,
        low_gaps=0,
        generated_at=datetime.now(tz=UTC),
    )
    b = AnalyticsSummary(
        framework_name="NIST_CSF",
        compliance_percentage=85.0,
        risk_score=40.0,
        maturity_level="MANAGED",
        total_controls=20,
        critical_gaps=1,
        high_gaps=1,
        medium_gaps=1,
        low_gaps=0,
        generated_at=datetime.now(tz=UTC),
    )

    # Compare snapshots and capture delta payload.
    deltas = _make_engine().compare_summaries(a, b)

    # Verify required comparison keys are present.
    assert "compliance_change" in deltas
    assert "risk_change" in deltas
    assert "maturity_change" in deltas


# Test top_priority_controls returns descending risk order.
def test_top_priority_controls_sorted_descending() -> None:
    # Compute ranked findings from test risk report.
    findings = _make_engine().top_priority_controls(_make_risk_report(), limit=10)

    # Extract scores and verify descending sort order.
    scores = [finding.risk_score for finding in findings]
    assert scores == sorted(scores, reverse=True)


# Test top_priority_controls respects the requested limit.
def test_top_priority_controls_respects_limit() -> None:
    # Request only top two findings from report.
    findings = _make_engine().top_priority_controls(_make_risk_report(), limit=2)

    # Verify output length is capped by limit value.
    assert len(findings) == 2

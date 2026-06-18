# -*- coding: utf-8 -*-
"""Analytics engine for compliance summary and prioritization.

Builds unified analytics summaries from gap and risk outputs and supports
comparisons and top-priority control extraction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.gap_analyzer import GapAnalysisResult
from src.core.maturity_model import MaturityModel
from src.core.risk_scorer import RiskFinding, RiskReport
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsSummary(BaseModel):
    """Immutable analytics snapshot for one framework.
    
    Aggregates gap analysis, risk scoring, and maturity assessment into
    a single unified view suitable for reporting and trending.
    """

    # PATTERN: Immutable Value Object — frozen prevents accidental mutations
    model_config = ConfigDict(frozen=True)

    # Framework that this summary describes (e.g., "NIST_CSF")
    framework_name: str
    
    # Percentage of framework controls that are implemented (0.0-100.0)
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    
    # Aggregated risk score from missing controls (0.0-100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    
    # Maturity level name (e.g., "DEVELOPING", "MANAGED")
    maturity_level: str
    
    # Total number of controls in the framework
    total_controls: int = Field(ge=0)
    
    # Count of missing controls classified as CRITICAL severity
    critical_gaps: int = Field(ge=0)
    
    # Count of missing controls classified as HIGH severity
    high_gaps: int = Field(ge=0)
    
    # Count of missing controls classified as MEDIUM severity
    medium_gaps: int = Field(ge=0)
    
    # Count of missing controls classified as LOW severity
    low_gaps: int = Field(ge=0)
    
    # UTC timestamp when this summary was generated
    generated_at: datetime


class AnalyticsEngine:
    """Computes analytics summaries and trend-friendly deltas."""

    # Initialize engine with injected maturity model dependency.
    def __init__(self, maturity_model: MaturityModel) -> None:
        # Store maturity model dependency for scoring level.
        self._maturity_model = maturity_model

    # Build a complete immutable analytics summary from pipeline outputs.
    def summarize(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
    ) -> AnalyticsSummary:
        # Compute maturity score from existing gap and risk results.
        maturity = self._maturity_model.calculate(gap_result, risk_report)

        # Count missing controls by risk severity bucket.
        severity_counts = self._count_severities(risk_report.findings)

        # Build immutable analytics summary object.
        summary = AnalyticsSummary(
            framework_name=gap_result.framework_name,
            compliance_percentage=round(gap_result.compliance_percentage, 2),
            risk_score=round(risk_report.risk_score, 2),
            maturity_level=maturity.level.name,
            total_controls=gap_result.total_controls,
            critical_gaps=severity_counts["CRITICAL"],
            high_gaps=severity_counts["HIGH"],
            medium_gaps=severity_counts["MEDIUM"],
            low_gaps=severity_counts["LOW"],
            generated_at=datetime.now(tz=UTC),
        )

        # Log summary creation for observability.
        logger.info(
            "Analytics summary generated",
            extra={
                "framework": summary.framework_name,
                "compliance": summary.compliance_percentage,
                "risk_score": summary.risk_score,
                "maturity_level": summary.maturity_level,
            },
        )

        # Return completed summary model.
        return summary

    # Compare two summaries and return delta dictionary using b - a semantics.
    def compare_summaries(
        self,
        a: AnalyticsSummary,
        b: AnalyticsSummary,
    ) -> dict[str, float | str]:
        # Calculate compliance delta as newer minus older.
        compliance_change = round(b.compliance_percentage - a.compliance_percentage, 2)

        # Calculate risk delta as newer minus older.
        risk_change = round(b.risk_score - a.risk_score, 2)

        # Build maturity change label from prior to current.
        maturity_change = f"{a.maturity_level} -> {b.maturity_level}"

        # Return dictionary of requested comparison metrics.
        return {
            "compliance_change": compliance_change,
            "risk_change": risk_change,
            "maturity_change": maturity_change,
        }

    # Return top N findings sorted by descending risk score.
    def top_priority_controls(
        self,
        risk_report: RiskReport,
        limit: int = 10,
    ) -> list[RiskFinding]:
        # Clamp limit to at least one to avoid empty slicing surprises.
        safe_limit = max(1, int(limit))

        # Sort findings descending by risk score.
        sorted_findings = sorted(
            risk_report.findings,
            key=lambda finding: finding.risk_score,
            reverse=True,
        )

        # Return top controls bounded by requested limit.
        return sorted_findings[:safe_limit]

    # Count findings per severity for analytics summary fields.
    @staticmethod
    def _count_severities(findings: list[RiskFinding]) -> dict[str, int]:
        # Initialize severity counters with required buckets.
        counts: dict[str, int] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }

        # Aggregate each finding into its severity bucket.
        for finding in findings:
            counts[finding.severity] += 1

        # Return final severity count mapping.
        return counts

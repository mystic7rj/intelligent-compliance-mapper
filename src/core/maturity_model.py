"""Maturity scoring model for compliance analytics.

Maps compliance and risk outcomes to a maturity level with actionable
recommendations. This module is pure calculation logic with no side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field

from src.core.gap_analyzer import GapAnalysisResult
from src.core.risk_scorer import RiskReport
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MaturityLevel(IntEnum):
    """Maturity level scale from ad-hoc to optimized controls."""

    INITIAL = 1
    DEVELOPING = 2
    DEFINED = 3
    MANAGED = 4
    OPTIMIZING = 5


class MaturityScore(BaseModel):
    """Immutable maturity scoring output for a framework."""

    model_config = ConfigDict(frozen=True)

    framework_name: str
    level: MaturityLevel
    score: float = Field(ge=0.0, le=100.0)
    description: str
    recommendations: list[str]
    scored_at: datetime


class MaturityModel:
    """Calculates maturity score from gap and risk outputs."""

    # Return maturity output from compliance and risk inputs.
    def calculate(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
    ) -> MaturityScore:
        # Read and normalize compliance score from gap analysis.
        compliance_score = float(gap_result.compliance_percentage)

        # Resolve maturity level from compliance threshold mapping.
        level = self._level_from_compliance(compliance_score)

        # Build human-readable description for the selected maturity level.
        description = self._description_for_level(level, risk_report.risk_score)

        # Build actionable recommendations for the selected maturity level.
        recommendations = self._recommendations_for_level(level)

        # Log scoring outcome for observability.
        logger.info(
            "Maturity score calculated",
            extra={
                "framework": gap_result.framework_name,
                "score": compliance_score,
                "level": level.name,
            },
        )

        # Return immutable maturity score object.
        return MaturityScore(
            framework_name=gap_result.framework_name,
            level=level,
            score=round(compliance_score, 2),
            description=description,
            recommendations=recommendations,
            scored_at=datetime.now(tz=UTC),
        )

    # Map a compliance percentage to a maturity level enum.
    @staticmethod
    def _level_from_compliance(compliance_score: float) -> MaturityLevel:
        # Map 0–20 to INITIAL.
        if compliance_score <= 20.0:
            return MaturityLevel.INITIAL

        # Map 21–40 to DEVELOPING.
        if compliance_score <= 40.0:
            return MaturityLevel.DEVELOPING

        # Map 41–60 to DEFINED.
        if compliance_score <= 60.0:
            return MaturityLevel.DEFINED

        # Map 61–80 to MANAGED.
        if compliance_score <= 80.0:
            return MaturityLevel.MANAGED

        # Map 81–100 to OPTIMIZING.
        return MaturityLevel.OPTIMIZING

    # Build a concise maturity description for display.
    @staticmethod
    def _description_for_level(level: MaturityLevel, risk_score: float) -> str:
        # Return description for INITIAL level.
        if level == MaturityLevel.INITIAL:
            return (
                "Controls are mostly ad hoc and reactive. "
                f"Current risk exposure remains elevated (risk score {risk_score:.2f})."
            )

        # Return description for DEVELOPING level.
        if level == MaturityLevel.DEVELOPING:
            return (
                "Core controls are emerging but inconsistent. "
                f"Risk posture is improving yet still material (risk score {risk_score:.2f})."
            )

        # Return description for DEFINED level.
        if level == MaturityLevel.DEFINED:
            return (
                "Security practices are documented and repeatable across teams. "
                f"Risk posture is moderate (risk score {risk_score:.2f})."
            )

        # Return description for MANAGED level.
        if level == MaturityLevel.MANAGED:
            return (
                "Controls are measured, monitored, and actively governed. "
                f"Residual risk is controlled (risk score {risk_score:.2f})."
            )

        # Return description for OPTIMIZING level.
        return (
            "Controls are continuously improved with strong operational feedback loops. "
            f"Residual risk is comparatively low (risk score {risk_score:.2f})."
        )

    # Build recommendations tailored to the maturity level.
    @staticmethod
    def _recommendations_for_level(level: MaturityLevel) -> list[str]:
        # Return recommendations for INITIAL level.
        if level == MaturityLevel.INITIAL:
            return [
                "Establish baseline security policies and control ownership.",
                "Prioritize remediation of critical and high-severity gaps first.",
                "Implement minimum viable monitoring for key assets and access.",
            ]

        # Return recommendations for DEVELOPING level.
        if level == MaturityLevel.DEVELOPING:
            return [
                "Standardize control implementation workflows across teams.",
                "Introduce periodic control testing and evidence collection.",
                "Expand incident response coverage and run tabletop exercises.",
            ]

        # Return recommendations for DEFINED level.
        if level == MaturityLevel.DEFINED:
            return [
                "Automate recurring compliance checks where feasible.",
                "Strengthen KPI-based oversight for control performance.",
                "Integrate risk findings into engineering and change planning.",
            ]

        # Return recommendations for MANAGED level.
        if level == MaturityLevel.MANAGED:
            return [
                "Increase predictive analytics for control failures and drift.",
                "Continuously tune controls using incident and audit feedback.",
                "Benchmark maturity outcomes across business units.",
            ]

        # Return recommendations for OPTIMIZING level.
        return [
            "Maintain continuous improvement cadences and peer reviews.",
            "Share proven control patterns across broader operations.",
            "Focus on strategic resilience and emerging threat adaptation.",
        ]

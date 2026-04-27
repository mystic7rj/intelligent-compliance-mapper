"""Risk scoring engine for the Compliance Mapper.

Applies a simplified FAIR (Factor Analysis of Information Risk)
methodology to a ``GapAnalysisResult`` and produces an immutable
``RiskReport``.  Standalone — no external dependencies injected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.exceptions import RiskScoringError
from src.core.gap_analyzer import GapAnalysisResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — FAIR-inspired calibration tables
# ---------------------------------------------------------------------------

# PATTERN: Strategy — these lookup tables define risk scoring strategies
# Based on FAIR (Factor Analysis of Information Risk) methodology
# Maps control priority levels to (likelihood, impact) probability tuples
_PRIORITY_FACTORS: dict[str, tuple[float, float]] = {
    # (likelihood of exploitation, impact if exploited)
    "critical": (0.95, 0.95),  # 95% likely, 95% impact
    "high": (0.80, 0.80),      # 80% likely, 80% impact
    "medium": (0.50, 0.60),    # 50% likely, 60% impact
    "low": (0.30, 0.30),       # 30% likely, 30% impact
}

# PATTERN: Strategy — control family weighting strategy for NIST CSF
# Reflects real-world risk impact of each NIST CSF function
_FAMILY_WEIGHTS: dict[str, float] = {
    "ID": 0.80,   # Identify — foundational but lower direct risk
    "PR": 1.00,   # Protect — highest risk impact (core defenses)
    "DE": 0.90,   # Detect — critical for breach detection
    "RS": 0.85,   # Respond — important for damage control
    "RC": 0.70,   # Recover — lowest immediate risk impact
}

# Fallback weight for controls not matching known families
_DEFAULT_FAMILY_WEIGHT: float = 0.75


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RiskFinding(BaseModel):
    """A single risk finding for one missing control."""

    model_config = ConfigDict(frozen=True)

    control_id: str
    control_name: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    likelihood: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=100.0)


class RiskReport(BaseModel):
    """Immutable report summarising overall risk posture."""

    model_config = ConfigDict(frozen=True)

    overall_risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: float = Field(ge=0.0, le=100.0)
    findings: list[RiskFinding]
    recommendations: list[str]
    scored_at: datetime


# ---------------------------------------------------------------------------
# RiskScorer
# ---------------------------------------------------------------------------


class RiskScorer:
    """Scores compliance risk using simplified FAIR methodology.

    Standalone class — no external dependencies are injected.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, gap_result: GapAnalysisResult) -> RiskReport:
        """Produce a ``RiskReport`` from a gap analysis result.

        Args:
            gap_result: Output of ``GapAnalyzer.analyze()``.

        Returns:
            An immutable ``RiskReport``.

        Raises:
            RiskScoringError: If *gap_result* has no missing controls.
        """
        if not gap_result.missing_controls:
            msg = "Cannot score risk — no missing controls in the gap result"
            raise RiskScoringError(msg)

        # 1. Score each missing control
        findings = [self._score_control(ctrl) for ctrl in gap_result.missing_controls]

        # 2. Compute overall risk score (average of individual scores)
        overall = sum(f.risk_score for f in findings) / len(findings)
        overall = round(min(overall, 100.0), 2)

        # 3. Classify risk level
        risk_level = self._classify_risk(overall)

        # 4. Auto-generate recommendations from top-3 riskiest findings
        recommendations = self._generate_recommendations(findings)

        report = RiskReport(
            overall_risk_level=risk_level,
            risk_score=overall,
            findings=findings,
            recommendations=recommendations,
            scored_at=datetime.now(tz=UTC),
        )

        logger.info(
            "Risk scoring complete",
            extra={
                "overall_risk": risk_level,
                "risk_score": overall,
                "findings_count": len(findings),
            },
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_control(ctrl: GapAnalysisResult.missing_controls) -> RiskFinding:  # type: ignore[name-defined]
        """Apply FAIR formula to a single missing control.

        ``risk_score = likelihood × impact × weight × 100``
        """
        priority = getattr(ctrl, "priority", "medium").lower()
        likelihood, impact = _PRIORITY_FACTORS.get(priority, (0.50, 0.60))

        # Derive family prefix from control_id (e.g. "ID.AM-1" → "ID")
        family_prefix = ctrl.control_id.split(".")[0] if "." in ctrl.control_id else ""
        weight = _FAMILY_WEIGHTS.get(family_prefix, _DEFAULT_FAMILY_WEIGHT)

        raw_score = likelihood * impact * weight * 100.0
        capped = round(min(raw_score, 100.0), 2)

        severity = RiskScorer._classify_risk(capped)

        return RiskFinding(
            control_id=ctrl.control_id,
            control_name=ctrl.title,
            severity=severity,
            likelihood=round(likelihood, 4),
            impact=round(impact, 4),
            risk_score=capped,
        )

    @staticmethod
    def _classify_risk(score: float) -> Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        """Map a 0–100 score to a risk level."""
        if score >= 75.0:
            return "CRITICAL"
        if score >= 50.0:
            return "HIGH"
        if score >= 25.0:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _generate_recommendations(findings: list[RiskFinding]) -> list[str]:
        """Return actionable recommendations for the top 3 riskiest findings."""
        sorted_findings = sorted(findings, key=lambda f: f.risk_score, reverse=True)
        top = sorted_findings[:3]
        recs: list[str] = []
        for i, finding in enumerate(top, start=1):
            recs.append(
                f"{i}. Prioritise implementation of control {finding.control_id} "
                f"({finding.control_name}) — {finding.severity} severity, "
                f"risk score {finding.risk_score}"
            )
        return recs

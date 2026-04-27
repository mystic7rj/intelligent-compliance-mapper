"""HTML report generator using Jinja2 templates.

Renders a professional compliance report as a standalone HTML file.
All dependencies are injected via the constructor — template directory
is never hardcoded.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jinja2

from src.core.exceptions import ReportGenerationError
from src.core.gap_analyzer import GapAnalysisResult
from src.core.risk_scorer import RiskReport
from src.reports.base_reporter import BaseReporter
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)


class HTMLReporter(BaseReporter):
    """Generate HTML compliance reports via Jinja2 templates.

    Args:
        template_dir: Absolute ``Path`` to the directory containing
            Jinja2 templates.  Validated through ``safe_path()`` at
            construction time.

    Raises:
        ReportGenerationError: If *template_dir* does not exist or
            fails security validation.
    """

    def __init__(self, template_dir: Path) -> None:
        # Validate template directory via safe_path
        if template_dir.is_absolute():
            base_dir = template_dir.resolve().parent
        else:
            base_dir = Path.cwd()

        try:
            validated_dir = safe_path(base_dir, template_dir)
        except SecurityError as exc:
            msg = f"Template directory failed security validation: {template_dir}"
            raise ReportGenerationError(msg, details={"cause": str(exc)}) from exc

        if not validated_dir.is_dir():
            msg = f"Template directory does not exist: {validated_dir}"
            raise ReportGenerationError(msg)

        self._template_dir = validated_dir
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(validated_dir)),
            autoescape=True,
        )
        logger.debug(
            "HTMLReporter initialised",
            extra={"template_dir": str(validated_dir)},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
        output_path: Path,
    ) -> Path:
        """Render an HTML report and write it to *output_path*.

        Args:
            gap_result: Gap analysis output.
            risk_report: Risk scoring output.
            output_path: Directory to write the report into.

        Returns:
            Absolute ``Path`` to the generated ``.html`` file.

        Raises:
            ReportGenerationError: On template or I/O errors.
            SecurityError: If *output_path* contains traversal.
        """
        # 1. Validate output directory
        validated_dir = self.validate_output_path(output_path)

        # 2. Build sanitised template context
        context = self._build_context(gap_result, risk_report)

        # 3. Load and render template
        try:
            template = self._env.get_template("report.html")
        except jinja2.TemplateNotFoundError as exc:
            msg = "Report template 'report.html' not found in template directory"
            raise ReportGenerationError(
                msg, details={"template_dir": str(self._template_dir)}
            ) from exc

        try:
            rendered = template.render(**context)
        except jinja2.TemplateError as exc:
            msg = f"Template rendering failed: {exc}"
            raise ReportGenerationError(msg) from exc

        # 4. Write to file
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"report_{context['framework_name']}_{timestamp}.html"
        report_path = validated_dir / filename

        try:
            report_path.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            msg = f"Failed to write report file: {report_path}"
            raise ReportGenerationError(
                msg, details={"cause": str(exc)}
            ) from exc

        logger.info(
            "HTML report generated",
            extra={"report_path": str(report_path)},
        )
        return report_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
    ) -> dict[str, Any]:
        """Build a sanitised template context from analysis results."""
        # Sanitise all text fields before passing to templates
        missing_controls = []
        for ctrl in gap_result.missing_controls:
            missing_controls.append({
                "control_id": self.sanitize_text(ctrl.control_id),
                "title": self.sanitize_text(ctrl.title),
                "description": self.sanitize_text(ctrl.description),
                "priority": self.sanitize_text(ctrl.priority),
            })

        findings = []
        for finding in risk_report.findings:
            findings.append({
                "control_id": self.sanitize_text(finding.control_id),
                "control_name": self.sanitize_text(finding.control_name),
                "severity": self.sanitize_text(finding.severity),
                "likelihood": finding.likelihood,
                "impact": finding.impact,
                "risk_score": finding.risk_score,
            })

        recommendations = [
            self.sanitize_text(rec) for rec in risk_report.recommendations
        ]

        # Compute severity counts for charts
        severity_counts = _count_severities(findings)

        return {
            "framework_name": self.sanitize_text(gap_result.framework_name),
            "total_controls": gap_result.total_controls,
            "implemented_count": gap_result.implemented_count,
            "compliance_percentage": gap_result.compliance_percentage,
            "analyzed_at": gap_result.analyzed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "missing_controls": missing_controls,
            "overall_risk_level": self.sanitize_text(risk_report.overall_risk_level),
            "risk_score": risk_report.risk_score,
            "findings": findings,
            "recommendations": recommendations,
            "severity_counts": severity_counts,
            "scored_at": risk_report.scored_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }


def _count_severities(findings: list[dict[str, Any]]) -> dict[str, int]:
    """Count findings per severity level."""
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        level = f["severity"].upper()
        if level in counts:
            counts[level] += 1
    return counts

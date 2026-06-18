# -*- coding: utf-8 -*-
"""PDF report generator using ReportLab.

Produces a professional compliance report as a standalone .pdf document
with cover page, executive summary table, gap analysis table, risk
summary, and page-number footers.  All dependencies are injected via
the constructor — template directory is never hardcoded.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.core.exceptions import ReportGenerationError
from src.core.gap_analyzer import GapAnalysisResult
from src.core.risk_scorer import RiskReport
from src.reports.base_reporter import BaseReporter
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — severity-to-colour mapping for ReportLab
# ---------------------------------------------------------------------------

# Red colour for CRITICAL severity
COLOR_CRITICAL = colors.red
# Orange colour for HIGH severity
COLOR_HIGH = colors.orange
# Yellow colour for MEDIUM severity
COLOR_MEDIUM = colors.yellow
# Green colour for LOW severity
COLOR_LOW = colors.green

# Map severity strings to their ReportLab colour constants
SEVERITY_COLORS: dict[str, colors.Color] = {
    "CRITICAL": COLOR_CRITICAL,
    "HIGH": COLOR_HIGH,
    "MEDIUM": COLOR_MEDIUM,
    "LOW": COLOR_LOW,
}

# Regex to strip HTML tags from text values
_HTML_TAG_RE = re.compile(r"<[^>]+>")


class PDFReporter(BaseReporter):
    """Generate PDF compliance reports via ReportLab platypus.

    Args:
        template_dir: Absolute ``Path`` to the template directory.
            Accepted for interface consistency with other reporters;
            not directly used by PDF generation.

    Raises:
        ReportGenerationError: If construction fails.
    """

    def __init__(self, template_dir: Path) -> None:
        # Store injected template directory for interface consistency
        self._template_dir = template_dir
        # Load default ReportLab paragraph styles
        self._styles = getSampleStyleSheet()
        logger.debug(
            "PDFReporter initialised",
            extra={"template_dir": str(template_dir)},
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
        """Generate a PDF report and write it to *output_path*.

        Args:
            gap_result: Gap analysis output.
            risk_report: Risk scoring output.
            output_path: Directory to write the report into.

        Returns:
            Absolute ``Path`` to the generated ``.pdf`` file.

        Raises:
            ReportGenerationError: On any PDF build or I/O error.
            SecurityError: If *output_path* contains traversal.
        """
        # Validate output directory via safe_path
        validated_dir = self.validate_output_path(output_path)

        # Construct output filename with framework name and timestamp
        framework_name = self._sanitize_text(gap_result.framework_name)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"report_{framework_name}_{timestamp}.pdf"
        report_path = validated_dir / filename

        # Store timestamp string for footers
        self._generation_timestamp = datetime.now(tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        try:
            # Build the PDF document using SimpleDocTemplate
            doc = SimpleDocTemplate(
                str(report_path),
                pagesize=A4,
                title=f"Compliance Report — {framework_name}",
                author="Compliance Mapper",
            )

            # Assemble all flowable elements in order
            elements: list[object] = []
            elements.extend(self._build_cover_page(gap_result))
            elements.extend(self._build_executive_summary(gap_result, risk_report))
            elements.extend(self._build_gap_analysis_table(gap_result))
            elements.extend(self._build_risk_summary(risk_report))

            # Build the PDF with a custom page-number footer
            doc.build(elements, onFirstPage=self._add_footer, onLaterPages=self._add_footer)

        except (OSError, ValueError, TypeError) as exc:
            msg = f"Failed to generate PDF report: {exc}"
            raise ReportGenerationError(msg, details={"cause": str(exc)}) from exc

        logger.info(
            "PDF report generated",
            extra={"report_path": str(report_path)},
        )
        return report_path

    # ------------------------------------------------------------------
    # Private section builders
    # ------------------------------------------------------------------

    def _build_cover_page(
        self,
        gap_result: GapAnalysisResult,
    ) -> list[object]:
        """Build the cover page: title, framework, date, compliance %."""
        elements: list[object] = []

        # Custom large title style for the cover page
        title_style = ParagraphStyle(
            "CoverTitle",
            parent=self._styles["Title"],
            fontSize=28,
            spaceAfter=30,
            alignment=1,  # Centred
        )

        # Custom subtitle style for secondary cover text
        subtitle_style = ParagraphStyle(
            "CoverSubtitle",
            parent=self._styles["Heading2"],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
        )

        # Large compliance percentage display style
        percentage_style = ParagraphStyle(
            "CoverPercentage",
            parent=self._styles["Title"],
            fontSize=48,
            textColor=colors.HexColor("#2E86AB"),
            spaceAfter=30,
            alignment=1,
        )

        # Add cover page elements
        elements.append(Spacer(1, 2 * inch))
        elements.append(Paragraph("Compliance Report", title_style))
        elements.append(
            Paragraph(
                f"Framework: {self._sanitize_text(gap_result.framework_name)}",
                subtitle_style,
            )
        )
        elements.append(
            Paragraph(
                f"Date: {datetime.now(tz=UTC).strftime('%Y-%m-%d')}",
                subtitle_style,
            )
        )
        elements.append(Spacer(1, 0.5 * inch))
        # Show compliance percentage as large text
        elements.append(
            Paragraph(
                f"{gap_result.compliance_percentage}%",
                percentage_style,
            )
        )
        elements.append(
            Paragraph("Overall Compliance", subtitle_style)
        )
        elements.append(Spacer(1, 2 * inch))

        return elements

    def _build_executive_summary(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
    ) -> list[object]:
        """Build the executive summary section as a 2-column table."""
        elements: list[object] = []

        # Section heading
        elements.append(
            Paragraph("Executive Summary", self._styles["Heading1"])
        )
        elements.append(Spacer(1, 0.2 * inch))

        # 2-column key-value table data
        table_data = [
            ["Metric", "Value"],
            ["Total Controls", str(gap_result.total_controls)],
            ["Implemented Controls", str(gap_result.implemented_count)],
            ["Missing Controls", str(len(gap_result.missing_controls))],
            [
                "Compliance Percentage",
                f"{gap_result.compliance_percentage}%",
            ],
            [
                "Overall Risk Level",
                self._sanitize_text(risk_report.overall_risk_level),
            ],
            ["Risk Score", str(risk_report.risk_score)],
        ]

        # Build the table with styling
        table = Table(table_data, colWidths=[3 * inch, 3 * inch])

        # Determine colour for the risk level row
        risk_level = risk_report.overall_risk_level.upper()
        risk_color = SEVERITY_COLORS.get(risk_level, colors.white)

        # Apply table styles: header row, grid, risk-level row colour
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (1, 5), (1, 5), risk_color),
            ])
        )

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))
        return elements

    def _build_gap_analysis_table(
        self,
        gap_result: GapAnalysisResult,
    ) -> list[object]:
        """Build the gap analysis table with severity colour coding."""
        elements: list[object] = []

        # Section heading
        elements.append(
            Paragraph("Gap Analysis — Missing Controls", self._styles["Heading1"])
        )
        elements.append(Spacer(1, 0.2 * inch))

        # Table header row
        table_data: list[list[str]] = [
            ["Control ID", "Control Name", "Severity"],
        ]

        # Row styles to be applied after building the data
        row_styles: list[tuple[str, tuple[int, int], tuple[int, int], colors.Color]] = []

        # Add one row per missing control
        for idx, ctrl in enumerate(gap_result.missing_controls):
            severity = self._sanitize_text(
                getattr(ctrl, "priority", "medium")
            ).upper()
            table_data.append([
                self._sanitize_text(ctrl.control_id),
                self._sanitize_text(ctrl.title),
                severity,
            ])

            # Queue severity background colour for this row
            severity_color = SEVERITY_COLORS.get(severity, colors.white)
            data_row = idx + 1  # offset by header
            row_styles.append(
                ("BACKGROUND", (2, data_row), (2, data_row), severity_color)
            )

        # Build and style the table
        table = Table(table_data, colWidths=[1.5 * inch, 3 * inch, 1.5 * inch])
        base_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        # Merge base styles with per-row severity colours
        table.setStyle(TableStyle(base_styles + row_styles))  # type: ignore[arg-type]

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))
        return elements

    def _build_risk_summary(
        self,
        risk_report: RiskReport,
    ) -> list[object]:
        """Build the risk summary section with top-3 recommendations."""
        elements: list[object] = []

        # Section heading
        elements.append(
            Paragraph("Risk Summary", self._styles["Heading1"])
        )
        elements.append(Spacer(1, 0.2 * inch))

        # Overall risk level paragraph
        risk_level = self._sanitize_text(risk_report.overall_risk_level)
        elements.append(
            Paragraph(
                f"<b>Overall Risk Level:</b> {risk_level}",
                self._styles["Normal"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>Risk Score:</b> {risk_report.risk_score}",
                self._styles["Normal"],
            )
        )
        elements.append(Spacer(1, 0.3 * inch))

        # Top 3 recommendations as a numbered list
        elements.append(
            Paragraph("Top Recommendations", self._styles["Heading2"])
        )
        for rec in risk_report.recommendations[:3]:
            sanitized_rec = self._sanitize_text(rec)
            elements.append(
                Paragraph(sanitized_rec, self._styles["Normal"])
            )
            elements.append(Spacer(1, 0.1 * inch))

        return elements

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_footer(
        self,
        canvas: object,
        doc: SimpleDocTemplate,
    ) -> None:
        """Draw page number and generation timestamp in the footer."""
        canvas.saveState()  # type: ignore[attr-defined]
        page_num = canvas.getPageNumber()  # type: ignore[attr-defined]
        footer_text = (
            f"Page {page_num} | Generated: {self._generation_timestamp}"
        )
        # Draw footer text centred at the bottom of the page
        canvas.setFont("Helvetica", 8)  # type: ignore[attr-defined]
        canvas.drawCentredString(  # type: ignore[attr-defined]
            A4[0] / 2, 0.5 * inch, footer_text,
        )
        canvas.restoreState()  # type: ignore[attr-defined]

    @staticmethod
    def _sanitize_text(value: str) -> str:
        """Strip HTML tags and special characters from text content.

        Prevents XSS and markup injection by removing all HTML tags
        and non-printable characters from the input string.

        Args:
            value: Raw string to sanitize.

        Returns:
            Clean string safe for PDF text elements.
        """
        # Strip HTML tags from the value
        cleaned = _HTML_TAG_RE.sub("", str(value))
        # Remove non-printable / special control characters
        cleaned = re.sub(r"[^\w\s.,;:!?%()\-/]", "", cleaned)
        return cleaned.strip()

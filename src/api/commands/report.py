"""Click command group for report generation.

Orchestrates the full analyze → risk-score pipeline and writes
reports via ``HTMLReporter``, ``ExcelReporter``, or ``PDFReporter``.
Contains zero business logic — only orchestration.  All file paths
validated through ``safe_path()``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

from src.core.exceptions import (
    FrameworkNotFoundError,
    GapAnalysisError,
    ReportGenerationError,
    RiskScoringError,
    ValidationError,
)
from src.reports.excel_reporter import ExcelReporter
from src.reports.html_reporter import HTMLReporter
from src.reports.pdf_reporter import PDFReporter
from src.core.gap_analyzer import ALLOWED_FRAMEWORKS, GapAnalyzer
from src.core.risk_scorer import RiskScorer
from src.data.database import get_engine, get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)
console = Console()


def _validate_framework(
    ctx: click.Context,
    param: click.Parameter,
    value: str,
) -> str:
    """Validate --framework against the allowed whitelist."""
    cleaned = value.strip().upper()
    if cleaned not in ALLOWED_FRAMEWORKS:
        msg = (
            f"Invalid framework '{cleaned}'. "
            f"Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
        )
        raise click.BadParameter(msg)
    return cleaned


@click.group("report")
def report() -> None:
    """Report generation commands."""


@report.command("generate")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    expose_value=True,
    help="Framework to generate report for (NIST_CSF, ISO_27001, CIS_V8, SOC2).",
)
@click.option(
    "--controls",
    required=True,
    type=click.Path(exists=True),
    help="Path to .txt file with one control ID per line.",
)
@click.option(
    "--format",
    "report_format",
    type=click.Choice(["html", "excel", "pdf"], case_sensitive=False),
    default="html",
    show_default=True,
    help="Report output format.",
)
@click.option(
    "--output-dir",
    default="./output",
    show_default=True,
    help="Directory to write the report file to.",
)
def generate(
    framework: str,
    controls: str,
    report_format: str,
    output_dir: str,
) -> None:
    """Generate a compliance report for a framework."""
    try:
        # Validate paths through safe_path
        validated_controls = safe_path(Path.cwd(), controls)
        validated_output = safe_path(Path.cwd(), output_dir)

        # Create output directory if missing
        validated_output.mkdir(parents=True, exist_ok=True)

        with Progress(console=console) as progress:
            task = progress.add_task("Generating report…", total=4)

            # Step 1: Read controls
            progress.update(task, description="Reading controls file…")
            raw_text = validated_controls.read_text(encoding="utf-8")
            control_ids = [
                line.strip()
                for line in raw_text.splitlines()
                if line.strip()
            ]
            progress.advance(task)

            # Step 2: Run gap analysis
            progress.update(task, description="Running gap analysis…")
            engine = get_engine()
            with get_session(engine) as session:
                repo = FrameworkRepository(session)
                analyzer = GapAnalyzer(repo)
                gap_result = analyzer.analyze(framework, control_ids)
            progress.advance(task)

            # Step 3: Run risk scoring
            progress.update(task, description="Scoring risks…")
            scorer = RiskScorer()
            risk_report = scorer.score(gap_result)
            progress.advance(task)

            # Step 4: Write report file
            progress.update(task, description="Writing report file…")

            # Resolve template_dir from project root (shared by all reporters)
            template_dir = Path(__file__).resolve().parent.parent.parent.parent / "templates"

            if report_format == "html":
                # Use HTMLReporter for HTML output
                reporter = HTMLReporter(template_dir=template_dir)
            elif report_format == "excel":
                # Use ExcelReporter for .xlsx output
                reporter = ExcelReporter(template_dir=template_dir)
            else:
                # Use PDFReporter for .pdf output
                reporter = PDFReporter(template_dir=template_dir)

            # Generate the report via the selected reporter
            report_path = reporter.generate(
                gap_result, risk_report, validated_output,
            )

            progress.advance(task)

        console.print(Panel(
            f"[green]Report generated successfully![/green]\n"
            f"File: [bold]{report_path}[/bold]\n"
            f"Format: {report_format.upper()}\n"
            f"Framework: {framework}",
            title="✅ Report Complete",
            border_style="green",
        ))

    except SecurityError as exc:
        console.print(Panel(
            f"[red]Security Error:[/red] {exc}",
            title="⛔ Access Denied",
            border_style="red",
        ))
        sys.exit(1)
    except (FrameworkNotFoundError, ValidationError) as exc:
        console.print(Panel(
            f"[yellow]Validation Error:[/yellow] {exc.message}",
            title="⚠️ Validation Failed",
            border_style="yellow",
        ))
        sys.exit(1)
    except GapAnalysisError as exc:
        console.print(Panel(
            f"[red]Analysis Error:[/red] {exc.message}",
            title="❌ Gap Analysis Failed",
            border_style="red",
        ))
        sys.exit(1)
    except RiskScoringError as exc:
        console.print(Panel(
            f"[red]Scoring Error:[/red] {exc.message}",
            title="❌ Risk Scoring Failed",
            border_style="red",
        ))
        sys.exit(1)
    except ReportGenerationError as exc:
        console.print(Panel(
            f"[red]Report Error:[/red] {exc.message}",
            title="❌ Report Generation Failed",
            border_style="red",
        ))
        sys.exit(1)

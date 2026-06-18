# -*- coding: utf-8 -*-
"""Click command group for compliance gap analysis.

Orchestrates GapAnalyzer and RiskScorer — contains zero business logic.
All file paths validated through ``safe_path()`` before access.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.exceptions import (
    FrameworkNotFoundError,
    GapAnalysisError,
    RiskScoringError,
    ValidationError,
)
from src.core.gap_analyzer import ALLOWED_FRAMEWORKS, GapAnalyzer
from src.core.risk_scorer import RiskScorer
from src.data.database import get_engine, get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)
console = Console()

_RISK_COLORS: dict[str, str] = {
    "CRITICAL": "red",
    "HIGH": "yellow",
    "MEDIUM": "blue",
    "LOW": "green",
}


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


@click.group("analyze")
def analyze() -> None:
    """Compliance gap analysis commands."""


@analyze.command("run")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    expose_value=True,
    help="Framework to validate against (NIST_CSF, ISO_27001, CIS_V8, SOC2).",
)
@click.option(
    "--controls",
    required=True,
    type=click.Path(exists=True),
    help="Path to .txt file with one control ID per line.",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format for analysis results.",
)
def run(framework: str, controls: str, output_format: str) -> None:
    """Run a gap analysis and risk scoring against a framework."""
    try:
        # Validate controls file path through safe_path
        validated_path = safe_path(Path.cwd(), controls)

        # Read and clean control IDs
        raw_text = validated_path.read_text(encoding="utf-8")
        control_ids = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]

        # Wire up real dependencies
        engine = get_engine()
        with get_session(engine) as session:
            repo = FrameworkRepository(session)
            analyzer = GapAnalyzer(repo)
            scorer = RiskScorer()

            # Run pipeline
            gap_result = analyzer.analyze(framework, control_ids)
            risk_report = scorer.score(gap_result)

        # Output results
        if output_format == "json":
            output = {
                "gap_analysis": gap_result.model_dump(mode="json"),
                "risk_report": risk_report.model_dump(mode="json"),
            }
            console.print(json.dumps(output, indent=2, default=str))
        else:
            _render_table(gap_result, risk_report)

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


def _render_table(gap_result: object, risk_report: object) -> None:
    """Render gap analysis and risk results as Rich tables."""
    # Gap analysis summary
    console.print(Panel(
        f"Framework: [bold]{gap_result.framework_name}[/bold]\n"  # type: ignore[union-attr]
        f"Total Controls: {gap_result.total_controls}\n"  # type: ignore[union-attr]
        f"Implemented: {gap_result.implemented_count}\n"  # type: ignore[union-attr]
        f"Compliance: {gap_result.compliance_percentage}%",  # type: ignore[union-attr]
        title="📊 Gap Analysis Summary",
        border_style="cyan",
    ))

    # Risk findings table
    table = Table(title="Risk Findings", show_lines=True)
    table.add_column("Control ID", style="bold")
    table.add_column("Control Name")
    table.add_column("Severity")
    table.add_column("Likelihood", justify="right")
    table.add_column("Impact", justify="right")
    table.add_column("Risk Score", justify="right")

    for finding in risk_report.findings:  # type: ignore[union-attr]
        color = _RISK_COLORS.get(finding.severity, "white")
        table.add_row(
            finding.control_id,
            finding.control_name,
            f"[{color}]{finding.severity}[/{color}]",
            str(finding.likelihood),
            str(finding.impact),
            f"[{color}]{finding.risk_score}[/{color}]",
        )

    console.print(table)

    # Overall risk level
    overall_color = _RISK_COLORS.get(
        risk_report.overall_risk_level, "white",  # type: ignore[union-attr]
    )
    console.print(Panel(
        f"Overall Risk Level: [{overall_color}]{risk_report.overall_risk_level}"  # type: ignore[union-attr]
        f"[/{overall_color}]\n"
        f"Risk Score: [{overall_color}]{risk_report.risk_score}[/{overall_color}]",  # type: ignore[union-attr]
        title="🎯 Risk Assessment",
        border_style=overall_color,
    ))

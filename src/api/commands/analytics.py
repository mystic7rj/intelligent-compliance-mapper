"""Click command group for analytics, maturity, and trend views.

Provides summary, trend, top-risks, and improvement commands with Rich
tables/panels. Command layer only orchestrates existing core services.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.analytics import AnalyticsEngine, AnalyticsSummary
from src.core.exceptions import (
    FrameworkNotFoundError,
    GapAnalysisError,
    RiskScoringError,
    ValidationError,
)
from src.core.gap_analyzer import ALLOWED_FRAMEWORKS, GapAnalyzer
from src.core.maturity_model import MaturityModel
from src.core.risk_scorer import RiskScorer
from src.core.trend_tracker import TrendTracker
from src.data.database import get_engine, get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)
console = Console()

# Keep in-memory tracker module-local for CLI session reuse.
_trend_tracker = TrendTracker()

# Map maturity level names to Rich color badges.
_MATURITY_COLORS: dict[str, str] = {
    "INITIAL": "red",
    "DEVELOPING": "yellow",
    "DEFINED": "cyan",
    "MANAGED": "blue",
    "OPTIMIZING": "green",
}

# Map risk severities to Rich colors.
_RISK_COLORS: dict[str, str] = {
    "CRITICAL": "red",
    "HIGH": "yellow",
    "MEDIUM": "blue",
    "LOW": "green",
}


# Validate framework option against whitelist.
def _validate_framework(
    ctx: click.Context,
    param: click.Parameter,
    value: str,
) -> str:
    # Normalize value for whitelist check.
    cleaned = value.strip().upper()

    # Reject frameworks outside supported whitelist.
    if cleaned not in ALLOWED_FRAMEWORKS:
        msg = f"Invalid framework '{cleaned}'. Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
        raise click.BadParameter(msg)

    # Return normalized framework name.
    return cleaned


# Build full analytics dependencies with database-backed repository.
def _build_pipeline() -> tuple[AnalyticsEngine, GapAnalyzer, RiskScorer]:
    # Initialize engine and analyzer dependencies.
    maturity_model = MaturityModel()
    analytics_engine = AnalyticsEngine(maturity_model=maturity_model)
    risk_scorer = RiskScorer()

    # Create DB-backed analyzer for framework retrieval.
    engine = get_engine()
    session = get_session(engine)
    db_session = session.__enter__()
    repository = FrameworkRepository(db_session)
    gap_analyzer = GapAnalyzer(repository=repository)

    # Return wired pipeline components.
    return analytics_engine, gap_analyzer, risk_scorer


# Safely close session wrapper created by _build_pipeline.
def _close_pipeline_session(gap_analyzer: GapAnalyzer) -> None:
    # Read private repository to close underlying session context.
    repository = gap_analyzer._repository  # pyright: ignore[reportPrivateUsage]

    # Exit context when repository is DB-backed.
    if isinstance(repository, FrameworkRepository):
        # Access session object and close it gracefully.
        repository._session.close()  # pyright: ignore[reportPrivateUsage]


@click.group("analytics")
def analytics() -> None:
    """Analytics, maturity, and trend commands."""


# Run full pipeline and show analytics summary panel.
@analytics.command("summary")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    help="Framework to analyze (NIST_CSF, ISO_27001, CIS_V8, SOC2).",
)
@click.option(
    "--controls",
    required=True,
    type=click.Path(exists=True),
    help="Path to .txt file with one implemented control ID per line.",
)
def summary(framework: str, controls: str) -> None:
    """Generate and display analytics summary for one framework."""
    try:
        # Validate controls path before reading.
        validated_path = safe_path(Path.cwd(), controls)

        # Load implemented controls from file.
        control_ids = [
            line.strip()
            for line in validated_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        # Build and run analytics pipeline.
        analytics_engine, gap_analyzer, risk_scorer = _build_pipeline()
        gap_result = gap_analyzer.analyze(framework, control_ids)
        risk_report = risk_scorer.score(gap_result)
        summary_result = analytics_engine.summarize(gap_result, risk_report)

        # Record summary into trend tracker.
        _trend_tracker.record(summary_result)

        # Resolve maturity badge color.
        maturity_color = _MATURITY_COLORS.get(summary_result.maturity_level, "white")

        # Render summary as rich panel.
        console.print(
            Panel(
                "\n".join(
                    [
                        f"Framework: [bold]{summary_result.framework_name}[/bold]",
                        f"Compliance: [bold]{summary_result.compliance_percentage:.2f}%[/bold]",
                        f"Risk Score: [bold]{summary_result.risk_score:.2f}[/bold]",
                        f"Maturity: [{maturity_color}]● {summary_result.maturity_level}[/{maturity_color}]",
                        f"Total Controls: {summary_result.total_controls}",
                        f"Critical Gaps: {summary_result.critical_gaps}",
                        f"High Gaps: {summary_result.high_gaps}",
                        f"Medium Gaps: {summary_result.medium_gaps}",
                        f"Low Gaps: {summary_result.low_gaps}",
                    ]
                ),
                title="📈 Analytics Summary",
                border_style="cyan",
            )
        )

        # Close pipeline resources after successful execution.
        _close_pipeline_session(gap_analyzer)
    except Exception as exc:
        # Show all errors as rich error panels.
        _render_error_panel(exc, "❌ Analytics Summary Failed")
        sys.exit(1)


# Display trend history table for one framework.
@analytics.command("trend")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    help="Framework to query trend history for.",
)
def trend(framework: str) -> None:
    """Display historical trend entries for one framework."""
    try:
        # Load ordered trend entries from tracker.
        entries = _trend_tracker.get_trend(framework)

        # Build Rich table for trend entries.
        table = Table(title=f"Trend History — {framework}", show_lines=True)
        table.add_column("Date", style="cyan")
        table.add_column("Compliance %", justify="right")
        table.add_column("Risk Score", justify="right")
        table.add_column("Maturity Level")

        # Add each trend entry row in ascending date order.
        for entry in entries:
            maturity_color = _MATURITY_COLORS.get(entry.maturity_level, "white")
            table.add_row(
                entry.recorded_at.isoformat(),
                f"{entry.compliance_percentage:.2f}",
                f"{entry.risk_score:.2f}",
                f"[{maturity_color}]{entry.maturity_level}[/{maturity_color}]",
            )

        # Show fallback panel when no entries exist.
        if not entries:
            console.print(
                Panel(
                    f"No trend data recorded for framework [bold]{framework}[/bold] yet.",
                    title="ℹ️ No Trend Data",
                    border_style="yellow",
                )
            )
            return

        # Render trend table to terminal.
        console.print(table)
    except Exception as exc:
        # Show all errors as rich error panels.
        _render_error_panel(exc, "❌ Trend Query Failed")
        sys.exit(1)


# Display top N risk findings as prioritized table.
@analytics.command("top-risks")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    help="Framework to analyze (NIST_CSF, ISO_27001, CIS_V8, SOC2).",
)
@click.option(
    "--controls",
    required=True,
    type=click.Path(exists=True),
    help="Path to .txt file with one implemented control ID per line.",
)
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=int,
    help="Maximum number of top risks to display.",
)
def top_risks(framework: str, controls: str, limit: int) -> None:
    """Display top N prioritized risk findings for one framework."""
    try:
        # Validate controls path before reading.
        validated_path = safe_path(Path.cwd(), controls)

        # Read implemented controls from file.
        control_ids = [
            line.strip()
            for line in validated_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        # Build and run scoring pipeline.
        analytics_engine, gap_analyzer, risk_scorer = _build_pipeline()
        gap_result = gap_analyzer.analyze(framework, control_ids)
        risk_report = risk_scorer.score(gap_result)
        top_findings = analytics_engine.top_priority_controls(risk_report, limit=limit)

        # Create rich table for prioritized findings.
        table = Table(title=f"Top {max(1, limit)} Risk Findings — {framework}", show_lines=True)
        table.add_column("Control ID", style="bold")
        table.add_column("Control Name")
        table.add_column("Severity")
        table.add_column("Risk Score", justify="right")
        table.add_column("Likelihood", justify="right")
        table.add_column("Impact", justify="right")

        # Populate rows with colorized severity and score.
        for finding in top_findings:
            color = _RISK_COLORS.get(finding.severity, "white")
            table.add_row(
                finding.control_id,
                finding.control_name,
                f"[{color}]{finding.severity}[/{color}]",
                f"[{color}]{finding.risk_score:.2f}[/{color}]",
                f"{finding.likelihood:.2f}",
                f"{finding.impact:.2f}",
            )

        # Render top risks table.
        console.print(table)

        # Close pipeline resources after successful execution.
        _close_pipeline_session(gap_analyzer)
    except Exception as exc:
        # Show all errors as rich error panels.
        _render_error_panel(exc, "❌ Top Risks Failed")
        sys.exit(1)


# Display improvement delta for one framework from trend history.
@analytics.command("improvement")
@click.option(
    "--framework",
    required=True,
    type=str,
    callback=_validate_framework,
    help="Framework to compute improvement for.",
)
def improvement(framework: str) -> None:
    """Display compliance and risk improvement deltas from trend data."""
    try:
        # Compute improvement payload from trend tracker.
        improvement_data = _trend_tracker.calculate_improvement(framework)

        # Render improvement panel from computed data.
        console.print(
            Panel(
                "\n".join(
                    [
                        f"Framework: [bold]{framework}[/bold]",
                        f"First Recorded: {improvement_data['first_recorded']}",
                        f"Latest Recorded: {improvement_data['latest_recorded']}",
                        f"Compliance Change: [green]{improvement_data['compliance_change']}[/green]",
                        f"Risk Change: [yellow]{improvement_data['risk_change']}[/yellow]",
                        f"Total Snapshots: {improvement_data['total_snapshots']}",
                    ]
                ),
                title="📊 Improvement Delta",
                border_style="magenta",
            )
        )
    except Exception as exc:
        # Show all errors as rich error panels.
        _render_error_panel(exc, "❌ Improvement Calculation Failed")
        sys.exit(1)


# Render standardized rich error panel for command failures.
def _render_error_panel(exc: Exception, title: str) -> None:
    # Render domain-specific exception message.
    if isinstance(
        exc,
        (
            SecurityError,
            FrameworkNotFoundError,
            GapAnalysisError,
            RiskScoringError,
            ValidationError,
        ),
    ):
        message = getattr(exc, "message", str(exc))
        console.print(Panel(f"[red]{message}[/red]", title=title, border_style="red"))
        return

    # Render generic exception details for unknown failures.
    console.print(Panel(f"[red]{str(exc)}[/red]", title=title, border_style="red"))

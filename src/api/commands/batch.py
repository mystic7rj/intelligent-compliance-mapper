"""Click command group for batch report processing.

Provides ``run``, ``run-all``, ``status``, and ``list-jobs`` sub-commands.
All file paths are validated through ``safe_path()`` and all exceptions
are caught and displayed as Rich error panels.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.batch_processor import BatchProcessor
from src.core.gap_analyzer import ALLOWED_FRAMEWORKS, GapAnalyzer
from src.core.job_queue import JobQueue, ReportJob
from src.core.risk_scorer import RiskScorer
from src.data.database import get_engine, get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.reports.excel_reporter import ExcelReporter
from src.reports.html_reporter import HTMLReporter
from src.reports.pdf_reporter import PDFReporter
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)
console = Console()

# Module-level shared queue so status/list-jobs can read back results.
_job_queue = JobQueue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Validate --framework against the allowed whitelist.
def _validate_framework(
    ctx: click.Context,
    param: click.Parameter,
    value: str,
) -> str:
    """Validate framework name against the whitelist."""
    cleaned = value.strip().upper()
    if cleaned not in ALLOWED_FRAMEWORKS:
        msg = (
            f"Invalid framework '{cleaned}'. "
            f"Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
        )
        raise click.BadParameter(msg)
    return cleaned


# Build a BatchProcessor wired to real dependencies.
def _build_processor(queue: JobQueue) -> BatchProcessor:
    """Create a fully-wired ``BatchProcessor``."""
    engine = get_engine()
    session = get_session(engine).__enter__()  # noqa: PLC2801
    repo = FrameworkRepository(session)
    analyzer = GapAnalyzer(repo)
    scorer = RiskScorer()

    # Resolve the shared template directory
    template_dir = (
        Path(__file__).resolve().parent.parent.parent.parent / "templates"
    )

    # Map format names to concrete reporter instances
    reporters = {
        "html": HTMLReporter(template_dir=template_dir),
        "excel": ExcelReporter(template_dir=template_dir),
        "pdf": PDFReporter(template_dir=template_dir),
    }
    return BatchProcessor(queue, analyzer, scorer, reporters)


# ---------------------------------------------------------------------------
# Command group
# ---------------------------------------------------------------------------


# Click group for batch commands.
@click.group("batch")
def batch() -> None:
    """Batch report processing commands."""


# ---------------------------------------------------------------------------
# batch run — single report job
# ---------------------------------------------------------------------------


# Run a single report job for the given framework and controls file.
@batch.command("run")
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
def run(
    framework: str,
    controls: str,
    report_format: str,
    output_dir: str,
) -> None:
    """Run a single report job."""
    try:
        # Validate paths through safe_path
        validated_controls = safe_path(Path.cwd(), controls)
        validated_output = safe_path(Path.cwd(), output_dir)

        # Read control IDs from the controls file
        raw_text = validated_controls.read_text(encoding="utf-8")
        control_ids = [
            line.strip() for line in raw_text.splitlines() if line.strip()
        ]

        # Create a job with validated parameters
        job = ReportJob(
            framework_name=framework,
            controls_list=control_ids,
            output_format=report_format,
            output_dir=validated_output,
        )

        # Build processor and process the job as a single-item batch
        processor = _build_processor(_job_queue)
        results = processor.process_batch([job])

        # Display result in a Rich panel
        result = results[0]
        if result["status"] == "COMPLETED":
            console.print(Panel(
                f"[green]Job completed![/green]\n"
                f"Job ID: [bold]{result['job_id']}[/bold]\n"
                f"Output: {result['output_path']}",
                title="✅ Batch Run Complete",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[red]Job failed:[/red] {result.get('error', 'Unknown')}",
                title="❌ Batch Run Failed",
                border_style="red",
            ))
            sys.exit(1)

    except SecurityError as exc:
        # Display security violations as error panel
        console.print(Panel(
            f"[red]Security Error:[/red] {exc}",
            title="⛔ Access Denied",
            border_style="red",
        ))
        sys.exit(1)
    except Exception as exc:
        # Catch-all for unexpected errors
        console.print(Panel(
            f"[red]Unexpected Error:[/red] {exc}",
            title="❌ Error",
            border_style="red",
        ))
        sys.exit(1)


# ---------------------------------------------------------------------------
# batch run-all — batch from JSON file
# ---------------------------------------------------------------------------


# Read a JSON jobs file and process all jobs as a batch.
@batch.command("run-all")
@click.option(
    "--jobs-file",
    required=True,
    type=click.Path(exists=True),
    help="Path to JSON file containing list of job definitions.",
)
def run_all(jobs_file: str) -> None:
    """Process a batch of report jobs from a JSON file."""
    try:
        # Validate the jobs-file path
        validated_path = safe_path(Path.cwd(), jobs_file)

        # Parse the JSON jobs file
        raw_json = validated_path.read_text(encoding="utf-8")
        job_defs = json.loads(raw_json)

        # Validate that the file contains a list
        if not isinstance(job_defs, list):
            console.print(Panel(
                "[red]Jobs file must contain a JSON array.[/red]",
                title="❌ Invalid Format",
                border_style="red",
            ))
            sys.exit(1)

        # Build ReportJob instances from each definition
        jobs: list[ReportJob] = []
        for entry in job_defs:
            # Read controls from the referenced file
            controls_path = safe_path(Path.cwd(), entry["controls_file"])
            raw_text = controls_path.read_text(encoding="utf-8")
            control_ids = [
                line.strip() for line in raw_text.splitlines() if line.strip()
            ]

            # Determine output directory (default to ./output)
            out_dir = safe_path(
                Path.cwd(), entry.get("output_dir", "./output"),
            )

            # Create job with parsed parameters
            jobs.append(ReportJob(
                framework_name=entry["framework"].strip().upper(),
                controls_list=control_ids,
                output_format=entry.get("format", "html"),
                output_dir=out_dir,
            ))

        # Build processor and run the batch
        processor = _build_processor(_job_queue)
        results = processor.process_batch(jobs)

        # Display summary of all results
        completed = sum(1 for r in results if r["status"] == "COMPLETED")
        failed = sum(1 for r in results if r["status"] == "FAILED")

        console.print(Panel(
            f"[bold]Total:[/bold] {len(results)}\n"
            f"[green]Completed:[/green] {completed}\n"
            f"[red]Failed:[/red] {failed}",
            title="📋 Batch Results",
            border_style="blue",
        ))

    except SecurityError as exc:
        # Display security violations as error panel
        console.print(Panel(
            f"[red]Security Error:[/red] {exc}",
            title="⛔ Access Denied",
            border_style="red",
        ))
        sys.exit(1)
    except (json.JSONDecodeError, KeyError) as exc:
        # Handle malformed JSON or missing keys
        console.print(Panel(
            f"[red]File Error:[/red] {exc}",
            title="❌ Invalid Jobs File",
            border_style="red",
        ))
        sys.exit(1)
    except Exception as exc:
        # Catch-all for unexpected errors
        console.print(Panel(
            f"[red]Unexpected Error:[/red] {exc}",
            title="❌ Error",
            border_style="red",
        ))
        sys.exit(1)


# ---------------------------------------------------------------------------
# batch status — show single job status
# ---------------------------------------------------------------------------


# Display the status of a specific job by its ID.
@batch.command("status")
@click.option(
    "--job-id",
    required=True,
    type=str,
    help="UUID of the job to query.",
)
def status(job_id: str) -> None:
    """Show the status of a specific job."""
    try:
        # Look up the job status from the shared queue
        job_status = _job_queue.get_status(job_id)

        if job_status is None:
            # Unknown job ID
            console.print(Panel(
                f"[yellow]No job found with ID:[/yellow] {job_id}",
                title="⚠️ Not Found",
                border_style="yellow",
            ))
            sys.exit(1)

        # Display status in a Rich panel
        console.print(Panel(
            f"Job ID: [bold]{job_id}[/bold]\n"
            f"Status: {job_status.value}",
            title="📌 Job Status",
            border_style="cyan",
        ))

    except Exception as exc:
        # Catch-all for unexpected errors
        console.print(Panel(
            f"[red]Error:[/red] {exc}",
            title="❌ Error",
            border_style="red",
        ))
        sys.exit(1)


# ---------------------------------------------------------------------------
# batch list-jobs — show all jobs in queue
# ---------------------------------------------------------------------------


# Display all jobs in the queue as a Rich table.
@batch.command("list-jobs")
def list_jobs() -> None:
    """List all jobs in the queue."""
    try:
        # Retrieve every job from the shared queue
        all_jobs = _job_queue.get_all_jobs()

        if not all_jobs:
            console.print(Panel(
                "[yellow]No jobs in the queue.[/yellow]",
                title="📋 Job Queue",
                border_style="yellow",
            ))
            return

        # Build a Rich table with job details
        table = Table(title="Job Queue", show_lines=True)
        table.add_column("Job ID", style="cyan", no_wrap=True)
        table.add_column("Framework", style="magenta")
        table.add_column("Format", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Created At", style="dim")

        for job in all_jobs:
            # Add each job as a row
            table.add_row(
                job.job_id,
                job.framework_name,
                job.output_format,
                job.status.value,
                job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )

        console.print(table)

    except Exception as exc:
        # Catch-all for unexpected errors
        console.print(Panel(
            f"[red]Error:[/red] {exc}",
            title="❌ Error",
            border_style="red",
        ))
        sys.exit(1)

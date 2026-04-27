"""Report scheduler for periodic compliance report generation.

Provides a synchronous, testable scheduler — no real background
threads.  ``ReportScheduler`` creates and processes one-off jobs
via the injected ``BatchProcessor``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.core.batch_processor import BatchProcessor
from src.core.job_queue import ReportJob
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------


class SchedulerConfig(BaseModel):
    """Configuration for the report scheduler."""

    interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between scheduled runs (1–168).",
    )
    output_format: Literal["html", "excel", "pdf"] = Field(
        default="html",
        description="Default report output format.",
    )
    output_dir: Path = Field(
        ..., description="Default output directory for scheduled reports."
    )
    enabled: bool = Field(
        default=True,
        description="Whether the scheduler is active.",
    )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class ReportScheduler:
    """Synchronous report scheduler backed by ``BatchProcessor``.

    No real background thread — methods are synchronous and fully
    testable.  Receives all dependencies via constructor.

    Args:
        batch_processor: The ``BatchProcessor`` that will execute jobs.
        config: Scheduler configuration (interval, format, etc.).
    """

    def __init__(
        self,
        batch_processor: BatchProcessor,
        config: SchedulerConfig,
    ) -> None:
        # Store injected batch processor
        self._processor = batch_processor
        # Store scheduler configuration
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Create a single job, enqueue it, and process it immediately.
    def schedule_once(
        self,
        framework_name: str,
        controls: list[str],
    ) -> str:
        """Create one report job, process it immediately, return its ID.

        Args:
            framework_name: Target compliance framework.
            controls: List of implemented control IDs.

        Returns:
            The ``job_id`` of the created job.
        """
        # Build a new ReportJob with scheduler defaults
        job = ReportJob(
            job_id=str(uuid.uuid4()),
            framework_name=framework_name,
            controls_list=controls,
            output_format=self._config.output_format,
            output_dir=self._config.output_dir,
        )

        # Process as a single-item batch
        self._processor.process_batch([job])

        logger.info(
            "Scheduled job processed",
            extra={"job_id": job.job_id, "framework": framework_name},
        )
        return job.job_id

    # Calculate when the next scheduled run would occur.
    def get_next_run_time(self) -> datetime:
        """Return ``now + interval_hours`` as the next hypothetical run."""
        return datetime.now(tz=UTC) + timedelta(hours=self._config.interval_hours)

    # Return a summary dict of the current scheduler configuration.
    def get_schedule_summary(self) -> dict[str, object]:
        """Return a dictionary summarising the scheduler state."""
        return {
            "interval_hours": self._config.interval_hours,
            "output_format": self._config.output_format,
            "output_dir": str(self._config.output_dir),
            "enabled": self._config.enabled,
            "next_run": self.get_next_run_time().isoformat(),
        }

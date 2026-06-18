# -*- coding: utf-8 -*-
"""Batch processor for report generation.

Receives all dependencies via constructor injection — never imports
reporters directly.  Processes jobs from the ``JobQueue``, running the
full gap-analyze → risk-score → report-generate pipeline for each.
On any single job failure the batch continues with remaining jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.job_queue import JobQueue, JobStatus, ReportJob
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)


class BatchProcessor:
    """Processes queued report jobs through the full compliance pipeline.
    
    PATTERN: Orchestration Service — coordinates gap analysis, risk scoring, and reporting
    PATTERN: Dependency Injection — all collaborators injected for testability
    
    All collaborators are injected — no internal imports of reporters
    or analysers.  This makes the class fully testable with mocks.

    Args:
        job_queue: Shared ``JobQueue`` instance.
        gap_analyzer: Object with an ``analyze(framework, controls)`` method.
        risk_scorer: Object with a ``score(gap_result)`` method.
        reporters: Mapping of format name → reporter instance, e.g.
            ``{"html": HTMLReporter(...), "excel": ExcelReporter(...)}``.
    """

    # PATTERN: Dependency Injection — store all collaborators for pipeline execution
    def __init__(
        self,
        job_queue: JobQueue,
        gap_analyzer: Any,
        risk_scorer: Any,
        reporters: dict[str, Any],
    ) -> None:
        """Initialize batch processor with all pipeline dependencies.
        
        Args:
            job_queue: Shared queue for managing report jobs
            gap_analyzer: Gap analysis engine (duck-typed protocol)
            risk_scorer: Risk scoring engine (duck-typed protocol)
            reporters: Format-to-reporter mapping for report generation
        """
        # Store injected job queue for managing work items
        self._queue = job_queue
        # Store gap analyzer for compliance analysis step
        self._analyzer = gap_analyzer
        # Store risk scorer for risk assessment step
        self._scorer = risk_scorer
        # Store reporters dict for flexible output format selection
        self._reporters = reporters

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Run the full pipeline for a single job and return the output path.
    def process_job(self, job: ReportJob) -> Path:
        """Execute gap analysis → risk scoring → report generation.

        Args:
            job: The ``ReportJob`` to process.

        Returns:
            ``Path`` to the generated report file.

        Raises:
            SecurityError: If *output_dir* fails path validation.
            KeyError: If *output_format* has no matching reporter.
        """
        # Validate output directory against path traversal
        validated_dir = safe_path(Path.cwd(), job.output_dir)

        # Ensure the output directory exists
        validated_dir.mkdir(parents=True, exist_ok=True)

        # Step 1 — run gap analysis
        gap_result = self._analyzer.analyze(
            job.framework_name, job.controls_list,
        )

        # Step 2 — run risk scoring
        risk_report = self._scorer.score(gap_result)

        # Step 3 — select the appropriate reporter
        reporter = self._reporters.get(job.output_format)
        if reporter is None:
            msg = f"No reporter registered for format '{job.output_format}'"
            raise KeyError(msg)

        # Step 4 — generate the report file
        output_path: Path = reporter.generate(
            gap_result, risk_report, validated_dir,
        )

        logger.info(
            "Job processed successfully",
            extra={"job_id": job.job_id, "output": str(output_path)},
        )
        return output_path

    # Dequeue and process all pending jobs, returning a summary list.
    def process_all(self) -> list[dict[str, Any]]:
        """Dequeue every pending job and process it.

        On failure the job is marked ``FAILED`` with an error message
        but processing continues with remaining jobs.

        Returns:
            List of result dicts with ``job_id``, ``status``, and
            ``output_path`` or ``error``.
        """
        results: list[dict[str, Any]] = []

        # Keep dequeuing until the queue is empty
        while True:
            job = self._queue.dequeue()
            if job is None:
                break

            # Mark the job as running
            self._queue.update_status(job.job_id, JobStatus.RUNNING)

            try:
                # Attempt full pipeline processing
                output_path = self.process_job(job)

                # Mark as completed on success
                self._queue.update_status(job.job_id, JobStatus.COMPLETED)
                results.append({
                    "job_id": job.job_id,
                    "status": JobStatus.COMPLETED.value,
                    "output_path": str(output_path),
                })

            except Exception as exc:
                # Mark as failed but do NOT stop the batch
                error_msg = str(exc)
                self._queue.update_status(
                    job.job_id, JobStatus.FAILED, error=error_msg,
                )
                results.append({
                    "job_id": job.job_id,
                    "status": JobStatus.FAILED.value,
                    "error": error_msg,
                })
                logger.error(
                    "Job failed",
                    extra={"job_id": job.job_id, "error": error_msg},
                )

        return results

    # Enqueue a batch of jobs then process them all at once.
    def process_batch(self, jobs: list[ReportJob]) -> list[dict[str, Any]]:
        """Enqueue *jobs* and then process the entire queue.

        Args:
            jobs: List of ``ReportJob`` instances to enqueue.

        Returns:
            Combined results list from ``process_all()``.
        """
        # Enqueue every job first
        for job in jobs:
            self._queue.enqueue(job)

        # Process the full queue
        return self.process_all()

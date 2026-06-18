# -*- coding: utf-8 -*-
"""In-memory job queue for batch report processing.

Provides a thread-safe FIFO queue backed by ``collections.deque`` with
O(1) job-ID lookup via an internal dictionary.  All mutations are
guarded by ``threading.Lock``.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(Enum):
    """Possible lifecycle states of a report job.
    
    State transitions:
    PENDING → RUNNING → COMPLETED
    PENDING → RUNNING → FAILED
    """

    # Job is queued but not yet processing
    PENDING = "PENDING"
    # Job is currently being processed
    RUNNING = "RUNNING"
    # Job completed successfully
    COMPLETED = "COMPLETED"
    # Job failed with an error
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class ReportJob(BaseModel):
    """Data model representing a single queued report job."""

    job_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique job identifier (UUID4).",
    )
    framework_name: str = Field(..., description="Target compliance framework.")
    controls_list: list[str] = Field(
        ..., description="List of implemented control IDs."
    )
    output_format: Literal["html", "excel", "pdf"] = Field(
        ..., description="Desired report format."
    )
    output_dir: Path = Field(..., description="Directory for the output report.")
    status: JobStatus = Field(
        default=JobStatus.PENDING, description="Current job status."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Timestamp when the job was created.",
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the job finished."
    )
    error_message: Optional[str] = Field(
        default=None, description="Error details if the job failed."
    )


# ---------------------------------------------------------------------------
# Thread-safe job queue
# ---------------------------------------------------------------------------


class JobQueue:
    """Thread-safe in-memory FIFO queue for report jobs.

    Uses ``collections.deque`` for ordering and a ``dict`` for O(1)
    lookups by ``job_id``.  Every public method acquires ``_lock``
    before mutating shared state.
    """

    def __init__(self) -> None:
        # Internal FIFO queue
        self._queue: deque[ReportJob] = deque()
        # Fast lookup by job_id
        self._jobs: dict[str, ReportJob] = {}
        # Lock for thread-safe access
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Add a job to the back of the queue and return its job_id.
    def enqueue(self, job: ReportJob) -> str:
        """Append *job* to the queue and return its ``job_id``."""
        with self._lock:
            self._queue.append(job)
            self._jobs[job.job_id] = job
            logger.info(
                "Job enqueued",
                extra={"job_id": job.job_id, "framework": job.framework_name},
            )
        return job.job_id

    # Remove and return the next pending job, or None if the queue is empty.
    def dequeue(self) -> Optional[ReportJob]:
        """Pop the oldest job from the front of the queue."""
        with self._lock:
            if not self._queue:
                return None
            job = self._queue.popleft()
            logger.info("Job dequeued", extra={"job_id": job.job_id})
            return job

    # Look up the status of a job by its ID (returns None for unknown IDs).
    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """Return the current status of the given job, or ``None``."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.status if job else None

    # Transition a job to a new status, optionally recording an error.
    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
    ) -> None:
        """Update the status (and optional error) of *job_id*."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                logger.warning(
                    "Attempted to update unknown job",
                    extra={"job_id": job_id},
                )
                return
            # Mutate status fields directly
            job.status = status
            if error is not None:
                job.error_message = error
            # Mark completion timestamp on terminal states
            if status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                job.completed_at = datetime.now(tz=UTC)
            logger.info(
                "Job status updated",
                extra={"job_id": job_id, "new_status": status.value},
            )

    # Return a snapshot of every job in the registry.
    def get_all_jobs(self) -> list[ReportJob]:
        """Return a list of all jobs (queued and processed)."""
        with self._lock:
            return list(self._jobs.values())

    # Remove every job from both the queue and the registry.
    def clear(self) -> None:
        """Empty the queue and the job registry."""
        with self._lock:
            self._queue.clear()
            self._jobs.clear()
            logger.info("Job queue cleared")

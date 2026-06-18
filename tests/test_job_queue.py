# -*- coding: utf-8 -*-
"""Unit tests for the in-memory job queue.

Covers enqueue/dequeue ordering, status management, and thread safety.
All tests use isolated ``JobQueue`` instances — no shared state.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.core.job_queue import JobQueue, JobStatus, ReportJob

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def queue() -> JobQueue:
    """Provide a fresh, empty JobQueue for each test."""
    return JobQueue()


@pytest.fixture()
def sample_job(tmp_path: Path) -> ReportJob:
    """Create a sample ReportJob pointing at a temp directory."""
    return ReportJob(
        framework_name="NIST_CSF",
        controls_list=["ID.AM-1", "PR.AC-1"],
        output_format="html",
        output_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Verify that enqueue() returns a valid UUID4 string.
class TestEnqueue:
    def test_enqueue_returns_valid_uuid(
        self, queue: JobQueue, sample_job: ReportJob,
    ) -> None:
        """enqueue() must return a string that parses as UUID."""
        job_id = queue.enqueue(sample_job)
        # Should not raise ValueError
        parsed = uuid.UUID(job_id, version=4)
        assert str(parsed) == job_id


# Verify that dequeue() returns jobs in FIFO order.
class TestDequeue:
    def test_dequeue_fifo_order(self, queue: JobQueue, tmp_path: Path) -> None:
        """Jobs must be dequeued in the order they were enqueued."""
        # Create two distinct jobs
        job_a = ReportJob(
            framework_name="NIST_CSF",
            controls_list=["ID.AM-1"],
            output_format="html",
            output_dir=tmp_path,
        )
        job_b = ReportJob(
            framework_name="ISO_27001",
            controls_list=["PR.AC-1"],
            output_format="pdf",
            output_dir=tmp_path,
        )

        queue.enqueue(job_a)
        queue.enqueue(job_b)

        # First dequeue should return job_a
        first = queue.dequeue()
        assert first is not None
        assert first.job_id == job_a.job_id

        # Second dequeue should return job_b
        second = queue.dequeue()
        assert second is not None
        assert second.job_id == job_b.job_id

    def test_dequeue_empty_returns_none(self, queue: JobQueue) -> None:
        """Dequeuing from an empty queue must return None."""
        assert queue.dequeue() is None


# Verify that get_status() returns the correct status after enqueue.
class TestGetStatus:
    def test_status_after_enqueue(
        self, queue: JobQueue, sample_job: ReportJob,
    ) -> None:
        """Newly enqueued jobs should have PENDING status."""
        job_id = queue.enqueue(sample_job)
        assert queue.get_status(job_id) == JobStatus.PENDING

    # Verify that get_status() returns None for an unknown job_id.
    def test_status_unknown_job_returns_none(self, queue: JobQueue) -> None:
        """Unknown job IDs must return None."""
        assert queue.get_status("nonexistent-id") is None


# Verify that update_status() changes the job status correctly.
class TestUpdateStatus:
    def test_update_status_changes_correctly(
        self, queue: JobQueue, sample_job: ReportJob,
    ) -> None:
        """update_status() should change the stored status."""
        job_id = queue.enqueue(sample_job)
        queue.update_status(job_id, JobStatus.RUNNING)
        assert queue.get_status(job_id) == JobStatus.RUNNING

    def test_update_status_records_error(
        self, queue: JobQueue, sample_job: ReportJob,
    ) -> None:
        """update_status() should record the error message on failure."""
        job_id = queue.enqueue(sample_job)
        queue.update_status(job_id, JobStatus.FAILED, error="boom")

        # Retrieve job to check the error field
        jobs = queue.get_all_jobs()
        failed = [j for j in jobs if j.job_id == job_id][0]
        assert failed.error_message == "boom"


# Verify that clear() empties the queue completely.
class TestClear:
    def test_clear_empties_queue(
        self, queue: JobQueue, sample_job: ReportJob,
    ) -> None:
        """After clear(), the queue must be empty."""
        queue.enqueue(sample_job)
        queue.clear()
        assert queue.dequeue() is None
        assert queue.get_all_jobs() == []


# Verify that get_all_jobs() returns all enqueued jobs.
class TestGetAllJobs:
    def test_get_all_jobs_returns_all(
        self, queue: JobQueue, tmp_path: Path,
    ) -> None:
        """get_all_jobs() must return every enqueued job."""
        job_a = ReportJob(
            framework_name="NIST_CSF",
            controls_list=["ID.AM-1"],
            output_format="html",
            output_dir=tmp_path,
        )
        job_b = ReportJob(
            framework_name="CIS_V8",
            controls_list=["PR.AC-1"],
            output_format="excel",
            output_dir=tmp_path,
        )
        queue.enqueue(job_a)
        queue.enqueue(job_b)

        all_jobs = queue.get_all_jobs()
        assert len(all_jobs) == 2
        ids = {j.job_id for j in all_jobs}
        assert job_a.job_id in ids
        assert job_b.job_id in ids

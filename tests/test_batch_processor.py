# -*- coding: utf-8 -*-
"""Unit tests for the batch processor.

All reporters, GapAnalyzer, and RiskScorer are fully mocked — zero
real processing.  ``safe_path`` is patched so that pytest's ``tmp_path``
(outside project CWD) passes validation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.batch_processor import BatchProcessor
from src.core.job_queue import JobQueue, JobStatus, ReportJob
from src.utils.security import SecurityError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def queue() -> JobQueue:
    """Provide a fresh, empty JobQueue."""
    return JobQueue()


@pytest.fixture()
def mock_analyzer() -> MagicMock:
    """Create a mock GapAnalyzer."""
    analyzer = MagicMock()
    # analyze() returns a mock gap result
    analyzer.analyze.return_value = MagicMock()
    return analyzer


@pytest.fixture()
def mock_scorer() -> MagicMock:
    """Create a mock RiskScorer."""
    scorer = MagicMock()
    # score() returns a mock risk report
    scorer.score.return_value = MagicMock()
    return scorer


@pytest.fixture()
def mock_reporters(tmp_path: Path) -> dict[str, MagicMock]:
    """Create mock reporters for all three formats."""
    reporters: dict[str, MagicMock] = {}
    for fmt in ("html", "excel", "pdf"):
        reporter = MagicMock()
        # generate() returns a fake file path
        reporter.generate.return_value = tmp_path / f"report.{fmt}"
        reporters[fmt] = reporter
    return reporters


@pytest.fixture()
def processor(
    queue: JobQueue,
    mock_analyzer: MagicMock,
    mock_scorer: MagicMock,
    mock_reporters: dict[str, MagicMock],
) -> BatchProcessor:
    """Build a BatchProcessor wired to mock dependencies."""
    return BatchProcessor(queue, mock_analyzer, mock_scorer, mock_reporters)


@pytest.fixture()
def sample_job(tmp_path: Path) -> ReportJob:
    """Create a sample ReportJob pointing at a real temp directory."""
    return ReportJob(
        framework_name="NIST_CSF",
        controls_list=["ID.AM-1", "PR.AC-1"],
        output_format="html",
        output_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Verify that process_job() returns a valid Path on success.
class TestProcessJob:
    @patch("src.core.batch_processor.safe_path")
    def test_process_job_returns_path(
        self,
        mock_safe_path: MagicMock,
        processor: BatchProcessor,
        sample_job: ReportJob,
    ) -> None:
        """process_job() must return a Path object."""
        # Allow safe_path to pass through by returning the job's output_dir
        mock_safe_path.return_value = sample_job.output_dir
        result = processor.process_job(sample_job)
        assert isinstance(result, Path)

    # Verify that a successfully processed job is marked COMPLETED.
    @patch("src.core.batch_processor.safe_path")
    def test_job_status_completed_on_success(
        self,
        mock_safe_path: MagicMock,
        queue: JobQueue,
        processor: BatchProcessor,
        sample_job: ReportJob,
    ) -> None:
        """After process_batch, successful job must be COMPLETED."""
        mock_safe_path.return_value = sample_job.output_dir
        results = processor.process_batch([sample_job])
        assert results[0]["status"] == "COMPLETED"
        assert queue.get_status(sample_job.job_id) == JobStatus.COMPLETED

    # Verify that a job is marked FAILED when the reporter raises.
    @patch("src.core.batch_processor.safe_path")
    def test_job_status_failed_on_exception(
        self,
        mock_safe_path: MagicMock,
        queue: JobQueue,
        mock_analyzer: MagicMock,
        mock_scorer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Reporter exception must mark the job FAILED."""
        mock_safe_path.return_value = tmp_path

        # Create a reporter that explodes
        bad_reporter = MagicMock()
        bad_reporter.generate.side_effect = RuntimeError("render error")

        processor = BatchProcessor(
            queue, mock_analyzer, mock_scorer, {"html": bad_reporter},
        )

        job = ReportJob(
            framework_name="NIST_CSF",
            controls_list=["ID.AM-1"],
            output_format="html",
            output_dir=tmp_path,
        )
        results = processor.process_batch([job])
        assert results[0]["status"] == "FAILED"
        assert "render error" in results[0]["error"]


# Verify that process_all() continues after a single-job failure.
class TestProcessAll:
    @patch("src.core.batch_processor.safe_path")
    def test_continues_after_failure(
        self,
        mock_safe_path: MagicMock,
        queue: JobQueue,
        mock_analyzer: MagicMock,
        mock_scorer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Batch must not stop when one job fails."""
        mock_safe_path.return_value = tmp_path

        # First reporter succeeds, second fails
        good_reporter = MagicMock()
        good_reporter.generate.return_value = tmp_path / "report.html"

        bad_reporter = MagicMock()
        bad_reporter.generate.side_effect = RuntimeError("crash")

        reporters = {"html": good_reporter, "pdf": bad_reporter}
        processor = BatchProcessor(
            queue, mock_analyzer, mock_scorer, reporters,
        )

        job_ok = ReportJob(
            framework_name="NIST_CSF",
            controls_list=["ID.AM-1"],
            output_format="html",
            output_dir=tmp_path,
        )
        job_fail = ReportJob(
            framework_name="ISO_27001",
            controls_list=["PR.AC-1"],
            output_format="pdf",
            output_dir=tmp_path,
        )

        results = processor.process_batch([job_ok, job_fail])
        # Both jobs should have results
        assert len(results) == 2
        statuses = {r["status"] for r in results}
        assert "COMPLETED" in statuses
        assert "FAILED" in statuses


# Verify that process_batch() processes all jobs and returns results.
class TestProcessBatch:
    @patch("src.core.batch_processor.safe_path")
    def test_process_batch_returns_all(
        self,
        mock_safe_path: MagicMock,
        processor: BatchProcessor,
        tmp_path: Path,
    ) -> None:
        """process_batch() must return one result per job."""
        mock_safe_path.return_value = tmp_path

        jobs = [
            ReportJob(
                framework_name="NIST_CSF",
                controls_list=["ID.AM-1"],
                output_format="html",
                output_dir=tmp_path,
            ),
            ReportJob(
                framework_name="CIS_V8",
                controls_list=["PR.AC-1"],
                output_format="excel",
                output_dir=tmp_path,
            ),
        ]
        results = processor.process_batch(jobs)
        assert len(results) == 2
        assert all(r["status"] == "COMPLETED" for r in results)


# Verify that path traversal in output_dir raises SecurityError.
class TestPathTraversal:
    def test_traversal_raises_security_error(
        self, processor: BatchProcessor,
    ) -> None:
        """output_dir with '..' must raise SecurityError."""
        malicious_job = ReportJob(
            framework_name="NIST_CSF",
            controls_list=["ID.AM-1"],
            output_format="html",
            output_dir=Path("../../etc/secrets"),
        )
        with pytest.raises(SecurityError):
            processor.process_job(malicious_job)

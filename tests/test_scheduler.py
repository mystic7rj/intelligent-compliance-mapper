# -*- coding: utf-8 -*-
"""Unit tests for the report scheduler.

BatchProcessor is fully mocked — zero real processing.  Tests verify
that scheduling operations return correct types and that configuration
is reflected in summaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.scheduler import ReportScheduler, SchedulerConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_processor() -> MagicMock:
    """Create a mock BatchProcessor."""
    processor = MagicMock()
    # process_batch() returns a single-item results list
    processor.process_batch.return_value = [
        {"job_id": "test-id", "status": "COMPLETED", "output_path": "/tmp/out"},
    ]
    return processor


@pytest.fixture()
def config(tmp_path: Path) -> SchedulerConfig:
    """Build a default SchedulerConfig pointing at a temp directory."""
    return SchedulerConfig(
        interval_hours=12,
        output_format="html",
        output_dir=tmp_path,
        enabled=True,
    )


@pytest.fixture()
def scheduler(
    mock_processor: MagicMock, config: SchedulerConfig,
) -> ReportScheduler:
    """Build a ReportScheduler wired to a mock processor."""
    return ReportScheduler(mock_processor, config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Verify that schedule_once() returns a valid job_id string.
class TestScheduleOnce:
    def test_returns_valid_job_id(self, scheduler: ReportScheduler) -> None:
        """schedule_once() must return a non-empty string job_id."""
        job_id = scheduler.schedule_once("NIST_CSF", ["ID.AM-1"])
        assert isinstance(job_id, str)
        assert len(job_id) > 0


# Verify that get_next_run_time() returns a future datetime.
class TestGetNextRunTime:
    def test_returns_future_datetime(self, scheduler: ReportScheduler) -> None:
        """Next run time must be in the future."""
        now = datetime.now(tz=UTC)
        next_run = scheduler.get_next_run_time()
        assert isinstance(next_run, datetime)
        assert next_run > now


# Verify that get_schedule_summary() contains required keys.
class TestGetScheduleSummary:
    def test_summary_contains_required_keys(
        self, scheduler: ReportScheduler,
    ) -> None:
        """Summary dict must include interval, format, enabled, next_run."""
        summary = scheduler.get_schedule_summary()
        assert "interval_hours" in summary
        assert "output_format" in summary
        assert "enabled" in summary
        assert "next_run" in summary
        # Verify values match config
        assert summary["interval_hours"] == 12
        assert summary["output_format"] == "html"
        assert summary["enabled"] is True


# Verify that a disabled scheduler config is reflected in the summary.
class TestDisabledConfig:
    def test_disabled_reflected_in_summary(
        self, mock_processor: MagicMock, tmp_path: Path,
    ) -> None:
        """When enabled=False, summary must show enabled=False."""
        disabled_config = SchedulerConfig(
            interval_hours=24,
            output_format="pdf",
            output_dir=tmp_path,
            enabled=False,
        )
        scheduler = ReportScheduler(mock_processor, disabled_config)
        summary = scheduler.get_schedule_summary()
        assert summary["enabled"] is False
        assert summary["output_format"] == "pdf"

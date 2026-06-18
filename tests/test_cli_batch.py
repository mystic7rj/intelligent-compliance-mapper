# -*- coding: utf-8 -*-
"""CLI tests for batch command group with mocked processing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.api.cli import cli


# Verify `batch run` exits 0 when valid inputs produce a completed result.
@patch("src.api.commands.batch._build_processor")
@patch("src.api.commands.batch.safe_path")
def test_batch_run_valid_inputs_exit_zero(
    mock_safe_path: MagicMock,
    mock_build_processor: MagicMock,
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    # Create an input controls file accepted by click.Path.
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\nDE.CM-1\n", encoding="utf-8")
    # Configure path validation and batch processor result.
    mock_safe_path.side_effect = [controls_file, tmp_output_dir]
    mock_build_processor.return_value.process_batch.return_value = [
        {"status": "COMPLETED", "job_id": "job-1", "output_path": str(tmp_output_dir / "report.html")},
    ]
    # Invoke the batch run command.
    result = CliRunner().invoke(
        cli,
        ["batch", "run", "--framework", "NIST_CSF", "--controls", str(controls_file), "--format", "html"],
    )
    # Assert command succeeded with expected completion output.
    assert result.exit_code == 0
    assert "Batch Run Complete" in result.output


# Verify `batch run` exits 2 when framework option fails click validation.
def test_batch_run_invalid_framework_exit_two(tmp_path: Path) -> None:
    # Create a controls file to satisfy click.Path(exists=True).
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\n", encoding="utf-8")
    # Invoke command with an invalid framework option.
    result = CliRunner().invoke(
        cli,
        ["batch", "run", "--framework", "INVALID_FW", "--controls", str(controls_file)],
    )
    # Assert click usage error exit code for invalid framework.
    assert result.exit_code == 2
    assert "Invalid framework" in result.output


# Verify `batch list-jobs` displays the empty-queue informational message.
@patch("src.api.commands.batch._job_queue")
def test_batch_list_jobs_shows_empty_queue_message(mock_queue: MagicMock) -> None:
    # Configure queue to return no jobs.
    mock_queue.get_all_jobs.return_value = []
    # Invoke list-jobs command.
    result = CliRunner().invoke(cli, ["batch", "list-jobs"])
    # Assert command succeeds with empty queue panel text.
    assert result.exit_code == 0
    assert "No jobs in the queue" in result.output


# Verify `batch status` with unknown id reports a not-found message.
@patch("src.api.commands.batch._job_queue")
def test_batch_status_unknown_job_id_shows_not_found(mock_queue: MagicMock) -> None:
    # Configure queue status lookup to return unknown.
    mock_queue.get_status.return_value = None
    # Invoke status command with non-existent job id.
    result = CliRunner().invoke(cli, ["batch", "status", "--job-id", "missing-job"])
    # Assert command returns non-zero with not-found output.
    assert result.exit_code == 1
    assert "Not Found" in result.output


# Verify `batch run-all` exits 0 when jobs file contains valid entries.
@patch("src.api.commands.batch._build_processor")
@patch("src.api.commands.batch.safe_path")
def test_batch_run_all_valid_jobs_file_exit_zero(
    mock_safe_path: MagicMock,
    mock_build_processor: MagicMock,
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    # Create controls file referenced by jobs JSON.
    controls_file = tmp_path / "controls.txt"
    controls_file.write_text("PR.AC-1\n", encoding="utf-8")
    # Create valid jobs file with one batch entry.
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [
                {
                    "framework": "NIST_CSF",
                    "controls_file": str(controls_file),
                    "format": "html",
                    "output_dir": str(tmp_output_dir),
                },
            ]
        ),
        encoding="utf-8",
    )
    # Configure safe_path responses for jobs file, controls file, and output dir.
    mock_safe_path.side_effect = [jobs_file, controls_file, tmp_output_dir]
    # Configure processor to return a completed batch result.
    mock_build_processor.return_value.process_batch.return_value = [
        {"status": "COMPLETED", "job_id": "job-1", "output_path": str(tmp_output_dir / "report.html")},
    ]
    # Invoke run-all command.
    result = CliRunner().invoke(cli, ["batch", "run-all", "--jobs-file", str(jobs_file)])
    # Assert command succeeds and prints batch summary panel.
    assert result.exit_code == 0
    assert "Batch Results" in result.output

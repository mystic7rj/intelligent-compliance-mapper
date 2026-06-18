# -*- coding: utf-8 -*-
"""CLI tests for framework command group with mocked dependencies."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.api.cli import cli


# Verify `framework list` renders framework names from a populated repository.
@patch("src.api.commands.framework.get_session")
@patch("src.api.commands.framework.get_engine")
@patch("src.api.commands.framework.FrameworkRepository")
def test_framework_list_populated_shows_names(
    mock_repo_cls: MagicMock,
    _mock_engine: MagicMock,
    mock_session: MagicMock,
) -> None:
    # Build a framework row payload with control families.
    framework_row = SimpleNamespace(
        name="NIST_CSF",
        created_at=datetime.now(tz=UTC),
        families=[
            SimpleNamespace(controls=[SimpleNamespace(control_id="PR.AC-1")]),
            SimpleNamespace(controls=[SimpleNamespace(control_id="DE.CM-1")]),
        ],
    )
    # Configure repository and session context manager mocks.
    mock_repo_cls.return_value.get_all.return_value = [framework_row]
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke the framework list command.
    result = CliRunner().invoke(cli, ["framework", "list"])
    # Assert command succeeds and shows expected framework name.
    assert result.exit_code == 0
    assert "NIST_CSF" in result.output


# Verify `framework load` succeeds with a valid framework JSON file path.
@patch("src.api.commands.framework.get_session")
@patch("src.api.commands.framework.get_engine")
@patch("src.api.commands.framework.FrameworkRepository")
@patch("src.api.commands.framework.FrameworkLoader")
@patch("src.api.commands.framework.safe_path")
def test_framework_load_valid_path_succeeds(
    mock_safe_path: MagicMock,
    mock_loader_cls: MagicMock,
    mock_repo_cls: MagicMock,
    _mock_engine: MagicMock,
    mock_session: MagicMock,
    tmp_path: Path,
    mock_framework,
) -> None:
    # Create a valid framework JSON file for click.Path(exists=True).
    framework_file = tmp_path / "nist_csf.json"
    framework_file.write_text(json.dumps({"name": "NIST_CSF"}), encoding="utf-8")
    # Configure path validation and loader to return framework fixture.
    mock_safe_path.return_value = framework_file
    mock_loader_cls.return_value.load.return_value = mock_framework
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke the framework load command.
    result = CliRunner().invoke(cli, ["framework", "load", "--path", str(framework_file)])
    # Assert command exits successfully and prints success marker.
    assert result.exit_code == 0
    assert "Framework Loaded" in result.output
    assert mock_repo_cls.return_value.save.called


# Verify `framework load` returns an already-loaded message for duplicates.
@patch("src.api.commands.framework.get_session")
@patch("src.api.commands.framework.get_engine")
@patch("src.api.commands.framework.FrameworkRepository")
@patch("src.api.commands.framework.FrameworkLoader")
@patch("src.api.commands.framework.safe_path")
def test_framework_load_duplicate_shows_already_loaded(
    mock_safe_path: MagicMock,
    mock_loader_cls: MagicMock,
    mock_repo_cls: MagicMock,
    _mock_engine: MagicMock,
    mock_session: MagicMock,
    tmp_path: Path,
    mock_framework,
) -> None:
    framework_file = tmp_path / "nist_csf.json"
    framework_file.write_text(json.dumps({"name": "NIST_CSF"}), encoding="utf-8")
    mock_safe_path.return_value = framework_file
    mock_loader_cls.return_value.load.return_value = mock_framework
    mock_repo_cls.return_value.get_by_name.return_value = SimpleNamespace(
        name=mock_framework.name,
        version=mock_framework.version,
    )
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)

    result = CliRunner().invoke(cli, ["framework", "load", "--path", str(framework_file)])

    assert result.exit_code == 0
    assert "Framework Already Loaded" in result.output
    assert not mock_repo_cls.return_value.save.called


# Verify `framework load` renders an error panel when JSON loading fails.
@patch("src.api.commands.framework.FrameworkLoader")
@patch("src.api.commands.framework.safe_path")
def test_framework_load_invalid_json_shows_error_panel(
    mock_safe_path: MagicMock,
    mock_loader_cls: MagicMock,
    tmp_path: Path,
) -> None:
    # Create an invalid JSON file path accepted by click path validation.
    invalid_file = tmp_path / "broken.json"
    invalid_file.write_text("{invalid", encoding="utf-8")
    # Configure safe_path and force loader failure to emulate parse error.
    mock_safe_path.return_value = invalid_file
    mock_loader_cls.return_value.load.side_effect = ValueError("Invalid framework JSON")
    # Invoke the framework load command.
    result = CliRunner().invoke(cli, ["framework", "load", "--path", str(invalid_file)])
    # Assert command fails and renders the load error panel title.
    assert result.exit_code == 1
    assert "Failed to Load Framework" in result.output


# Verify `framework show` displays a controls table for a known framework.
@patch("src.api.commands.framework.console.pager")
@patch("src.api.commands.framework.get_session")
@patch("src.api.commands.framework.get_engine")
@patch("src.api.commands.framework.ControlRepository")
@patch("src.api.commands.framework.FrameworkRepository")
def test_framework_show_valid_name_shows_controls_table(
    mock_fw_repo_cls: MagicMock,
    mock_ctrl_repo_cls: MagicMock,
    _mock_engine: MagicMock,
    mock_session: MagicMock,
    mock_pager: MagicMock,
) -> None:
    # Set up framework and controls returned by repositories.
    mock_fw_repo_cls.return_value.get_by_name.return_value = SimpleNamespace(id="fw-1")
    mock_ctrl_repo_cls.return_value.get_by_framework.return_value = [
        SimpleNamespace(
            control_id="PR.AC-1",
            title="Identity Management",
            description="Control description",
            family=SimpleNamespace(function_id="PR"),
        ),
    ]
    # Configure context managers for database and pager usage.
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_pager.return_value.__enter__ = MagicMock(return_value=None)
    mock_pager.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke framework show with a whitelisted framework name.
    result = CliRunner().invoke(cli, ["framework", "show", "--name", "NIST_CSF"])
    # Assert command succeeds and includes control table content.
    assert result.exit_code == 0
    assert "Controls" in result.output
    assert "PR.AC-1" in result.output


# Verify `framework show` returns the framework-not-found error panel.
@patch("src.api.commands.framework.get_session")
@patch("src.api.commands.framework.get_engine")
@patch("src.api.commands.framework.FrameworkRepository")
def test_framework_show_unknown_name_shows_error_panel(
    mock_fw_repo_cls: MagicMock,
    _mock_engine: MagicMock,
    mock_session: MagicMock,
) -> None:
    # Simulate a missing framework in repository lookup.
    mock_fw_repo_cls.return_value.get_by_name.return_value = None
    # Configure database session context manager.
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke framework show command with valid but unknown name.
    result = CliRunner().invoke(cli, ["framework", "show", "--name", "NIST_CSF"])
    # Assert command exits non-zero and shows not-found panel title.
    assert result.exit_code == 1
    assert "Framework Not Found" in result.output

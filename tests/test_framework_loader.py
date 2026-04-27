"""Tests for the FrameworkLoader — valid loading, error cases, and security."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.framework_loader import (
    FrameworkLoader,
    FrameworkNotFoundError,
    FrameworkValidationError,
)
from src.core.models import Framework
from src.utils.security import SecurityError
from src.utils.validators import ValidationError


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with frameworks subdirectory."""
    frameworks_dir = tmp_path / "frameworks"
    frameworks_dir.mkdir()
    return tmp_path


@pytest.fixture()
def sample_framework_data() -> dict:
    """Return valid NIST CSF framework data for testing."""
    return {
        "name": "NIST CSF",
        "version": "2.0",
        "description": "Test framework",
        "families": [
            {
                "function_name": "Identify",
                "function_id": "ID",
                "description": "Identify function",
                "controls": [
                    {
                        "id": "ID.AM-1",
                        "title": "Asset inventory",
                        "description": "Physical devices are inventoried.",
                        "priority": "high",
                    }
                ],
            }
        ],
    }


@pytest.fixture()
def loader_with_data(
    data_dir: Path, sample_framework_data: dict
) -> FrameworkLoader:
    """Create a FrameworkLoader with valid sample data written to disk."""
    framework_file = data_dir / "frameworks" / "nist_csf.json"
    framework_file.write_text(json.dumps(sample_framework_data), encoding="utf-8")
    return FrameworkLoader(base_dir=data_dir)


class TestLoadValidFramework:
    """Tests for successfully loading a valid framework."""

    def test_load_returns_framework_instance(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        assert isinstance(result, Framework)

    def test_load_framework_name(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        assert result.name == "NIST CSF"

    def test_load_framework_version(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        assert result.version == "2.0"

    def test_load_framework_has_families(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        assert len(result.families) == 1
        assert result.families[0].function_name == "Identify"

    def test_load_framework_total_controls(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        assert result.total_controls == 1

    def test_load_framework_control_details(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        result = loader_with_data.load("nist_csf")
        control = result.families[0].controls[0]
        assert control.id == "ID.AM-1"
        assert control.title == "Asset inventory"


class TestLoadInvalidPath:
    """Tests for loading frameworks that don't exist."""

    def test_nonexistent_framework_raises_not_found(
        self, data_dir: Path
    ) -> None:
        loader = FrameworkLoader(base_dir=data_dir)
        # "soc2" is whitelisted but the file doesn't exist
        with pytest.raises(FrameworkNotFoundError, match="not found"):
            loader.load("soc2")

    def test_invalid_framework_name_raises_validation_error(
        self, data_dir: Path
    ) -> None:
        loader = FrameworkLoader(base_dir=data_dir)
        with pytest.raises(ValidationError, match="not allowed"):
            loader.load("not_a_real_framework")


class TestLoadMalformedJSON:
    """Tests for loading frameworks with invalid JSON content."""

    def test_malformed_json_raises_validation_error(
        self, data_dir: Path
    ) -> None:
        bad_file = data_dir / "frameworks" / "nist_csf.json"
        bad_file.write_text("{invalid json content!!!", encoding="utf-8")
        loader = FrameworkLoader(base_dir=data_dir)

        with pytest.raises(FrameworkValidationError, match="Malformed JSON"):
            loader.load("nist_csf")

    def test_valid_json_but_invalid_schema_raises_validation_error(
        self, data_dir: Path
    ) -> None:
        bad_data = {"wrong_field": "wrong_value"}
        bad_file = data_dir / "frameworks" / "nist_csf.json"
        bad_file.write_text(json.dumps(bad_data), encoding="utf-8")
        loader = FrameworkLoader(base_dir=data_dir)

        with pytest.raises(FrameworkValidationError, match="Validation failed"):
            loader.load("nist_csf")


class TestPathTraversal:
    """Tests for path traversal attack prevention."""

    def test_traversal_in_framework_name_raises_security_error(
        self, data_dir: Path
    ) -> None:
        loader = FrameworkLoader(base_dir=data_dir)
        # This should be caught by the validators before even hitting safe_path
        with pytest.raises((SecurityError, ValidationError)):
            loader.load("../../etc/passwd")

    def test_traversal_with_dotdot_raises_error(
        self, data_dir: Path
    ) -> None:
        loader = FrameworkLoader(base_dir=data_dir)
        with pytest.raises((SecurityError, ValidationError)):
            loader.load("../secrets")


class TestListAvailable:
    """Tests for listing available frameworks."""

    def test_list_available_with_data(
        self, loader_with_data: FrameworkLoader
    ) -> None:
        available = loader_with_data.list_available()
        assert "nist_csf" in available

    def test_list_available_empty_dir(self, data_dir: Path) -> None:
        loader = FrameworkLoader(base_dir=data_dir)
        available = loader.list_available()
        assert available == []

    def test_list_available_nonexistent_dir(self, tmp_path: Path) -> None:
        loader = FrameworkLoader(base_dir=tmp_path / "nonexistent")
        available = loader.list_available()
        assert available == []

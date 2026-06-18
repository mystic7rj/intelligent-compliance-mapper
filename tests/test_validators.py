# -*- coding: utf-8 -*-
"""Tests for input validation utilities."""

from __future__ import annotations

import pytest

from src.utils.validators import (
    ValidationError,
    validate_control_id,
    validate_file_path,
    validate_framework_name,
)


class TestValidateFrameworkName:
    """Tests for framework name whitelist validation."""

    @pytest.mark.parametrize(
        "name",
        ["NIST_CSF", "ISO_27001", "CIS_V8", "SOC2"],
    )
    def test_valid_framework_names(self, name: str) -> None:
        assert validate_framework_name(name) == name

    def test_valid_name_with_whitespace(self) -> None:
        assert validate_framework_name("  nist_csf  ") == "NIST_CSF"

    def test_valid_name_case_insensitive(self) -> None:
        assert validate_framework_name("nist_csf") == "NIST_CSF"

    def test_invalid_framework_name(self) -> None:
        with pytest.raises(ValidationError, match="not allowed"):
            validate_framework_name("unknown_framework")

    def test_empty_framework_name(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_framework_name("")

    def test_whitespace_only_framework_name(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_framework_name("   ")


class TestValidateControlId:
    """Tests for control ID format validation."""

    @pytest.mark.parametrize(
        "control_id",
        [
            # NIST CSF
            "ID.AM-1",
            "PR.AC-1",
            "PR.DS-12",
            "DE.CM-3",
            "RS.RP-1",
            "IDENTIFY.AM-1",
            # ISO 27001
            "A.5.1",
            "A.8.34",
            # CIS v8
            "CIS-01.01",
            "CIS-18.05",
            # SOC 2
            "CC6.1",
            "PI1.5",
            "A1.1",
        ],
    )
    def test_valid_control_ids(self, control_id: str) -> None:
        assert validate_control_id(control_id) == control_id

    def test_valid_control_id_with_whitespace(self) -> None:
        assert validate_control_id("  ID.AM-1  ") == "ID.AM-1"

    @pytest.mark.parametrize(
        "bad_id",
        [
            "invalid",
            "ID-AM.1",
            "id.am-1",
            "ID.AM-123",
            "I.AM-1",
            "ID.A-1",
            "ABCDEFGHIJK.AM-1",
            "",
        ],
    )
    def test_invalid_control_ids(self, bad_id: str) -> None:
        with pytest.raises(ValidationError):
            validate_control_id(bad_id)

    def test_empty_control_id(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_control_id("")


class TestValidateFilePath:
    """Tests for file path safety validation."""

    @pytest.mark.parametrize(
        "path",
        ["data/frameworks/nist_csf.json", "report.pdf", "subdir/file.txt"],
    )
    def test_valid_file_paths(self, path: str) -> None:
        assert validate_file_path(path) == path

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError, match="traversal"):
            validate_file_path("../../etc/passwd")

    def test_single_dotdot_rejected(self) -> None:
        with pytest.raises(ValidationError, match="traversal"):
            validate_file_path("../secret")

    def test_embedded_dotdot_rejected(self) -> None:
        with pytest.raises(ValidationError, match="traversal"):
            validate_file_path("data/../../../etc/shadow")

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValidationError, match="null bytes"):
            validate_file_path("file.txt\x00.jpg")

    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_file_path("")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_file_path("   ")

"""Security hardening tests for sanitization and path validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ValidationError
from src.utils.security import (
    SecurityError,
    safe_path,
    sanitize_cell_value,
    sanitize_filename,
    validate_json_structure,
)


# Verify leading "=" is removed to prevent spreadsheet formula injection.
def test_sanitize_cell_value_strips_equals_formula_prefix() -> None:
    # Sanitize a cell value with an Excel formula payload.
    sanitized = sanitize_cell_value("=SUM(A1:A2)")
    # Assert the dangerous formula prefix is stripped.
    assert sanitized == "SUM(A1:A2)"


# Verify leading "+", "-", and "@" are removed from formula-like values.
@pytest.mark.parametrize("raw, expected", [("+1+2", "1+2"), ("-CMD()", "CMD()"), ("@A1", "A1")])
def test_sanitize_cell_value_strips_other_formula_prefixes(raw: str, expected: str) -> None:
    # Sanitize each formula-injection variant.
    sanitized = sanitize_cell_value(raw)
    # Assert dangerous leading characters are removed.
    assert sanitized == expected


# Verify HTML tags are removed from exported cell content.
def test_sanitize_cell_value_strips_html_tags() -> None:
    # Sanitize HTML-tagged text content.
    sanitized = sanitize_cell_value("<b>alert</b>")
    # Assert tags are removed and text remains.
    assert sanitized == "alert"


# Verify embedded null bytes are removed from cell values.
def test_sanitize_cell_value_strips_null_bytes() -> None:
    # Sanitize value containing null-byte injection.
    sanitized = sanitize_cell_value("good\x00value")
    # Assert the null byte is stripped from output.
    assert sanitized == "goodvalue"


# Verify path separators are removed from filenames.
def test_sanitize_filename_removes_path_separators() -> None:
    # Sanitize a filename containing traversal separators.
    sanitized = sanitize_filename("..\\unsafe/../report.html")
    # Assert slash characters are removed from resulting filename.
    assert "\\" not in sanitized and "/" not in sanitized


# Verify unsupported special characters are removed from filenames.
def test_sanitize_filename_removes_special_characters() -> None:
    # Sanitize filename containing forbidden punctuation.
    sanitized = sanitize_filename("my*report?:2026!.xlsx")
    # Assert only allowed characters are preserved.
    assert sanitized == "myreport2026.xlsx"


# Verify only alphanumeric, dash, underscore, and dot are preserved.
def test_sanitize_filename_allows_safe_characters() -> None:
    # Sanitize an already-safe filename.
    sanitized = sanitize_filename("Q1_audit-report.v1.2")
    # Assert safe filename remains unchanged.
    assert sanitized == "Q1_audit-report.v1.2"


# Verify required-key validation succeeds when all keys are present.
def test_validate_json_structure_passes_with_required_keys() -> None:
    # Validate a complete JSON-like payload.
    is_valid = validate_json_structure({"name": "NIST", "version": "2.0"}, ["name", "version"])
    # Assert validation passes and returns True.
    assert is_valid is True


# Verify required-key validation raises ValidationError when key is missing.
def test_validate_json_structure_raises_on_missing_key() -> None:
    # Validate payload that omits a required key.
    with pytest.raises(ValidationError, match="Missing required keys"):
        validate_json_structure({"name": "NIST"}, ["name", "version"])


# Verify safe_path rejects null-byte path injection attempts.
def test_safe_path_blocks_null_byte_injection(tmp_path: Path) -> None:
    # Attempt to resolve a path containing a null byte.
    with pytest.raises(SecurityError, match="null bytes"):
        safe_path(tmp_path, "report.txt\x00.html")


# Verify safe_path rejects unicode-encoded traversal payloads.
def test_safe_path_blocks_unicode_path_traversal_attempts(tmp_path: Path) -> None:
    # Attempt traversal using percent-encoded ".." with unicode slash.
    with pytest.raises(SecurityError, match="traversal"):
        safe_path(tmp_path, "%2E%2E∕secret.txt")

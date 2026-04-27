"""Input validation utilities for the Compliance Mapper.

Provides whitelist-based framework name validation, path safety checks,
and regex-based control ID validation — all using Pydantic where applicable.
"""

from __future__ import annotations

import re

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Whitelist of allowed framework identifiers
ALLOWED_FRAMEWORKS: frozenset[str] = frozenset(
    {"nist_csf", "iso27001", "cis_controls", "soc2"}
)

# Regex pattern for valid control IDs (e.g. "ID.AM-1", "PR.DS-2")
_CONTROL_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z]{2}\.[A-Z]{2}-\d{1,2}$")


class ValidationError(Exception):
    """Raised when input validation fails."""


def validate_framework_name(name: str) -> str:
    """Validate that a framework name is in the allowed whitelist.

    Args:
        name: The framework name to validate.

    Returns:
        The validated framework name (lowercased, stripped).

    Raises:
        ValidationError: If the name is not in the allowed whitelist.
    """
    cleaned = name.strip().lower()

    if not cleaned:
        logger.warning("Empty framework name provided")
        msg = "Framework name cannot be empty"
        raise ValidationError(msg)

    if cleaned not in ALLOWED_FRAMEWORKS:
        logger.warning(
            "Invalid framework name attempted",
            extra={"framework_name": cleaned},
        )
        msg = (
            f"Framework '{cleaned}' is not allowed. "
            f"Allowed frameworks: {sorted(ALLOWED_FRAMEWORKS)}"
        )
        raise ValidationError(msg)

    return cleaned


def validate_file_path(path: str) -> str:
    """Validate a file path string for safety.

    Rejects paths containing traversal sequences or null bytes.

    Args:
        path: The file path string to validate.

    Returns:
        The validated path string.

    Raises:
        ValidationError: If the path contains traversal or dangerous characters.
    """
    if not path or not path.strip():
        msg = "File path cannot be empty"
        raise ValidationError(msg)

    # Reject null bytes
    if "\x00" in path:
        logger.warning("Null byte detected in file path")
        msg = "File path contains null bytes"
        raise ValidationError(msg)

    # Reject path traversal
    if ".." in path:
        logger.warning(
            "Path traversal attempt in file path",
            extra={"path": path},
        )
        msg = f"Path traversal detected in: {path}"
        raise ValidationError(msg)

    return path.strip()


def validate_control_id(control_id: str) -> str:
    """Validate a control ID matches the expected format.

    Expected format: Two uppercase letters, a dot, two uppercase letters,
    a hyphen, and one or two digits (e.g. 'ID.AM-1', 'PR.DS-12').

    Args:
        control_id: The control ID string to validate.

    Returns:
        The validated control ID.

    Raises:
        ValidationError: If the control ID does not match the expected format.
    """
    cleaned = control_id.strip()

    if not cleaned:
        msg = "Control ID cannot be empty"
        raise ValidationError(msg)

    if not _CONTROL_ID_PATTERN.match(cleaned):
        logger.warning(
            "Invalid control ID format",
            extra={"control_id": cleaned},
        )
        msg = (
            f"Control ID '{cleaned}' does not match required format. "
            f"Expected pattern: XX.XX-N (e.g. 'ID.AM-1')"
        )
        raise ValidationError(msg)

    return cleaned

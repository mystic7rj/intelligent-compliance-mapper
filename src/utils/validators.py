# -*- coding: utf-8 -*-
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
    {"NIST_CSF", "ISO_27001", "CIS_V8", "SOC2"}
)

# Regex pattern for valid control IDs supporting NIST CSF, ISO 27001, CIS v8, and SOC2
_CONTROL_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^("
    r"[A-Z]{2,10}\.[A-Z]{2,4}-\d{1,2}"    # NIST CSF: ID.AM-1, GV.OC-01
    r"|[A-Z]\.\d{1,2}\.\d{1,2}"            # ISO 27001: A.5.1, A.8.34
    r"|[A-Z]{2,3}-\d{2}\.\d{2}"            # CIS v8: CIS-01.01, CIS-18.05
    r"|[A-Z]{1,3}\d{1,2}\.\d{1,2}"         # SOC 2: CC1.1, CC6.8, PI1.5, A1.1
    r")$"
)


class ValidationError(Exception):
    """Raised when input validation fails."""


def validate_framework_name(name: str) -> str:
    """Validate that a framework name is in the allowed whitelist.

    Args:
        name: The framework name to validate.

    Returns:
        The validated framework name (uppercased, stripped).

    Raises:
        ValidationError: If the name is not in the allowed whitelist.
    """
    cleaned = name.strip().upper()

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

    Accepts control IDs from four frameworks:
    - NIST CSF: ID.AM-1, GV.OC-01
    - ISO 27001: A.5.1, A.8.34
    - CIS v8: CIS-01.01, CIS-18.05
    - SOC 2: CC1.1, CC6.8, PI1.5, A1.1

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
            f"Expected format: NIST (ID.AM-1), ISO (A.5.1), CIS (CIS-01.01), or SOC2 (CC6.1)"
        )
        raise ValidationError(msg)

    return cleaned

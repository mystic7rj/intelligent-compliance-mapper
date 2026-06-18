# -*- coding: utf-8 -*-
"""Security utilities for safe file system access.

SECURITY: Path Traversal Protection — prevents directory traversal attacks
Provides path traversal protection to ensure all file access
stays within the designated base directory. This is the primary
defense against path-based injection attacks.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import unquote
from pathlib import Path

from src.core.exceptions import ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityError(Exception):
    """Raised when a security violation is detected (e.g. path traversal)."""


# Normalize and decode a path string before traversal inspection.
def _normalize_path_input(path_str: str) -> str:
    # Decode percent-encoded content to catch encoded traversal payloads.
    decoded = unquote(path_str)
    # Normalize unicode confusables to canonical representation.
    normalized = unicodedata.normalize("NFKC", decoded)
    # Convert slash-like unicode separators to standard slash.
    for separator in ("\\", "∕", "／", "⁄", "⧸"):
        normalized = normalized.replace(separator, "/")
    # Return normalized path text for consistent checks.
    return normalized


def safe_path(base_dir: Path, user_path: Path | str) -> Path:
    """Resolve a user-supplied path and verify it stays within base_dir.

    All file access in the application must go through this function
    to prevent directory traversal attacks.

    Args:
        base_dir: The root directory that all paths must remain within.
        user_path: The user-supplied path to validate. Accepts both
            ``Path`` objects and strings for convenience.

    Returns:
        The resolved absolute ``Path`` if it is safely within ``base_dir``.

    Raises:
        SecurityError: If the resolved path escapes ``base_dir``, contains
            null bytes, or includes traversal components.
    """
    path_str = str(user_path)
    # Normalize path text to detect encoded or unicode traversal patterns.
    normalized_path = _normalize_path_input(path_str)

    # Reject null bytes
    if "\x00" in normalized_path:
        logger.warning("Null byte detected in path input")
        msg = "Path contains null bytes"
        raise SecurityError(msg)

    # Reject explicit traversal patterns before resolution
    path_parts = [part for part in normalized_path.split("/") if part]
    if ".." in path_parts:
        logger.warning(
            "Path traversal attempt detected",
            extra={"attempted_path": normalized_path},
        )
        msg = f"Path traversal detected in: {path_str}"
        raise SecurityError(msg)

    resolved_base = base_dir.resolve()
    resolved_path = (resolved_base / path_str).resolve()

    # Ensure the resolved path is within or equal to the base directory
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        logger.warning(
            "Resolved path escapes base directory",
            extra={
                "base_dir": str(resolved_base),
                "resolved_path": str(resolved_path),
            },
        )
        msg = f"Path '{path_str}' resolves outside of base directory"
        raise SecurityError(msg) from exc

    return resolved_path


# Strip spreadsheet formulas, HTML, and null bytes from export cell content.
def sanitize_cell_value(value: str) -> str:
    # Remove any null bytes that can break downstream parsers.
    without_nulls = value.replace("\x00", "")
    # Remove HTML tags to prevent HTML/script injection in rendered outputs.
    without_tags = re.sub(r"<[^>]+>", "", without_nulls)
    # Strip dangerous spreadsheet formula prefixes from the beginning.
    cleaned = without_tags
    while cleaned.startswith(("=", "+", "-", "@")):
        cleaned = cleaned[1:]
    # Return sanitized cell-safe value.
    return cleaned


# Keep only safe characters in filenames and drop path separators/null bytes.
def sanitize_filename(filename: str) -> str:
    # Remove null bytes and normalize separators to avoid directory injection.
    normalized = filename.replace("\x00", "").replace("\\", "").replace("/", "")
    # Remove all characters except alphanumeric, dash, underscore, and dot.
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "", normalized)
    # Return a non-empty filename fallback when all characters are stripped.
    return sanitized or "unnamed"


# Validate required JSON keys and raise domain ValidationError when missing.
def validate_json_structure(data: dict[str, Any], required_keys: list[str]) -> bool:
    # Identify all keys required by the caller but absent from payload.
    missing_keys = [key for key in required_keys if key not in data]
    # Raise a typed validation error when required keys are missing.
    if missing_keys:
        msg = f"Missing required keys: {', '.join(missing_keys)}"
        raise ValidationError(msg, details={"missing_keys": missing_keys})
    # Return True for valid payloads to support guard-style checks.
    return True

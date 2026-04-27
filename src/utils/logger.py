"""Structured logger for the Compliance Mapper application.

Reads log level from environment variables via python-dotenv.
Uses structured key=value formatting. Automatically redacts any
fields whose names match sensitive keywords.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

_SENSITIVE_KEYWORDS: frozenset[str] = frozenset(
    {"password", "secret", "token", "key", "credential", "api_key"}
)

# Snapshot of default LogRecord attributes for filtering extras
_DEFAULT_RECORD_ATTRS: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, None, None, None).__dict__.keys()
)


class StructuredFormatter(logging.Formatter):
    """A structured log formatter that outputs key=value pairs.

    Automatically redacts any extra fields whose names contain
    sensitive keywords (e.g. password, token, secret).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured key=value output.
        
        Takes in a log record object and converts it to a structured string
        with automatic redaction of sensitive fields.
        
        Args:
            record: The LogRecord object to format.
            
        Returns:
            Formatted string with structure "base message | key=value key=value..."
        """
        # Call parent formatter to get the base message
        base_msg = super().format(record)

        # Extract and redact extra fields
        # Walk through all attributes in the record
        extras: dict[str, Any] = {}
        for attr_key, attr_val in record.__dict__.items():
            # Skip private attributes and default LogRecord fields
            if attr_key.startswith("_") or attr_key in _DEFAULT_RECORD_ATTRS:
                continue
            
            # SECURITY: Auto-redact sensitive field values to prevent credential leaks
            # Check if attribute name contains any sensitive keywords
            if any(kw in attr_key.lower() for kw in _SENSITIVE_KEYWORDS):
                extras[attr_key] = "[REDACTED]"
            else:
                # Include non-sensitive values as-is
                extras[attr_key] = attr_val

        # Append extras to base message if any exist
        if extras:
            # Build key=value pairs separated by spaces
            extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base_msg} | {extra_str}"

        # Return base message alone if no extras
        return base_msg


def get_logger(name: str) -> logging.Logger:
    """Create and return a configured structured logger.

    Reads ``LOG_LEVEL`` from environment variables (defaults to ``INFO``).
    Applies structured formatting with timestamp, level, and module name.

    Args:
        name: The logger name, typically ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance with structured formatting.
    """
    # Read log level from environment or default to INFO
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Validate the log level string against Python's logging constants
    numeric_level = getattr(logging, log_level_str, None)
    if not isinstance(numeric_level, int):
        # Fall back to INFO if invalid level specified
        numeric_level = logging.INFO

    # Get or create logger for this module
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    # Check if handlers already exist before adding new ones
    if not logger.handlers:
        # Create stream handler for console output
        handler = logging.StreamHandler()
        
        # PATTERN: Strategy Pattern — StructuredFormatter is swappable
        # Apply our custom structured formatter
        formatter = StructuredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",  # ISO 8601 format
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Set the logger to the requested level
    logger.setLevel(numeric_level)

    return logger

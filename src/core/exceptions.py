# -*- coding: utf-8 -*-
"""Centralized custom exceptions for the Compliance Mapper project.

Every custom exception carries a ``message`` string and an optional
``details`` dictionary for structured context.  No logic lives here —
these are pure exception definitions only.
"""

from __future__ import annotations

from typing import Any


class ComplianceMapperError(Exception):
    """Base exception for all Compliance Mapper errors.

    Args:
        message: Human-readable error description.
        details: Optional dict with structured context for logging / API responses.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)


class SecurityError(ComplianceMapperError):
    """Raised when a security violation is detected (e.g. path traversal).
    
    This exception is thrown when the system detects potential security attacks
    like directory traversal, null byte injection, or other malicious input.
    """


class ValidationError(ComplianceMapperError):
    """Raised when input validation fails.
    
    Thrown when user input doesn't meet required format or business rules,
    such as invalid framework names, malformed control IDs, or missing fields.
    """


class FrameworkNotFoundError(ComplianceMapperError):
    """Raised when a requested compliance framework does not exist.
    
    Indicates that the user requested a framework that is not in the database
    or not part of the supported framework whitelist.
    """


class GapAnalysisError(ComplianceMapperError):
    """Raised when gap analysis processing fails.
    
    Thrown when the gap analysis pipeline encounters errors during comparison
    of implemented controls against framework requirements.
    """


class RiskScoringError(ComplianceMapperError):
    """Raised when risk scoring processing fails.
    
    Indicates errors during risk calculation, such as invalid input data or
    mathematical errors in risk score computation.
    """


class ReportGenerationError(ComplianceMapperError):
    """Raised when report generation fails for any reason.
    
    Thrown when PDF, HTML, or Excel report generation encounters errors like
    template issues, file write failures, or data formatting problems.
    """

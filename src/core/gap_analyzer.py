"""Gap analysis engine for the Compliance Mapper.

Compares a framework's full control set against a list of implemented
control IDs to identify compliance gaps.  Receives its data source via
dependency injection (a repository-like object with a ``get_by_name``
method) — never imports or creates a repository directly.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from src.core.exceptions import FrameworkNotFoundError, GapAnalysisError, ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SECURITY: Whitelist of allowed framework names to prevent injection attacks
# Only these exact framework names are permitted for gap analysis
ALLOWED_FRAMEWORKS: frozenset[str] = frozenset(
    {"NIST_CSF", "ISO_27001", "CIS_V8", "SOC2"}
)

# SECURITY: Regex pattern validates control ID format to prevent malformed input
# Accepts formats like "ID.AM-1" or "AC-1" but rejects suspicious patterns
_CONTROL_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Z0-9]{2,10}(\.[A-Z0-9\-]{1,10})?$"
)

# ---------------------------------------------------------------------------
# Protocol — what the analyzer needs from its data source
# ---------------------------------------------------------------------------


@runtime_checkable
class FrameworkRepositoryProtocol(Protocol):
    """Minimal interface the gap analyzer expects from a repository."""

    def get_by_name(self, name: str) -> Any: ...


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Control(BaseModel):
    """Lightweight representation of a control in a gap analysis result."""

    model_config = ConfigDict(frozen=True)

    control_id: str = Field(..., description="Control identifier (e.g. 'ID.AM-1')")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(default="", description="Detailed description")
    priority: str = Field(default="medium", description="Priority level")


class GapAnalysisResult(BaseModel):
    """Immutable result of a gap analysis run."""

    model_config = ConfigDict(frozen=True)

    framework_name: str
    total_controls: int
    implemented_count: int
    missing_controls: list[Control]
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    analyzed_at: datetime


# ---------------------------------------------------------------------------
# GapAnalyzer
# ---------------------------------------------------------------------------


class GapAnalyzer:
    """Identifies compliance gaps by comparing framework controls to implemented ones.

    Args:
        repository: Any object satisfying ``FrameworkRepositoryProtocol``
            (must expose ``get_by_name(name) -> framework | None``).
    """

    def __init__(self, repository: FrameworkRepositoryProtocol) -> None:
        self._repository = repository

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        framework_name: str,
        implemented_control_ids: list[str],
    ) -> GapAnalysisResult:
        """Run a gap analysis for the given framework.

        Args:
            framework_name: Must be in the ``ALLOWED_FRAMEWORKS`` whitelist.
            implemented_control_ids: Control IDs the organisation has
                implemented.  Malformed IDs are silently skipped after a
                warning log.

        Returns:
            An immutable ``GapAnalysisResult``.

        Raises:
            ValidationError: If *framework_name* is not in the whitelist.
            FrameworkNotFoundError: If the framework does not exist in the
                repository.
            GapAnalysisError: On any other processing failure.
        """
        # 1. Validate framework name
        cleaned_name = self._validate_framework_name(framework_name)

        # 2. Sanitise implemented control IDs
        valid_ids = self._sanitise_control_ids(implemented_control_ids)

        # 3. Fetch framework from repository
        try:
            framework = self._repository.get_by_name(cleaned_name)
        except Exception as exc:
            msg = f"Repository error while fetching framework '{cleaned_name}'"
            raise GapAnalysisError(msg, details={"cause": str(exc)}) from exc

        if framework is None:
            msg = f"Framework '{cleaned_name}' not found in the database"
            raise FrameworkNotFoundError(msg)

        # 4. Collect all controls from framework
        all_controls = self._extract_controls(framework)
        total = len(all_controls)

        # 5. Identify missing controls
        implemented_set = frozenset(valid_ids)
        missing = [c for c in all_controls if c.control_id not in implemented_set]
        implemented_count = total - len(missing)

        # 6. Compute compliance percentage
        compliance_pct = (implemented_count / total * 100.0) if total > 0 else 0.0

        result = GapAnalysisResult(
            framework_name=cleaned_name,
            total_controls=total,
            implemented_count=implemented_count,
            missing_controls=missing,
            compliance_percentage=round(compliance_pct, 2),
            analyzed_at=datetime.now(tz=UTC),
        )

        logger.info(
            "Gap analysis complete",
            extra={
                "framework": cleaned_name,
                "total_controls": total,
                "implemented": implemented_count,
                "compliance_pct": result.compliance_percentage,
            },
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_framework_name(name: str) -> str:
        """Validate and normalise framework name against the whitelist."""
        cleaned = name.strip().upper()
        if not cleaned:
            msg = "Framework name cannot be empty"
            raise ValidationError(msg)
        if cleaned not in ALLOWED_FRAMEWORKS:
            msg = (
                f"Framework '{cleaned}' is not allowed. "
                f"Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
            )
            raise ValidationError(msg, details={"allowed": sorted(ALLOWED_FRAMEWORKS)})
        return cleaned

    @staticmethod
    def _sanitise_control_ids(ids: list[str]) -> list[str]:
        """Return only well-formed control IDs; skip bad ones with a warning."""
        valid: list[str] = []
        for raw_id in ids:
            stripped = raw_id.strip()
            if _CONTROL_ID_PATTERN.match(stripped):
                valid.append(stripped)
            else:
                logger.warning(
                    "Skipping malformed control ID",
                    extra={"raw_control_id": stripped},
                )
        return valid

    @staticmethod
    def _extract_controls(framework: Any) -> list[Control]:
        """Walk framework → families → controls and build Control list."""
        controls: list[Control] = []
        for family in framework.families:
            for ctrl in family.controls:
                controls.append(
                    Control(
                        control_id=ctrl.control_id,
                        title=ctrl.title,
                        description=getattr(ctrl, "description", ""),
                        priority=getattr(ctrl, "priority", "medium"),
                    )
                )
        return controls

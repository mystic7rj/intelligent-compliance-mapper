# -*- coding: utf-8 -*-
"""In-memory trend tracker for analytics summaries.

Stores framework analytics snapshots and provides historical trend and
improvement calculations with validation safeguards.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.analytics import AnalyticsSummary
from src.core.exceptions import ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrendEntry(BaseModel):
    """Immutable trend snapshot derived from analytics summaries."""

    model_config = ConfigDict(frozen=True)

    framework_name: str
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    maturity_level: str
    recorded_at: datetime


class TrendTracker:
    """Tracks analytics history in memory for each framework."""

    # Initialize in-memory list storage for trend snapshots.
    def __init__(self) -> None:
        # Keep trend entries in a simple list for deterministic ordering.
        self._entries: list[TrendEntry] = []

    # Record one analytics summary as a new trend entry.
    def record(self, summary: AnalyticsSummary) -> None:
        # Create immutable trend entry from analytics summary.
        entry = TrendEntry(
            framework_name=summary.framework_name,
            compliance_percentage=summary.compliance_percentage,
            risk_score=summary.risk_score,
            maturity_level=summary.maturity_level,
            recorded_at=summary.generated_at,
        )

        # Append entry to in-memory storage.
        self._entries.append(entry)

        # Log snapshot recording for observability.
        logger.info(
            "Trend entry recorded",
            extra={
                "framework": entry.framework_name,
                "recorded_at": entry.recorded_at.isoformat(),
            },
        )

    # Return all entries for a framework sorted by ascending date.
    def get_trend(self, framework_name: str) -> list[TrendEntry]:
        # Validate framework name before querying.
        cleaned_name = self._validate_framework_name(framework_name)

        # Filter entries for requested framework only.
        matching = [entry for entry in self._entries if entry.framework_name == cleaned_name]

        # Return entries sorted oldest-to-newest by timestamp.
        return sorted(matching, key=lambda entry: entry.recorded_at)

    # Return latest trend snapshot for framework, or None if absent.
    def get_latest(self, framework_name: str) -> TrendEntry | None:
        # Fetch ordered trend entries for framework.
        entries = self.get_trend(framework_name)

        # Return None when framework has no snapshots.
        if not entries:
            return None

        # Return final item as latest snapshot.
        return entries[-1]

    # Calculate improvement delta from first to latest trend entry.
    def calculate_improvement(self, framework_name: str) -> dict[str, float | int | datetime | None]:
        # Load ordered entries for improvement calculation.
        entries = self.get_trend(framework_name)

        # Return empty baseline structure if no snapshots exist.
        if not entries:
            return {
                "first_recorded": None,
                "latest_recorded": None,
                "compliance_change": 0.0,
                "risk_change": 0.0,
                "total_snapshots": 0,
            }

        # Resolve first and latest snapshots for delta comparison.
        first = entries[0]
        latest = entries[-1]

        # Compute compliance change as latest minus first.
        compliance_change = round(latest.compliance_percentage - first.compliance_percentage, 2)

        # Compute risk change as latest minus first.
        risk_change = round(latest.risk_score - first.risk_score, 2)

        # Return required improvement statistics payload.
        return {
            "first_recorded": first.recorded_at,
            "latest_recorded": latest.recorded_at,
            "compliance_change": compliance_change,
            "risk_change": risk_change,
            "total_snapshots": len(entries),
        }

    # Remove all trend entries for one framework.
    def clear(self, framework_name: str) -> None:
        # Validate framework name before deletion.
        cleaned_name = self._validate_framework_name(framework_name)

        # Keep only entries from other frameworks.
        self._entries = [entry for entry in self._entries if entry.framework_name != cleaned_name]

        # Log clear action for observability.
        logger.info("Trend entries cleared", extra={"framework": cleaned_name})

    # Validate that framework name is not empty.
    @staticmethod
    def _validate_framework_name(name: str) -> str:
        # Normalize incoming framework name.
        cleaned = name.strip().upper()

        # Reject empty framework names.
        if not cleaned:
            msg = "Framework name cannot be empty"
            raise ValidationError(msg)

        # Return normalized framework name.
        return cleaned

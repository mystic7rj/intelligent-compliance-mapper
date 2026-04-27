"""Tests for in-memory analytics trend tracking behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.analytics import AnalyticsSummary
from src.core.exceptions import ValidationError
from src.core.trend_tracker import TrendTracker


# Build an analytics summary object for trend tracker tests.
def _make_summary(
    framework_name: str,
    compliance_percentage: float,
    risk_score: float,
    maturity_level: str,
    generated_at: datetime,
) -> AnalyticsSummary:
    # Return immutable analytics summary with required fields.
    return AnalyticsSummary(
        framework_name=framework_name,
        compliance_percentage=compliance_percentage,
        risk_score=risk_score,
        maturity_level=maturity_level,
        total_controls=20,
        critical_gaps=1,
        high_gaps=1,
        medium_gaps=1,
        low_gaps=1,
        generated_at=generated_at,
    )


# Test that record adds a trend entry for the framework.
def test_record_adds_entry() -> None:
    # Create tracker and sample summary input.
    tracker = TrendTracker()
    summary = _make_summary(
        framework_name="NIST_CSF",
        compliance_percentage=60.0,
        risk_score=50.0,
        maturity_level="DEFINED",
        generated_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    # Record one summary and fetch trend list.
    tracker.record(summary)
    entries = tracker.get_trend("NIST_CSF")

    # Verify one entry was stored.
    assert len(entries) == 1


# Test that get_trend returns entries in ascending date order.
def test_get_trend_returns_sorted_entries() -> None:
    # Create tracker and two out-of-order summaries.
    tracker = TrendTracker()
    late = _make_summary("NIST_CSF", 70.0, 45.0, "MANAGED", datetime(2026, 3, 10, tzinfo=UTC))
    early = _make_summary("NIST_CSF", 50.0, 60.0, "DEFINED", datetime(2026, 3, 1, tzinfo=UTC))

    # Record snapshots in reverse chronological order.
    tracker.record(late)
    tracker.record(early)

    # Retrieve trend and verify ascending timestamps.
    entries = tracker.get_trend("NIST_CSF")
    assert entries[0].recorded_at <= entries[1].recorded_at


# Test that get_latest returns the most recent trend entry.
def test_get_latest_returns_most_recent_entry() -> None:
    # Create tracker and record multiple snapshots.
    tracker = TrendTracker()
    tracker.record(_make_summary("NIST_CSF", 55.0, 58.0, "DEFINED", datetime(2026, 3, 2, tzinfo=UTC)))
    tracker.record(_make_summary("NIST_CSF", 75.0, 42.0, "MANAGED", datetime(2026, 3, 12, tzinfo=UTC)))

    # Fetch latest entry and verify it matches newest date.
    latest = tracker.get_latest("NIST_CSF")
    assert latest is not None
    assert latest.recorded_at == datetime(2026, 3, 12, tzinfo=UTC)


# Test that get_latest returns None for unknown frameworks.
def test_get_latest_returns_none_for_unknown_framework() -> None:
    # Create tracker with no entries for requested framework.
    tracker = TrendTracker()

    # Verify unknown framework has no latest snapshot.
    assert tracker.get_latest("ISO_27001") is None


# Test that calculate_improvement returns expected compliance delta.
def test_calculate_improvement_returns_correct_compliance_change() -> None:
    # Create tracker and record baseline plus improved snapshot.
    tracker = TrendTracker()
    tracker.record(_make_summary("NIST_CSF", 40.0, 70.0, "DEVELOPING", datetime(2026, 3, 1, tzinfo=UTC)))
    tracker.record(_make_summary("NIST_CSF", 65.0, 50.0, "DEFINED", datetime(2026, 3, 20, tzinfo=UTC)))

    # Calculate improvement payload for framework.
    improvement = tracker.calculate_improvement("NIST_CSF")

    # Verify compliance moved by the expected amount.
    assert improvement["compliance_change"] == 25.0


# Test that clear removes only entries for one framework.
def test_clear_removes_entries_for_one_framework_only() -> None:
    # Create tracker and record entries for two frameworks.
    tracker = TrendTracker()
    tracker.record(_make_summary("NIST_CSF", 50.0, 60.0, "DEFINED", datetime(2026, 3, 1, tzinfo=UTC)))
    tracker.record(_make_summary("ISO_27001", 60.0, 55.0, "DEFINED", datetime(2026, 3, 1, tzinfo=UTC)))

    # Clear only one framework and inspect both trend lists.
    tracker.clear("NIST_CSF")
    nist_entries = tracker.get_trend("NIST_CSF")
    iso_entries = tracker.get_trend("ISO_27001")

    # Verify only targeted framework entries were removed.
    assert len(nist_entries) == 0
    assert len(iso_entries) == 1


# Test that empty framework names raise ValidationError.
def test_empty_framework_name_raises_validation_error() -> None:
    # Create tracker used for validation check.
    tracker = TrendTracker()

    # Verify framework validation rejects empty names.
    with pytest.raises(ValidationError):
        tracker.get_trend("   ")

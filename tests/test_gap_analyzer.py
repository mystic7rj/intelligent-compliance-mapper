# -*- coding: utf-8 -*-
"""Tests for the GapAnalyzer — validation, gap detection, and error handling.

Uses a lightweight mock repository backed by simple data classes — no real
database or ORM imports are needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.core.gap_analyzer import GapAnalysisResult, GapAnalyzer

# ---------------------------------------------------------------------------
# Mock objects (no ORM dependency)
# ---------------------------------------------------------------------------


@dataclass
class MockControl:
    """Mimics ControlTable attributes used by GapAnalyzer."""

    control_id: str
    title: str
    description: str = ""
    priority: str = "medium"


@dataclass
class MockFamily:
    """Mimics ControlFamilyTable with a list of controls."""

    function_name: str
    function_id: str
    controls: list[MockControl] = field(default_factory=list)


@dataclass
class MockFramework:
    """Mimics FrameworkTable with nested families → controls."""

    name: str
    version: str
    families: list[MockFamily] = field(default_factory=list)


class MockRepository:
    """In-memory repository satisfying FrameworkRepositoryProtocol."""

    def __init__(self, frameworks: dict[str, MockFramework] | None = None) -> None:
        self._data: dict[str, MockFramework] = frameworks or {}

    def get_by_name(self, name: str) -> MockFramework | None:
        return self._data.get(name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_CONTROLS = [
    MockControl(control_id="ID.AM-1", title="Asset inventory", priority="high"),
    MockControl(control_id="ID.AM-2", title="Software inventory", priority="medium"),
    MockControl(control_id="PR.AC-1", title="Access control", priority="critical"),
    MockControl(control_id="PR.DS-1", title="Data protection", priority="high"),
    MockControl(control_id="DE.CM-1", title="Monitoring", priority="medium"),
]


@pytest.fixture()
def sample_framework() -> MockFramework:
    """Return a framework with 5 controls across 3 families."""
    return MockFramework(
        name="NIST_CSF",
        version="2.0",
        families=[
            MockFamily(
                function_name="Identify",
                function_id="ID",
                controls=_SAMPLE_CONTROLS[:2],
            ),
            MockFamily(
                function_name="Protect",
                function_id="PR",
                controls=_SAMPLE_CONTROLS[2:4],
            ),
            MockFamily(
                function_name="Detect",
                function_id="DE",
                controls=_SAMPLE_CONTROLS[4:],
            ),
        ],
    )


@pytest.fixture()
def repo_with_data(sample_framework: MockFramework) -> MockRepository:
    """Repository pre-loaded with one framework."""
    return MockRepository(frameworks={"NIST_CSF": sample_framework})


@pytest.fixture()
def analyzer(repo_with_data: MockRepository) -> GapAnalyzer:
    """GapAnalyzer wired to the mock repository."""
    return GapAnalyzer(repository=repo_with_data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidGapAnalysis:
    """Tests for successful gap analysis runs."""

    def test_correct_compliance_percentage(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1", "PR.AC-1"])
        # 2 of 5 implemented → 40%
        assert result.compliance_percentage == 40.0

    def test_result_is_gap_analysis_result(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1"])
        assert isinstance(result, GapAnalysisResult)

    def test_missing_controls_count(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1", "ID.AM-2"])
        assert len(result.missing_controls) == 3

    def test_total_controls(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1"])
        assert result.total_controls == 5

    def test_framework_name_in_result(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1"])
        assert result.framework_name == "NIST_CSF"

    def test_analyzed_at_is_set(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1"])
        assert result.analyzed_at is not None

    def test_result_is_immutable(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["ID.AM-1"])
        with pytest.raises(PydanticValidationError):
            result.compliance_percentage = 99.0  # type: ignore[misc]


class TestFrameworkNameValidation:
    """Tests for framework name whitelist validation."""

    def test_unknown_framework_name_raises(self, analyzer: GapAnalyzer) -> None:
        with pytest.raises(ValidationError, match="not allowed"):
            analyzer.analyze("UNKNOWN_FW", ["ID.AM-1"])

    def test_empty_framework_name_raises(self, analyzer: GapAnalyzer) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            analyzer.analyze("", ["ID.AM-1"])

    def test_case_insensitive_name(self, analyzer: GapAnalyzer) -> None:
        # "nist_csf" should be normalised to "NIST_CSF"
        result = analyzer.analyze("nist_csf", ["ID.AM-1"])
        assert result.framework_name == "NIST_CSF"


class TestFrameworkNotFound:
    """Tests for missing frameworks."""

    def test_missing_framework_raises(self) -> None:
        empty_repo = MockRepository()
        analyzer = GapAnalyzer(repository=empty_repo)
        with pytest.raises(FrameworkNotFoundError, match="not found"):
            analyzer.analyze("NIST_CSF", ["ID.AM-1"])


class TestMalformedControlIds:
    """Tests for invalid control ID handling."""

    def test_malformed_ids_skipped_not_crashed(self, analyzer: GapAnalyzer) -> None:
        # Mix of valid and invalid IDs — analyzer should not crash
        result = analyzer.analyze(
            "NIST_CSF",
            ["ID.AM-1", "!!!invalid!!!", "", "lowercase"],
        )
        # Only "ID.AM-1" is valid → 1 of 5 implemented
        assert result.implemented_count == 1
        assert result.compliance_percentage == 20.0

    def test_all_invalid_ids_skipped(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", ["bad!", "@#$", ""])
        assert result.implemented_count == 0


class TestEmptyImplementedList:
    """Tests for 0% compliance edge case."""

    def test_empty_list_returns_zero_compliance(self, analyzer: GapAnalyzer) -> None:
        result = analyzer.analyze("NIST_CSF", [])
        assert result.compliance_percentage == 0.0
        assert result.implemented_count == 0
        assert len(result.missing_controls) == 5

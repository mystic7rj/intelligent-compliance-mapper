"""Tests for ControlMatcher — matching, confidence, validation, coverage.

EmbeddingGenerator, SimilarityCalculator, and repositories are fully mocked
so no real ML model or database is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.ml.control_matcher import ControlMatch, ControlMatcher, _score_to_confidence
from src.ml.similarity import SimilarityMatch


# ---------------------------------------------------------------------------
# Mock objects
# ---------------------------------------------------------------------------

_MOCK_DIM = 384


@dataclass
class MockControl:
    """Mimics ControlTable attributes used by ControlMatcher."""

    control_id: str
    title: str
    description: str = ""


@dataclass
class MockFramework:
    """Mimics FrameworkTable with an id and name."""

    id: str
    name: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_embedding_generator() -> MagicMock:
    """Return a mocked EmbeddingGenerator."""
    gen = MagicMock()
    # generate_single returns a random 1-D vector
    gen.generate_single.return_value = np.random.default_rng(0).random(_MOCK_DIM)
    # generate returns a 2-D array whose first axis matches input length
    gen.generate.side_effect = lambda texts: np.random.default_rng(0).random(
        (len(texts), _MOCK_DIM)
    )
    return gen


@pytest.fixture()
def mock_similarity_calculator() -> MagicMock:
    """Return a mocked SimilarityCalculator that produces predefined matches."""
    calc = MagicMock()
    # Default find_similar returns two matches with different scores
    calc.find_similar.return_value = [
        SimilarityMatch(candidate_id="0", score=0.92, rank=1),
        SimilarityMatch(candidate_id="1", score=0.80, rank=2),
    ]
    return calc


@pytest.fixture()
def mock_framework_repo() -> MagicMock:
    """Return a mocked FrameworkRepository with two frameworks."""
    repo = MagicMock()

    # Map framework names to mock objects
    frameworks = {
        "NIST_CSF": MockFramework(id="fw-1", name="NIST_CSF"),
        "ISO_27001": MockFramework(id="fw-2", name="ISO_27001"),
    }
    repo.get_by_name.side_effect = lambda name: frameworks.get(name)
    return repo


@pytest.fixture()
def mock_control_repo() -> MagicMock:
    """Return a mocked ControlRepository with controls for two frameworks."""
    repo = MagicMock()

    controls = {
        "fw-1": [
            MockControl(control_id="ID.AM-1", title="Asset inventory"),
            MockControl(control_id="PR.AC-1", title="Access control"),
        ],
        "fw-2": [
            MockControl(control_id="A.5.1", title="Information security policies"),
            MockControl(control_id="A.6.1", title="Organization of information security"),
        ],
    }
    repo.get_by_framework.side_effect = lambda fid: controls.get(fid, [])
    return repo


@pytest.fixture()
def matcher(
    mock_embedding_generator: MagicMock,
    mock_similarity_calculator: MagicMock,
    mock_framework_repo: MagicMock,
    mock_control_repo: MagicMock,
) -> ControlMatcher:
    """Return a fully-wired ControlMatcher with mocked dependencies."""
    return ControlMatcher(
        embedding_generator=mock_embedding_generator,
        similarity_calculator=mock_similarity_calculator,
        framework_repository=mock_framework_repo,
        control_repository=mock_control_repo,
    )


# ---------------------------------------------------------------------------
# Tests — match_control
# ---------------------------------------------------------------------------


class TestMatchControl:
    """Tests for the match_control() method."""

    # Test: match_control() returns list of ControlMatch objects
    def test_returns_control_match_list(self, matcher: ControlMatcher) -> None:
        results = matcher.match_control("ID.AM-1", "NIST_CSF", "ISO_27001")

        assert isinstance(results, list)
        assert all(isinstance(r, ControlMatch) for r in results)
        assert len(results) == 2

    # Test: match_framework() returns matches for all source controls
    def test_match_framework_all_controls(self, matcher: ControlMatcher) -> None:
        results = matcher.match_framework("NIST_CSF", "ISO_27001")

        # 2 source controls × 2 matches each = 4 total
        assert isinstance(results, list)
        assert len(results) == 4
        assert all(isinstance(r, ControlMatch) for r in results)


# ---------------------------------------------------------------------------
# Tests — confidence mapping
# ---------------------------------------------------------------------------


class TestConfidence:
    """Tests for the confidence level assignment."""

    # Test: confidence HIGH when score >= 0.90
    def test_high_confidence(self) -> None:
        assert _score_to_confidence(0.95) == "HIGH"
        assert _score_to_confidence(0.90) == "HIGH"

    # Test: confidence MEDIUM when score >= 0.75
    def test_medium_confidence(self) -> None:
        assert _score_to_confidence(0.85) == "MEDIUM"
        assert _score_to_confidence(0.75) == "MEDIUM"

    # Test: confidence LOW when score < 0.75
    def test_low_confidence(self) -> None:
        assert _score_to_confidence(0.70) == "LOW"
        assert _score_to_confidence(0.50) == "LOW"


# ---------------------------------------------------------------------------
# Tests — validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for framework name validation."""

    # Test: invalid framework name raises ValidationError
    def test_invalid_framework_raises(self, matcher: ControlMatcher) -> None:
        with pytest.raises(ValidationError, match="not allowed"):
            matcher.match_control("ID.AM-1", "UNKNOWN_FW", "ISO_27001")

    # Test: missing framework raises FrameworkNotFoundError
    def test_missing_framework_raises(
        self,
        mock_embedding_generator: MagicMock,
        mock_similarity_calculator: MagicMock,
        mock_control_repo: MagicMock,
    ) -> None:
        # Repository returns None for all lookups
        empty_fw_repo = MagicMock()
        empty_fw_repo.get_by_name.return_value = None

        matcher = ControlMatcher(
            embedding_generator=mock_embedding_generator,
            similarity_calculator=mock_similarity_calculator,
            framework_repository=empty_fw_repo,
            control_repository=mock_control_repo,
        )

        with pytest.raises(FrameworkNotFoundError, match="not found"):
            matcher.match_control("ID.AM-1", "NIST_CSF", "ISO_27001")


# ---------------------------------------------------------------------------
# Tests — coverage report
# ---------------------------------------------------------------------------


class TestCoverageReport:
    """Tests for the get_coverage_report() method."""

    # Test: get_coverage_report() returns dict with all required keys
    def test_report_has_required_keys(self, matcher: ControlMatcher) -> None:
        report = matcher.get_coverage_report("NIST_CSF", "ISO_27001")

        assert isinstance(report, dict)
        assert "total_source_controls" in report
        assert "matched_count" in report
        assert "unmatched_count" in report
        assert "average_similarity" in report
        assert "matches_by_confidence" in report

    # Test: report values are consistent and correct
    def test_report_values_consistent(self, matcher: ControlMatcher) -> None:
        report = matcher.get_coverage_report("NIST_CSF", "ISO_27001")

        # total = matched + unmatched
        assert report["total_source_controls"] == (
            report["matched_count"] + report["unmatched_count"]
        )
        # average similarity should be between 0 and 1
        assert 0.0 <= report["average_similarity"] <= 1.0
        # confidence counts should all be non-negative integers
        for level in ("HIGH", "MEDIUM", "LOW"):
            assert level in report["matches_by_confidence"]
            assert report["matches_by_confidence"][level] >= 0

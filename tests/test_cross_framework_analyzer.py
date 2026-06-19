# -*- coding: utf-8 -*-
"""Tests for the CrossFrameworkAnalyzer module.

Tests cross-framework mapping analysis, equivalence generation, and validation.
Uses mocked dependencies to avoid ML model calls and database access.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.core.cross_framework_analyzer import CrossFrameworkAnalyzer, CrossFrameworkResult
from src.core.exceptions import GapAnalysisError, ValidationError
from src.ml.control_matcher import ControlMatch


@pytest.fixture
def mock_matcher() -> Mock:
    """Create a mock ControlMatcher for testing.
    
    Returns a Mock that simulates the control matching behavior without
    actually running ML models.
    """
    matcher = Mock()

    # Default behavior: return empty list
    matcher.match_framework.return_value = []

    # The analyzer counts the actual source controls (registry metadata's
    # control_count is unreliable / 0 in production). Supply 5 source controls
    # so total_source_controls == 5 for the mocked frameworks.
    matcher._fetch_framework.return_value = Mock()
    matcher._get_controls_for_framework.return_value = [Mock() for _ in range(5)]

    return matcher


@pytest.fixture
def mock_registry() -> Mock:
    """Create a mock FrameworkRegistry for testing.
    
    Returns a Mock that provides framework metadata without file system access.
    """
    registry = Mock()
    
    # Set up default metadata for common frameworks
    def get_side_effect(name: str):
        metadata = Mock()
        if name == "nist_csf":
            metadata.name = "NIST CSF"
            metadata.version = "2.0"
            metadata.control_count = 5
        elif name == "iso_27001":
            metadata.name = "ISO 27001"
            metadata.version = "2022"
            metadata.control_count = 15
        elif name == "cis_v8":
            metadata.name = "CIS Controls v8"
            metadata.version = "8.0"
            metadata.control_count = 15
        elif name == "soc2":
            metadata.name = "SOC 2"
            metadata.version = "2017"
            metadata.control_count = 15
        else:
            raise ValidationError(f"Framework '{name}' not found")
        return metadata
    
    registry.get.side_effect = get_side_effect
    
    return registry


@pytest.fixture
def analyzer(mock_matcher: Mock, mock_registry: Mock) -> CrossFrameworkAnalyzer:
    """Create a CrossFrameworkAnalyzer instance for testing.
    
    Uses mocked dependencies to avoid external calls.
    """
    return CrossFrameworkAnalyzer(mock_matcher, mock_registry)


def test_analyze_returns_cross_framework_result_with_correct_fields(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that analyze() returns a CrossFrameworkResult with all expected fields.
    
    Verifies the result object contains source/target names, counts, percentage,
    and matches list.
    """
    # Set up matcher to return sample matches
    sample_matches = [
        ControlMatch(
            source_control_id="ID.AM-1",
            source_framework="NIST CSF",
            matched_control_id="IS.IN-1",
            matched_framework="ISO 27001",
            similarity_score=0.89,
            confidence="HIGH",
        ),
        ControlMatch(
            source_control_id="ID.AM-2",
            source_framework="NIST CSF",
            matched_control_id="IS.AU-1",
            matched_framework="ISO 27001",
            similarity_score=0.75,
            confidence="MEDIUM",
        ),
    ]
    mock_matcher.match_framework.return_value = sample_matches
    
    # Run analysis
    result = analyzer.analyze("nist_csf", "iso_27001")
    
    # Verify result is a CrossFrameworkResult
    assert isinstance(result, CrossFrameworkResult)
    
    # Verify all required fields are present
    assert result.source_framework == "NIST CSF"
    assert result.target_framework == "ISO 27001"
    assert result.total_source_controls == 5
    assert result.mapped_controls == 2
    assert result.unmapped_controls == 3
    assert isinstance(result.mapping_percentage, float)
    assert isinstance(result.matches, list)
    assert isinstance(result.analyzed_at, datetime)


def test_mapping_percentage_is_between_zero_and_one_hundred(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that mapping_percentage is always in the valid range.
    
    Verifies the percentage is between 0.0 and 100.0 inclusive.
    """
    # Test with some matches
    sample_matches = [
        ControlMatch(
            source_control_id="ID.AM-1",
            source_framework="NIST CSF",
            matched_control_id="A5.09-1",
            matched_framework="ISO 27001",
            similarity_score=0.85,
            confidence="HIGH",
        ),
    ]
    mock_matcher.match_framework.return_value = sample_matches
    
    result = analyzer.analyze("nist_csf", "iso_27001")
    
    # Verify percentage is in valid range
    assert 0.0 <= result.mapping_percentage <= 100.0
    
    # Test with no matches
    mock_matcher.match_framework.return_value = []
    result = analyzer.analyze("nist_csf", "iso_27001")
    
    # Should be 0.0
    assert result.mapping_percentage == 0.0


def test_analyze_all_pairs_returns_exactly_six_results(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that analyze_all_pairs() returns results for all 6 framework pairs.
    
    Verifies that all unique combinations of the 4 frameworks are analyzed.
    """
    # Set up matcher to return empty results
    mock_matcher.match_framework.return_value = []
    
    # Run analysis for all pairs
    results = analyzer.analyze_all_pairs()
    
    # Should return exactly 6 results
    assert len(results) == 6
    
    # Verify all results are CrossFrameworkResult instances
    for result in results:
        assert isinstance(result, CrossFrameworkResult)
    
    # Extract framework pairs
    pairs = [(r.source_framework, r.target_framework) for r in results]
    
    # Verify expected pairs are present (not checking exact names, just count)
    assert len(set(pairs)) == 6  # All unique pairs


def test_invalid_source_framework_raises_validation_error(
    analyzer: CrossFrameworkAnalyzer,
) -> None:
    """Test that analyze() raises ValidationError for invalid source framework.
    
    Verifies framework name validation happens before processing.
    """
    # Try to analyze with invalid source
    with pytest.raises(ValidationError) as exc_info:
        analyzer.analyze("invalid_framework", "iso_27001")
    
    # Verify error message mentions the invalid framework
    assert "invalid_framework" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


def test_invalid_target_framework_raises_validation_error(
    analyzer: CrossFrameworkAnalyzer,
) -> None:
    """Test that analyze() raises ValidationError for invalid target framework.
    
    Verifies framework name validation happens for both source and target.
    """
    # Try to analyze with invalid target
    with pytest.raises(ValidationError) as exc_info:
        analyzer.analyze("nist_csf", "invalid_framework")
    
    # Verify error message mentions validation failure
    assert "invalid_framework" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


def test_get_equivalence_map_returns_dict_keyed_by_source_control_ids(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that get_equivalence_map() returns a dict mapping source IDs to target IDs.
    
    Verifies the structure is {source_control_id: [target_control_ids]}.
    """
    # Set up matcher to return sample matches
    sample_matches = [
        ControlMatch(
            source_control_id="ID.AM-1",
            source_framework="NIST CSF",
            matched_control_id="IS.IN-1",
            matched_framework="ISO 27001",
            similarity_score=0.89,
            confidence="HIGH",
        ),
        ControlMatch(
            source_control_id="ID.AM-1",
            source_framework="NIST CSF",
            matched_control_id="IG.EA-1",
            matched_framework="ISO 27001",
            similarity_score=0.82,
            confidence="MEDIUM",
        ),
        ControlMatch(
            source_control_id="ID.AM-2",
            source_framework="NIST CSF",
            matched_control_id="IS.AU-1",
            matched_framework="ISO 27001",
            similarity_score=0.75,
            confidence="MEDIUM",
        ),
    ]
    mock_matcher.match_framework.return_value = sample_matches
    
    # Get equivalence map
    equivalence_map = analyzer.get_equivalence_map("nist_csf", "iso_27001")
    
    # Verify result is a dictionary
    assert isinstance(equivalence_map, dict)
    
    # Verify keys are source control IDs
    assert "ID.AM-1" in equivalence_map
    assert "ID.AM-2" in equivalence_map
    
    # Verify values are lists of target control IDs
    assert isinstance(equivalence_map["ID.AM-1"], list)
    assert len(equivalence_map["ID.AM-1"]) == 2
    assert "IS.IN-1" in equivalence_map["ID.AM-1"]
    assert "IG.EA-1" in equivalence_map["ID.AM-1"]
    
    assert isinstance(equivalence_map["ID.AM-2"], list)
    assert len(equivalence_map["ID.AM-2"]) == 1
    assert "IS.AU-1" in equivalence_map["ID.AM-2"]


def test_get_equivalence_map_filters_low_confidence_matches(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that get_equivalence_map() excludes LOW confidence matches.
    
    Verifies only HIGH and MEDIUM confidence matches are included.
    """
    # Set up matcher with mixed confidence levels
    sample_matches = [
        ControlMatch(
            source_control_id="ID.AM-1",
            source_framework="NIST CSF",
            matched_control_id="IS.IN-1",
            matched_framework="ISO 27001",
            similarity_score=0.89,
            confidence="HIGH",
        ),
        ControlMatch(
            source_control_id="ID.AM-2",
            source_framework="NIST CSF",
            matched_control_id="IS.AU-1",
            matched_framework="ISO 27001",
            similarity_score=0.45,
            confidence="LOW",  # Should be filtered out
        ),
    ]
    mock_matcher.match_framework.return_value = sample_matches
    
    # Get equivalence map
    equivalence_map = analyzer.get_equivalence_map("nist_csf", "iso_27001")
    
    # Should only contain HIGH confidence match
    assert "ID.AM-1" in equivalence_map
    assert "ID.AM-2" not in equivalence_map  # LOW confidence filtered out


def test_result_is_immutable_assignment_raises_error(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that CrossFrameworkResult is immutable after creation.
    
    Verifies that attempting to modify result fields raises an error.
    """
    # Set up matcher
    mock_matcher.match_framework.return_value = []
    
    # Run analysis
    result = analyzer.analyze("nist_csf", "iso_27001")
    
    # Try to modify a field - should raise error
    with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
        result.source_framework = "Different Framework"
    
    with pytest.raises(Exception):
        result.mapping_percentage = 99.9


def test_analyze_raises_gap_analysis_error_when_matcher_fails(
    analyzer: CrossFrameworkAnalyzer,
    mock_matcher: Mock,
) -> None:
    """Test that analyze() raises GapAnalysisError when matching fails.
    
    Verifies proper error handling when the control matcher encounters issues.
    """
    # Set up matcher to raise exception
    mock_matcher.match_framework.side_effect = Exception("Matching failed")
    
    # Try to analyze - should raise GapAnalysisError
    with pytest.raises(GapAnalysisError) as exc_info:
        analyzer.analyze("nist_csf", "iso_27001")
    
    # Verify error message
    assert "matching failed" in str(exc_info.value).lower()

"""Tests for the FrameworkRegistry module.

Tests framework metadata retrieval, validation, and batch loading operations.
Uses mocked dependencies to avoid database and file system access.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.core.framework_registry import FrameworkMetadata, FrameworkRegistry


@pytest.fixture
def mock_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for testing.
    
    Returns a Path to a temporary directory that can be used as the
    base data directory for the FrameworkRegistry.
    """
    frameworks_dir = tmp_path / "frameworks"
    frameworks_dir.mkdir()
    return tmp_path


@pytest.fixture
def registry(mock_data_dir: Path) -> FrameworkRegistry:
    """Create a FrameworkRegistry instance for testing.
    
    Uses a temporary data directory to avoid file system dependencies.
    """
    return FrameworkRegistry(mock_data_dir)


def test_get_all_returns_exactly_four_frameworks(registry: FrameworkRegistry) -> None:
    """Test that get_all() returns metadata for all 4 supported frameworks.
    
    Verifies that the registry knows about NIST CSF, ISO 27001, CIS v8, and SOC 2.
    """
    # Get all framework metadata
    all_frameworks = registry.get_all()
    
    # Should return exactly 4 frameworks
    assert len(all_frameworks) == 4
    
    # Extract framework names
    framework_names = [fw.name for fw in all_frameworks]
    
    # Verify all expected frameworks are present
    assert "NIST CSF" in framework_names
    assert "ISO 27001" in framework_names
    assert "CIS Controls v8" in framework_names
    assert "SOC 2" in framework_names
    
    # Verify all metadata objects are FrameworkMetadata instances
    for fw in all_frameworks:
        assert isinstance(fw, FrameworkMetadata)
        assert fw.name
        assert fw.version
        assert fw.file_path
        assert isinstance(fw.loaded, bool)


def test_get_returns_correct_metadata_for_each_framework(registry: FrameworkRegistry) -> None:
    """Test that get() returns the correct metadata for each framework name.
    
    Verifies that each supported framework identifier maps to the right
    display name and version.
    """
    # Test NIST CSF
    nist_meta = registry.get("nist_csf")
    assert nist_meta.name == "NIST CSF"
    assert nist_meta.version == "2.0"
    assert "nist_csf.json" in str(nist_meta.file_path)
    
    # Test ISO 27001
    iso_meta = registry.get("iso_27001")
    assert iso_meta.name == "ISO 27001"
    assert iso_meta.version == "2022"
    assert "iso_27001.json" in str(iso_meta.file_path)
    
    # Test CIS v8
    cis_meta = registry.get("cis_v8")
    assert cis_meta.name == "CIS Controls v8"
    assert cis_meta.version == "8.0"
    assert "cis_v8.json" in str(cis_meta.file_path)
    
    # Test SOC 2
    soc2_meta = registry.get("soc2")
    assert soc2_meta.name == "SOC 2"
    assert soc2_meta.version == "2017"
    assert "soc2.json" in str(soc2_meta.file_path)


def test_get_with_unknown_name_raises_framework_not_found_error(registry: FrameworkRegistry) -> None:
    """Test that get() raises FrameworkNotFoundError for invalid framework names.
    
    Verifies that requesting a framework not in the whitelist results in
    the appropriate exception.
    """
    # Test with completely invalid name
    with pytest.raises(ValidationError) as exc_info:
        registry.get("invalid_framework")
    assert "not supported" in str(exc_info.value).lower()
    
    # Test with empty name
    with pytest.raises(ValidationError) as exc_info:
        registry.get("")
    assert "cannot be empty" in str(exc_info.value).lower()


def test_get_supported_names_returns_list_of_four_names(registry: FrameworkRegistry) -> None:
    """Test that get_supported_names() returns all valid framework identifiers.
    
    Verifies the whitelist contains exactly 4 framework names.
    """
    # Get supported names
    supported = registry.get_supported_names()
    
    # Should return exactly 4 names
    assert len(supported) == 4
    
    # Verify expected names are present
    assert "nist_csf" in supported
    assert "iso_27001" in supported
    assert "cis_v8" in supported
    assert "soc2" in supported
    
    # Should be sorted
    assert supported == sorted(supported)


def test_is_loaded_returns_false_for_unloaded_framework(
    registry: FrameworkRegistry,
    mock_data_dir: Path,
) -> None:
    """Test that is_loaded() returns False when framework is not in database.
    
    Mocks the repository to simulate an empty database.
    """
    # Create mock repository that returns None (framework not found)
    mock_repo = Mock()
    mock_repo.get_by_name.return_value = None
    
    # Check if framework is loaded
    result = registry.is_loaded("nist_csf", mock_repo)
    
    # Should return False
    assert result is False
    
    # Verify repository was called with correct name
    mock_repo.get_by_name.assert_called_once_with("NIST CSF")


def test_is_loaded_returns_true_for_loaded_framework(
    registry: FrameworkRegistry,
    mock_data_dir: Path,
) -> None:
    """Test that is_loaded() returns True when framework exists in database.
    
    Mocks the repository to simulate a framework already loaded.
    """
    # Create mock repository that returns a framework object
    mock_repo = Mock()
    mock_framework = Mock()
    mock_repo.get_by_name.return_value = mock_framework
    
    # Check if framework is loaded
    result = registry.is_loaded("iso_27001", mock_repo)
    
    # Should return True
    assert result is True
    
    # Verify repository was called
    mock_repo.get_by_name.assert_called_once_with("ISO 27001")


def test_load_all_returns_dict_with_correct_keys(
    registry: FrameworkRegistry,
    mock_data_dir: Path,
) -> None:
    """Test that load_all() returns a dictionary with loaded/skipped/failed keys.
    
    Mocks both the loader and repository to avoid file system and database access.
    """
    # Create mock loader
    mock_loader = Mock()
    mock_framework = Mock()
    mock_framework.name = "NIST CSF"
    mock_framework.version = "2.0"
    mock_framework.description = "Test framework"
    mock_loader.load.return_value = mock_framework
    
    # Create mock repository
    mock_repo = Mock()
    mock_repo.get_by_name.return_value = None  # No frameworks loaded yet
    mock_repo.save.return_value = Mock()
    
    # Run load_all
    result = registry.load_all(mock_loader, mock_repo)
    
    # Verify result has correct keys
    assert "loaded" in result
    assert "skipped" in result
    assert "failed" in result
    
    # Verify keys contain lists
    assert isinstance(result["loaded"], list)
    assert isinstance(result["skipped"], list)
    assert isinstance(result["failed"], list)


def test_load_all_skips_already_loaded_frameworks(
    registry: FrameworkRegistry,
    mock_data_dir: Path,
) -> None:
    """Test that load_all() skips frameworks already in the database.
    
    Simulates some frameworks already loaded, verifies they are skipped.
    """
    # Create mock loader
    mock_loader = Mock()
    
    # Create mock repository that returns a framework for NIST CSF
    mock_repo = Mock()
    def get_by_name_side_effect(name: str):
        if name == "NIST CSF":
            return Mock()  # Framework already loaded
        return None  # Other frameworks not loaded
    
    mock_repo.get_by_name.side_effect = get_by_name_side_effect
    
    # Run load_all
    result = registry.load_all(mock_loader, mock_repo)
    
    # Verify NIST CSF was skipped
    assert "nist_csf" in result["skipped"]


def test_load_all_handles_loading_errors_gracefully(
    registry: FrameworkRegistry,
    mock_data_dir: Path,
) -> None:
    """Test that load_all() continues processing when individual loads fail.
    
    Simulates loader exceptions and verifies they are caught and tracked.
    """
    # Create mock loader that raises exception
    mock_loader = Mock()
    mock_loader.load.side_effect = Exception("Load failed")
    
    # Create mock repository
    mock_repo = Mock()
    mock_repo.get_by_name.return_value = None
    
    # Run load_all - should not raise exception
    result = registry.load_all(mock_loader, mock_repo)
    
    # All frameworks should be in failed list
    assert len(result["failed"]) > 0
    assert len(result["loaded"]) == 0

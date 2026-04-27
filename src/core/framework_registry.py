"""Framework registry for managing all supported compliance frameworks.

Provides a single source of truth for framework metadata and loading status.
All framework names are validated against a strict whitelist before processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.framework_loader import FrameworkLoader
    from src.data.repositories.framework_repository import FrameworkRepository

logger = get_logger(__name__)

# Whitelist of all supported framework identifiers
SUPPORTED_FRAMEWORKS: frozenset[str] = frozenset(
    {"nist_csf", "iso_27001", "cis_v8", "soc2"}
)


class FrameworkMetadata(BaseModel):
    """Metadata describing a single compliance framework.
    
    Holds information about a framework without loading the full control data.
    This allows fast lookups and listings without database queries.
    
    Attributes:
        name: Human-readable framework name (e.g., "NIST CSF").
        version: Framework version string.
        description: Brief description of the framework.
        control_count: Total number of controls in the framework.
        file_path: Path to the framework JSON file.
        loaded: Whether the framework has been loaded into the database.
    """
    
    # Display name for UI and reports
    name: str = Field(..., description="Framework display name")
    # Version number or year of the framework spec
    version: str = Field(..., description="Framework version")
    # Short summary of framework purpose
    description: str = Field(..., description="Framework description")
    # Total control count — used for progress tracking
    control_count: int = Field(..., ge=0, description="Total control count")
    # Location of the source JSON file
    file_path: Path = Field(..., description="Path to framework JSON file")
    # Database load status flag
    loaded: bool = Field(default=False, description="Whether framework is loaded in DB")


class FrameworkRegistry:
    """Central registry for all supported compliance frameworks.
    
    Provides metadata, validation, and batch loading capabilities for
    all frameworks in the system. All framework names are validated
    against the SUPPORTED_FRAMEWORKS whitelist.
    
    The registry is stateless — it does not hold framework data itself,
    only metadata about what frameworks exist and where to find them.
    """
    
    def __init__(self, data_dir: Path) -> None:
        """Initialize the framework registry.
        
        Args:
            data_dir: Base directory containing the frameworks/ subdirectory.
        """
        self._data_dir = data_dir
        self._frameworks_dir = data_dir / "frameworks"
        logger.info("FrameworkRegistry initialized", extra={"data_dir": str(data_dir)})
    
    def get_all(self) -> list[FrameworkMetadata]:
        """Return metadata for all supported frameworks.
        
        Returns a list with metadata for each framework in the whitelist.
        The control_count and loaded fields will be 0 and False respectively
        until the frameworks are actually loaded.
        
        Returns:
            List of FrameworkMetadata instances for all 4 frameworks.
        """
        # Define metadata for all supported frameworks
        metadata_specs = [
            {
                "name": "NIST CSF",
                "version": "2.0",
                "description": "NIST Cybersecurity Framework version 2.0",
                "file_name": "nist_csf.json",
            },
            {
                "name": "ISO 27001",
                "version": "2022",
                "description": "ISO/IEC 27001:2022 Information Security Management",
                "file_name": "iso_27001.json",
            },
            {
                "name": "CIS Controls v8",
                "version": "8.0",
                "description": "CIS Critical Security Controls version 8",
                "file_name": "cis_v8.json",
            },
            {
                "name": "SOC 2",
                "version": "2017",
                "description": "SOC 2 Trust Service Criteria",
                "file_name": "soc2.json",
            },
        ]
        
        # Build metadata objects for each framework
        all_metadata: list[FrameworkMetadata] = []
        for spec in metadata_specs:
            file_path = self._frameworks_dir / spec["file_name"]
            metadata = FrameworkMetadata(
                name=spec["name"],
                version=spec["version"],
                description=spec["description"],
                control_count=0,  # Will be populated after loading
                file_path=file_path,
                loaded=False,
            )
            all_metadata.append(metadata)
        
        return all_metadata
    
    def get(self, name: str) -> FrameworkMetadata:
        """Get metadata for a specific framework by name.
        
        Framework name is validated against the whitelist. Names are
        case-insensitive and can use underscores or spaces.
        
        Args:
            name: Framework identifier (e.g., "nist_csf", "iso_27001").
        
        Returns:
            FrameworkMetadata for the requested framework.
        
        Raises:
            FrameworkNotFoundError: If the framework name is not in the whitelist.
            ValidationError: If the name is empty or invalid.
        """
        # Validate and normalize the framework name
        normalized = self._validate_framework_name(name)
        
        # Map normalized names to their metadata
        name_mapping = {
            "nist_csf": "NIST CSF",
            "iso_27001": "ISO 27001",
            "cis_v8": "CIS Controls v8",
            "soc2": "SOC 2",
        }
        
        # Find the matching metadata from get_all()
        display_name = name_mapping.get(normalized)
        if not display_name:
            msg = f"Framework '{name}' not found in registry"
            logger.error(msg, extra={"framework_name": name})
            raise FrameworkNotFoundError(msg)
        
        # Return the matching metadata
        all_frameworks = self.get_all()
        for framework in all_frameworks:
            if framework.name == display_name:
                return framework
        
        # Should never reach here if whitelist is correct
        msg = f"Framework '{name}' not found in registry"
        raise FrameworkNotFoundError(msg)
    
    def is_loaded(self, name: str, repo: FrameworkRepository) -> bool:
        """Check if a framework exists in the database.
        
        Args:
            name: Framework identifier to check.
            repo: FrameworkRepository instance for DB queries.
        
        Returns:
            True if the framework exists in the database, False otherwise.
        
        Raises:
            ValidationError: If the framework name is invalid.
        """
        # Validate the framework name
        normalized = self._validate_framework_name(name)
        
        # Map to display name for DB lookup
        name_mapping = {
            "nist_csf": "NIST CSF",
            "iso_27001": "ISO 27001",
            "cis_v8": "CIS Controls v8",
            "soc2": "SOC 2",
        }
        
        display_name = name_mapping[normalized]
        
        # Check if framework exists in database
        result = repo.get_by_name(display_name)
        return result is not None
    
    def load_all(
        self,
        loader: FrameworkLoader,
        repo: FrameworkRepository,
    ) -> dict[str, list[str]]:
        """Load all unloaded frameworks into the database.
        
        Iterates through all supported frameworks and loads any that are
        not already present in the database. Returns a summary of which
        frameworks were loaded, skipped, or failed.
        
        Args:
            loader: FrameworkLoader instance for loading JSON files.
            repo: FrameworkRepository instance for DB operations.
        
        Returns:
            Dictionary with three keys:
                - "loaded": List of framework names that were loaded.
                - "skipped": List of framework names already in DB.
                - "failed": List of framework names that failed to load.
        """
        # Initialize result tracking
        result: dict[str, list[str]] = {
            "loaded": [],
            "skipped": [],
            "failed": [],
        }
        
        # Map framework identifiers to their file names
        framework_files = {
            "nist_csf": "nist_csf",
            "iso_27001": "iso_27001",
            "cis_v8": "cis_v8",
            "soc2": "soc2",
        }
        
        # Attempt to load each framework
        for identifier, file_name in framework_files.items():
            try:
                # Check if already loaded
                if self.is_loaded(identifier, repo):
                    logger.info(f"Framework already loaded: {identifier}")
                    result["skipped"].append(identifier)
                    continue
                
                # Load the framework from JSON
                logger.info(f"Loading framework: {identifier}")
                framework = loader.load(file_name)
                
                # Save to database via repository
                from src.data.schema import FrameworkTable
                framework_row = FrameworkTable(
                    name=framework.name,
                    version=framework.version,
                    description=framework.description,
                )
                repo.save(framework_row)
                
                result["loaded"].append(identifier)
                logger.info(f"Framework loaded successfully: {identifier}")
                
            except Exception as exc:
                # Log the error and continue with next framework
                logger.error(
                    f"Failed to load framework: {identifier}",
                    extra={"error": str(exc)},
                )
                result["failed"].append(identifier)
        
        return result
    
    def get_supported_names(self) -> list[str]:
        """Return list of all valid framework identifiers.
        
        Returns the whitelist of framework names that can be used with
        all registry methods. These are the normalized, lowercase names
        with underscores.
        
        Returns:
            List of valid framework identifiers (e.g., ["nist_csf", "iso_27001"]).
        """
        return sorted(SUPPORTED_FRAMEWORKS)
    
    def _validate_framework_name(self, name: str) -> str:
        """Validate a framework name against the whitelist.
        
        Normalizes the name to lowercase with underscores and checks
        if it exists in the SUPPORTED_FRAMEWORKS set.
        
        Args:
            name: Framework name to validate.
        
        Returns:
            Normalized framework name.
        
        Raises:
            ValidationError: If the name is empty or not in the whitelist.
        """
        # Clean and normalize the input
        if not name or not name.strip():
            msg = "Framework name cannot be empty"
            logger.warning(msg)
            raise ValidationError(msg)
        
        # Normalize to lowercase with underscores
        normalized = name.strip().lower().replace(" ", "_")
        
        # Check against whitelist
        if normalized not in SUPPORTED_FRAMEWORKS:
            msg = (
                f"Framework '{name}' is not supported. "
                f"Allowed frameworks: {sorted(SUPPORTED_FRAMEWORKS)}"
            )
            logger.warning(msg, extra={"framework_name": name})
            raise ValidationError(msg)
        
        return normalized

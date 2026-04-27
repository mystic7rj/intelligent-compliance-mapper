"""Factory-pattern framework loader for the Compliance Mapper.

Loads compliance framework definitions from JSON files in the data directory.
Uses dependency injection for the base directory and validates all paths
through the security module.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.core.models import Framework
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path
from src.utils.validators import validate_framework_name

logger = get_logger(__name__)


class FrameworkNotFoundError(Exception):
    """Raised when a requested framework file does not exist."""


class FrameworkValidationError(Exception):
    """Raised when a framework file contains invalid or malformed data."""


class FrameworkLoader:
    """Loads and validates compliance framework definitions from JSON files.

    Uses dependency injection for the base directory path, and all file
    access is routed through ``safe_path()`` to prevent path traversal.

    Args:
        base_dir: Root directory containing the ``frameworks/`` subdirectory.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._frameworks_dir = base_dir / "frameworks"
        logger.info(
            "FrameworkLoader initialized",
            extra={"base_dir": str(base_dir)},
        )

    def load(self, framework_name: str) -> Framework:
        """Load a compliance framework by name.

        Validates the framework name against the whitelist, resolves the
        file path securely, reads and parses the JSON, and returns a
        validated ``Framework`` model.

        Args:
            framework_name: Name of the framework to load (e.g. 'nist_csf').

        Returns:
            A validated ``Framework`` instance.

        Raises:
            FrameworkNotFoundError: If the framework JSON file does not exist.
            FrameworkValidationError: If the JSON is malformed or fails validation.
            SecurityError: If a path traversal attempt is detected.
        """
        # Step 1: Validate framework name against whitelist
        # SECURITY: Whitelist validation prevents path traversal and unauthorized file access
        # Only framework names in our predefined list can be loaded
        validated_name = validate_framework_name(framework_name)

        # Step 2: Build and validate the file path
        # Construct path to the framework JSON file
        relative_path = f"frameworks/{validated_name}.json"

        try:
            # SECURITY: safe_path() prevents directory traversal attacks
            # It ensures the resolved path stays within base_dir boundaries
            file_path = safe_path(self._base_dir, relative_path)
        except SecurityError:
            # Log security violations for monitoring and incident response
            logger.error(
                "Security violation during framework load",
                extra={"framework_name": validated_name},
            )
            raise

        # Step 3: Check file exists
        # Verify the JSON file is actually present on disk
        if not file_path.exists():
            # Log file not found for debugging
            logger.error(
                "Framework file not found",
                extra={"path": str(file_path)},
            )
            msg = f"Framework file not found: {validated_name}"
            raise FrameworkNotFoundError(msg)

        # Step 4: Read and parse JSON
        # Load file contents from disk with UTF-8 encoding
        try:
            raw_data = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            # Log file read errors (permissions, disk issues, etc.)
            logger.error(
                "Failed to read framework file",
                extra={"path": str(file_path), "error": str(exc)},
            )
            msg = f"Failed to read framework file: {validated_name}"
            raise FrameworkValidationError(msg) from exc

        # Parse the raw text as JSON
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            # Log JSON syntax errors for framework authors to fix
            logger.error(
                "Malformed JSON in framework file",
                extra={"path": str(file_path), "error": str(exc)},
            )
            msg = f"Malformed JSON in framework file: {validated_name}"
            raise FrameworkValidationError(msg) from exc

        # Step 5: Validate with Pydantic model
        # Ensure the JSON structure matches our Framework model schema
        try:
            framework = Framework.model_validate(data)
        except PydanticValidationError as exc:
            # Log validation errors showing which fields failed
            logger.error(
                "Framework data validation failed",
                extra={"path": str(file_path), "errors": str(exc)},
            )
            msg = f"Validation failed for framework: {validated_name}"
            raise FrameworkValidationError(msg) from exc

        # Log successful load with framework metadata
        logger.info(
            "Framework loaded successfully",
            extra={
                "framework": framework.name,
                "version": framework.version,
                "total_controls": framework.total_controls,
            },
        )

        # Return the validated Framework object
        return framework

    def list_available(self) -> list[str]:
        """List all available framework files in the data directory.

        Returns:
            A list of framework names (without file extensions).
        """
        # Check if the frameworks directory exists
        if not self._frameworks_dir.exists():
            # Log warning if directory is missing
            logger.warning("Frameworks directory does not exist")
            return []

        # Walk through directory and collect JSON filenames
        # Filter for .json extension and ensure they're files not directories
        return [
            path.stem  # Get filename without extension
            for path in self._frameworks_dir.iterdir()
            if path.suffix == ".json" and path.is_file()
        ]

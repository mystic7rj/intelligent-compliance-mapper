# -*- coding: utf-8 -*-
"""Core Pydantic models for the Compliance Mapper framework.

Defines the data structures for compliance controls, control families,
and frameworks with full type hints and field validation.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Priority(StrEnum):
    """Priority levels for compliance controls."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Control(BaseModel):
    """A single compliance control within a framework.

    Attributes:
        id: Unique identifier matching pattern like 'ID.AM-1' or 'PR.AC-1'.
        title: Human-readable title of the control.
        description: Detailed description of the control requirements.
        priority: Severity/priority level of the control.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Control identifier (e.g. 'ID.AM-1')",
    )
    # Short human-readable name describing what the control does
    title: str = Field(
        ...,  # Required field
        min_length=1,  # Must contain at least one character
        max_length=200,  # Keep titles concise for display
        description="Human-readable control title",
    )
    # Full explanation of control requirements and implementation guidance
    description: str = Field(
        ...,  # Required field
        min_length=1,  # Must provide description
        max_length=2000,  # Allow detailed explanations
        description="Detailed control description",
    )
    # How urgent it is to implement this control
    priority: Priority = Field(
        default=Priority.MEDIUM,  # Default to medium if not specified
        description="Control priority level",
    )

    @field_validator("id")
    @classmethod
    def validate_control_id(cls, value: str) -> str:
        """Validate that control ID matches expected format.
        
        Takes in the raw control ID string and returns it if valid, or raises
        an exception if the format is incorrect.
        
        Args:
            value: The control ID string to validate.
            
        Returns:
            The validated control ID string unchanged.
            
        Raises:
            ValueError: If the control ID doesn't match the required pattern.
        """
        # Define pattern for control IDs to support multiple formats:
        # 1. NIST CSF format: XX.XX-N (e.g., ID.AM-1)
        # 2. ISO 27001 format: A.N.N (e.g., A.5.1)
        # Requires at least one letter and follows letter/digit separator patterns
        pattern = r"^(?=.*[A-Z])[A-Z0-9]{1,3}(?:\.[A-Z]{0,2})?(?:[\.\-])\d{1,2}(?:[\.\-]\d{1,2})?$"
        
        # SECURITY: Input validation prevents malformed control IDs from
        # entering the system which could cause parsing errors or injection
        if not re.match(pattern, value):
            msg = (
                f"Control ID '{value}' does not match required format "
                f"(e.g. 'ID.AM-1' or 'A.5.1'). Pattern: {pattern}"
            )
            raise ValueError(msg)
        
        # Return validated value for storage
        return value


class ControlFamily(BaseModel):
    """A group of related controls under a framework function.

    Attributes:
        function_name: The high-level function name (e.g. 'Identify', 'Protect').
        function_id: Short identifier for the function (e.g. 'ID', 'PR').
        description: Description of this function area.
        controls: List of controls belonging to this family.
    """

    # Full name of the framework function (e.g., "Identify" or "Protect")
    function_name: str = Field(
        ...,  # Required field
        min_length=1,  # Cannot be empty
        max_length=100,  # Reasonable length for display
        description="Framework function name (e.g. 'Identify')",
    )
    # Short code for the function used in control IDs (e.g., "ID" for Identify)
    function_id: str = Field(
        ...,  # Required field
        min_length=1,  # Must have at least one character
        max_length=10,  # Keep IDs short for prefixing controls
        description="Function short identifier (e.g. 'ID')",
    )
    # Explanation of what this control family covers
    description: str = Field(
        default="",  # Optional field - empty string if not provided
        max_length=1000,  # Allow reasonable explanation length
        description="Description of the control family",
    )
    # List of all controls that belong to this family
    controls: list[Control] = Field(
        default_factory=list,  # Start with empty list if not provided
        description="Controls in this family",
    )


class Framework(BaseModel):
    """A complete compliance framework definition.

    Attributes:
        name: Framework name (e.g. 'NIST CSF').
        version: Framework version string.
        description: Overview of the framework.
        families: List of control families/functions in this framework.
    """

    # Framework identifier like "NIST CSF" or "ISO 27001"
    name: str = Field(
        ...,  # Required field
        min_length=1,  # Cannot be empty
        max_length=100,  # Reasonable length for framework names
        description="Framework name",
    )
    # Version number or year like "2.0" or "2022"
    version: str = Field(
        ...,  # Required field
        min_length=1,  # Must specify version
        max_length=20,  # Allow flexible version formats
        description="Framework version",
    )
    # Overview explaining the purpose and scope of this framework
    description: str = Field(
        default="",  # Optional - empty if not provided
        max_length=2000,  # Allow detailed framework descriptions
        description="Framework description",
    )
    # All control families that make up this framework
    families: list[ControlFamily] = Field(
        default_factory=list,  # Start with empty list if not provided
        description="Control families in this framework",
    )

    @property
    def total_controls(self) -> int:
        """Return total number of controls across all families.
        
        Returns:
            Integer count of all controls summed from all families.
        """
        # Walk through each family and count its controls
        # Sum them all up to get the total for the framework
        return sum(len(family.controls) for family in self.families)

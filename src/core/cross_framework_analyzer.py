"""Cross-framework control mapping and analysis.

Uses ML-based control matching to analyze relationships between different
compliance frameworks, identify gaps, and generate equivalence mappings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from src.core.exceptions import GapAnalysisError, ValidationError
from src.ml.control_matcher import ControlMatch
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.framework_registry import FrameworkRegistry
    from src.ml.control_matcher import ControlMatcher

logger = get_logger(__name__)


class CrossFrameworkResult(BaseModel):
    """Result of a cross-framework mapping analysis.
    
    Immutable result object containing all mapping data between two
    frameworks. The frozen configuration prevents accidental modification
    of analysis results.
    
    Attributes:
        source_framework: Name of the source framework.
        target_framework: Name of the target framework.
        total_source_controls: Total controls in source framework.
        mapped_controls: Number of source controls with at least one match.
        unmapped_controls: Number of source controls with no matches.
        mapping_percentage: Percentage of controls successfully mapped (0.0-100.0).
        matches: List of all control matches found.
        analyzed_at: Timestamp when analysis was performed.
    """
    
    model_config = ConfigDict(frozen=True)
    
    source_framework: str = Field(..., description="Source framework name")
    target_framework: str = Field(..., description="Target framework name")
    total_source_controls: int = Field(..., ge=0, description="Total source controls")
    mapped_controls: int = Field(..., ge=0, description="Successfully mapped controls")
    unmapped_controls: int = Field(..., ge=0, description="Unmapped controls")
    mapping_percentage: float = Field(..., ge=0.0, le=100.0, description="Mapping coverage %")
    matches: list[ControlMatch] = Field(default_factory=list, description="All control matches")
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis timestamp"
    )


class CrossFrameworkAnalyzer:
    """Analyzes control mappings across different compliance frameworks.
    
    Uses ML-based control matching to identify semantic similarities between
    controls from different frameworks. Validates all framework names against
    the registry before processing.
    
    Args:
        matcher: ControlMatcher instance for ML-based similarity detection.
        registry: FrameworkRegistry for validation and metadata.
    """
    
    def __init__(
        self,
        matcher: ControlMatcher,
        registry: FrameworkRegistry,
    ) -> None:
        """Initialize the cross-framework analyzer.
        
        Args:
            matcher: ControlMatcher for finding similar controls.
            registry: FrameworkRegistry for framework validation.
        """
        self._matcher = matcher
        self._registry = registry
        logger.info("CrossFrameworkAnalyzer initialized")
    
    def analyze(self, source: str, target: str) -> CrossFrameworkResult:
        """Perform full ML-based cross-framework mapping analysis.
        
        Compares all controls from the source framework against all controls
        in the target framework using semantic similarity matching. Calculates
        mapping coverage and identifies gaps.
        
        Args:
            source: Source framework identifier (e.g., "nist_csf").
            target: Target framework identifier (e.g., "iso_27001").
        
        Returns:
            CrossFrameworkResult with complete mapping analysis.
        
        Raises:
            ValidationError: If either framework name is invalid.
            GapAnalysisError: If either framework has no controls loaded.
        """
        # Validate both framework names
        logger.info(
            "Starting cross-framework analysis",
            extra={"source": source, "target": target}
        )
        
        try:
            source_meta = self._registry.get(source)
            target_meta = self._registry.get(target)
        except Exception as exc:
            msg = f"Framework validation failed: {exc}"
            logger.error(msg, extra={"source": source, "target": target})
            raise ValidationError(msg) from exc
        
        # Use the matcher to find all control matches
        # This delegates to the ML-based matching logic
        try:
            matches = self._matcher.match_controls(source, target)
        except Exception as exc:
            msg = f"Control matching failed: {exc}"
            logger.error(msg, extra={"source": source, "target": target})
            raise GapAnalysisError(msg) from exc
        
        # Check if frameworks have controls
        if not matches and source_meta.control_count == 0:
            msg = f"Source framework '{source}' has no controls loaded"
            logger.error(msg)
            raise GapAnalysisError(msg)
        
        if not matches and target_meta.control_count == 0:
            msg = f"Target framework '{target}' has no controls loaded"
            logger.error(msg)
            raise GapAnalysisError(msg)
        
        # Calculate mapping statistics
        total_source_controls = source_meta.control_count
        unique_mapped = len(set(match.source_control_id for match in matches))
        unmapped = total_source_controls - unique_mapped
        
        # Calculate mapping percentage
        if total_source_controls > 0:
            percentage = (unique_mapped / total_source_controls) * 100.0
        else:
            percentage = 0.0
        
        # Build and return result
        result = CrossFrameworkResult(
            source_framework=source_meta.name,
            target_framework=target_meta.name,
            total_source_controls=total_source_controls,
            mapped_controls=unique_mapped,
            unmapped_controls=unmapped,
            mapping_percentage=round(percentage, 2),
            matches=matches,
        )
        
        logger.info(
            "Cross-framework analysis complete",
            extra={
                "source": source,
                "target": target,
                "mapped": unique_mapped,
                "total": total_source_controls,
                "percentage": result.mapping_percentage,
            }
        )
        
        return result
    
    def analyze_all_pairs(self) -> list[CrossFrameworkResult]:
        """Analyze all possible framework pairs.
        
        Runs cross-framework analysis for all 6 unique pairs:
        - NIST CSF ↔ ISO 27001
        - NIST CSF ↔ CIS v8
        - NIST CSF ↔ SOC 2
        - ISO 27001 ↔ CIS v8
        - ISO 27001 ↔ SOC 2
        - CIS v8 ↔ SOC 2
        
        Returns:
            List of CrossFrameworkResult, one for each framework pair.
        
        Raises:
            GapAnalysisError: If any framework pair analysis fails.
        """
        # Define all framework pairs to analyze
        framework_pairs = [
            ("nist_csf", "iso_27001"),
            ("nist_csf", "cis_v8"),
            ("nist_csf", "soc2"),
            ("iso_27001", "cis_v8"),
            ("iso_27001", "soc2"),
            ("cis_v8", "soc2"),
        ]
        
        # Run analysis for each pair
        results: list[CrossFrameworkResult] = []
        for source, target in framework_pairs:
            try:
                logger.info(f"Analyzing pair: {source} -> {target}")
                result = self.analyze(source, target)
                results.append(result)
            except Exception as exc:
                msg = f"Failed to analyze {source} -> {target}: {exc}"
                logger.error(msg)
                raise GapAnalysisError(msg) from exc
        
        logger.info(f"All pairs analyzed: {len(results)} results")
        return results
    
    def get_equivalence_map(
        self,
        source: str,
        target: str,
    ) -> dict[str, list[str]]:
        """Generate flat equivalence mapping between frameworks.
        
        Returns a dictionary mapping each source control ID to a list of
        matched target control IDs. Only includes HIGH and MEDIUM confidence
        matches.
        
        Args:
            source: Source framework identifier.
            target: Target framework identifier.
        
        Returns:
            Dictionary mapping source control IDs to lists of target control IDs.
            Example: {"ID.AM-1": ["A5.09-1", "IG.01-1"], "PR.AC-1": ["CC.06-3"]}
        
        Raises:
            ValidationError: If either framework name is invalid.
            GapAnalysisError: If analysis fails.
        """
        # Validate framework names before processing
        logger.info(
            "Building equivalence map",
            extra={"source": source, "target": target}
        )
        
        try:
            self._registry.get(source)
            self._registry.get(target)
        except Exception as exc:
            msg = f"Framework validation failed: {exc}"
            logger.error(msg, extra={"source": source, "target": target})
            raise ValidationError(msg) from exc
        
        # Run the analysis to get all matches
        result = self.analyze(source, target)
        
        # Build equivalence mapping
        equivalence: dict[str, list[str]] = {}
        for match in result.matches:
            # Only include high and medium confidence matches
            if match.confidence in ("HIGH", "MEDIUM"):
                source_id = match.source_control_id
                target_id = match.matched_control_id
                
                # Add to mapping
                if source_id not in equivalence:
                    equivalence[source_id] = []
                equivalence[source_id].append(target_id)
        
        # Sort target IDs within each mapping for consistency
        for source_id in equivalence:
            equivalence[source_id].sort()
        
        logger.info(
            "Equivalence map created",
            extra={
                "source": source,
                "target": target,
                "mapped_controls": len(equivalence),
            }
        )
        
        return equivalence

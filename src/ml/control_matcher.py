"""Cross-framework control matching using ML embeddings.

Orchestrates ``EmbeddingGenerator`` and ``SimilarityCalculator`` to find
semantically similar controls between two compliance frameworks.  All
dependencies are injected via the constructor — no internal imports.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from src.core.exceptions import FrameworkNotFoundError, ValidationError
from src.ml.embeddings import EmbeddingGenerator
from src.ml.similarity import SimilarityCalculator, SimilarityMatch
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — reuse the same whitelist used elsewhere in the project
# ---------------------------------------------------------------------------

ALLOWED_FRAMEWORKS: frozenset[str] = frozenset(
    {"NIST_CSF", "ISO_27001", "CIS_V8", "SOC2"}
)


# ---------------------------------------------------------------------------
# Protocol — what the matcher needs from its data source
# ---------------------------------------------------------------------------


@runtime_checkable
class ControlRepositoryProtocol(Protocol):
    """Minimal interface the matcher expects from a control repository."""

    def get_by_framework(self, framework_id: Any) -> Any: ...


@runtime_checkable
class FrameworkRepositoryProtocol(Protocol):
    """Minimal interface the matcher expects from a framework repository."""

    def get_by_name(self, name: str) -> Any: ...


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ControlMatch(BaseModel):
    """A single cross-framework control match result.

    Attributes:
        source_control_id: Control ID in the source framework.
        source_framework: Name of the source framework.
        matched_control_id: Control ID in the target framework.
        matched_framework: Name of the target framework.
        similarity_score: Cosine / euclidean similarity (0.0–1.0).
        confidence: Confidence bucket derived from the score.
    """

    model_config = ConfigDict(frozen=True)

    source_control_id: str = Field(..., description="Source control identifier")
    source_framework: str = Field(..., description="Source framework name")
    matched_control_id: str = Field(..., description="Matched control identifier")
    matched_framework: str = Field(..., description="Target framework name")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Confidence level"
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _score_to_confidence(score: float) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Map a similarity score to a confidence bucket."""
    if score >= 0.90:
        return "HIGH"
    if score >= 0.75:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Control matcher
# ---------------------------------------------------------------------------


class ControlMatcher:
    """Finds semantically similar controls across compliance frameworks.

    All dependencies are injected via the constructor:
    - ``embedding_generator`` for text-to-vector conversion,
    - ``similarity_calculator`` for vector comparison,
    - ``framework_repository`` for framework look-ups,
    - ``control_repository`` for control look-ups.

    Args:
        embedding_generator: Pre-configured ``EmbeddingGenerator``.
        similarity_calculator: Pre-configured ``SimilarityCalculator``.
        framework_repository: Object satisfying ``FrameworkRepositoryProtocol``.
        control_repository: Object satisfying ``ControlRepositoryProtocol``.
    """

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator,
        similarity_calculator: SimilarityCalculator,
        framework_repository: FrameworkRepositoryProtocol,
        control_repository: ControlRepositoryProtocol,
    ) -> None:
        # Store all injected dependencies
        self._embedder = embedding_generator
        self._similarity = similarity_calculator
        self._framework_repo = framework_repository
        self._control_repo = control_repository

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_framework_name(name: str) -> str:
        """Validate and normalise a framework name against the whitelist."""
        cleaned = name.strip().upper()
        # Reject empty names
        if not cleaned:
            msg = "Framework name cannot be empty"
            raise ValidationError(msg)
        # Reject names not in the allowed set
        if cleaned not in ALLOWED_FRAMEWORKS:
            msg = (
                f"Framework '{cleaned}' is not allowed. "
                f"Allowed: {sorted(ALLOWED_FRAMEWORKS)}"
            )
            raise ValidationError(msg, details={"allowed": sorted(ALLOWED_FRAMEWORKS)})
        return cleaned

    def _fetch_framework(self, name: str) -> Any:
        """Fetch a framework by name, raising FrameworkNotFoundError if absent."""
        framework = self._framework_repo.get_by_name(name)
        if framework is None:
            msg = f"Framework '{name}' not found in the database"
            raise FrameworkNotFoundError(msg)
        return framework

    def _get_controls_for_framework(self, framework: Any) -> list[Any]:
        """Retrieve all controls belonging to a framework via its ID."""
        return self._control_repo.get_by_framework(framework.id)

    @staticmethod
    def _build_control_text(control: Any) -> str:
        """Concatenate control title and description into a single text."""
        title = getattr(control, "title", "")
        description = getattr(control, "description", "")
        # Combine title and description for richer embedding input
        return f"{title} {description}".strip()

    def _build_matches(
        self,
        source_control: Any,
        source_framework: str,
        target_framework: str,
        similar: list[SimilarityMatch],
        target_id_map: dict[str, str],
    ) -> list[ControlMatch]:
        """Convert SimilarityMatch results into ControlMatch objects."""
        matches: list[ControlMatch] = []
        for sim in similar:
            # Map candidate_id back to the actual control_id string
            matched_ctrl_id = target_id_map.get(sim.candidate_id, sim.candidate_id)
            matches.append(
                ControlMatch(
                    source_control_id=source_control.control_id,
                    source_framework=source_framework,
                    matched_control_id=matched_ctrl_id,
                    matched_framework=target_framework,
                    similarity_score=sim.score,
                    confidence=_score_to_confidence(sim.score),
                )
            )
        return matches

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match_control(
        self,
        control_id: str,
        source_framework: str,
        target_framework: str,
    ) -> list[ControlMatch]:
        """Find similar controls in a target framework for one source control.

        Args:
            control_id: The control ID to match (e.g. ``"ID.AM-1"``).
            source_framework: Source framework name (whitelist-validated).
            target_framework: Target framework name (whitelist-validated).

        Returns:
            A list of ``ControlMatch`` results sorted by similarity descending.

        Raises:
            ValidationError: If a framework name is invalid.
            FrameworkNotFoundError: If a framework is not in the database.
        """
        # Validate both framework names against the whitelist
        src_name = self._validate_framework_name(source_framework)
        tgt_name = self._validate_framework_name(target_framework)

        # Fetch frameworks from the repository
        src_fw = self._fetch_framework(src_name)
        tgt_fw = self._fetch_framework(tgt_name)

        # Retrieve controls for both frameworks
        src_controls = self._get_controls_for_framework(src_fw)
        tgt_controls = self._get_controls_for_framework(tgt_fw)

        # Find the source control by its control_id string
        source_ctrl = None
        for ctrl in src_controls:
            if ctrl.control_id == control_id:
                source_ctrl = ctrl
                break

        # Return empty if the requested control_id was not found
        if source_ctrl is None:
            logger.warning(
                "Source control not found",
                extra={"control_id": control_id, "framework": src_name},
            )
            return []

        # Build text representations for the source and target controls
        source_text = self._build_control_text(source_ctrl)
        target_texts = [self._build_control_text(c) for c in tgt_controls]
        target_ids = [str(idx) for idx in range(len(tgt_controls))]

        # Map index-based IDs to real control_id strings
        target_id_map = {str(idx): c.control_id for idx, c in enumerate(tgt_controls)}

        # Generate embeddings for source and all target controls
        source_embedding = self._embedder.generate_single(source_text)
        target_embeddings = self._embedder.generate(target_texts)

        # Find the most similar target controls
        similar = self._similarity.find_similar(
            source_embedding, target_embeddings, target_ids
        )

        # Convert to ControlMatch objects
        matches = self._build_matches(
            source_ctrl, src_name, tgt_name, similar, target_id_map
        )

        logger.info(
            "Control matched",
            extra={
                "source_control": control_id,
                "source_framework": src_name,
                "target_framework": tgt_name,
                "matches_found": len(matches),
            },
        )
        return matches

    def match_framework(
        self,
        source_framework: str,
        target_framework: str,
    ) -> list[ControlMatch]:
        """Match all controls in a source framework against a target framework.

        Args:
            source_framework: Source framework name (whitelist-validated).
            target_framework: Target framework name (whitelist-validated).

        Returns:
            A list of ``ControlMatch`` results for every source control.

        Raises:
            ValidationError: If a framework name is invalid.
            FrameworkNotFoundError: If a framework is not in the database.
        """
        # Validate both framework names
        src_name = self._validate_framework_name(source_framework)
        tgt_name = self._validate_framework_name(target_framework)

        # Fetch frameworks and their controls
        src_fw = self._fetch_framework(src_name)
        tgt_fw = self._fetch_framework(tgt_name)
        src_controls = self._get_controls_for_framework(src_fw)
        tgt_controls = self._get_controls_for_framework(tgt_fw)

        # Pre-compute target embeddings once for all source controls
        target_texts = [self._build_control_text(c) for c in tgt_controls]
        target_ids = [str(idx) for idx in range(len(tgt_controls))]
        target_id_map = {str(idx): c.control_id for idx, c in enumerate(tgt_controls)}
        target_embeddings = self._embedder.generate(target_texts)

        all_matches: list[ControlMatch] = []

        # Iterate over each source control and find its best matches
        for ctrl in src_controls:
            source_text = self._build_control_text(ctrl)
            source_embedding = self._embedder.generate_single(source_text)

            similar = self._similarity.find_similar(
                source_embedding, target_embeddings, target_ids
            )

            matches = self._build_matches(
                ctrl, src_name, tgt_name, similar, target_id_map
            )
            all_matches.extend(matches)

        logger.info(
            "Framework matching complete",
            extra={
                "source_framework": src_name,
                "target_framework": tgt_name,
                "source_controls": len(src_controls),
                "total_matches": len(all_matches),
            },
        )
        return all_matches

    def get_coverage_report(
        self,
        source_framework: str,
        target_framework: str,
    ) -> dict:
        """Generate a coverage summary for cross-framework matching.

        Args:
            source_framework: Source framework name (whitelist-validated).
            target_framework: Target framework name (whitelist-validated).

        Returns:
            A dict with keys: ``total_source_controls``, ``matched_count``,
            ``unmatched_count``, ``average_similarity``, and
            ``matches_by_confidence``.

        Raises:
            ValidationError: If a framework name is invalid.
            FrameworkNotFoundError: If a framework is not in the database.
        """
        # Get all matches for the framework pair
        all_matches = self.match_framework(source_framework, target_framework)

        # Validate to get cleaned names for control counting
        src_name = self._validate_framework_name(source_framework)
        src_fw = self._fetch_framework(src_name)
        src_controls = self._get_controls_for_framework(src_fw)
        total_source = len(src_controls)

        # Determine which source controls got at least one match
        matched_source_ids: set[str] = {m.source_control_id for m in all_matches}
        matched_count = len(matched_source_ids)
        unmatched_count = total_source - matched_count

        # Compute average similarity across all matches
        avg_similarity = 0.0
        if all_matches:
            avg_similarity = round(
                sum(m.similarity_score for m in all_matches) / len(all_matches), 4
            )

        # Count matches by confidence level
        confidence_counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for match in all_matches:
            confidence_counts[match.confidence] += 1

        report = {
            "total_source_controls": total_source,
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "average_similarity": avg_similarity,
            "matches_by_confidence": confidence_counts,
        }

        logger.info(
            "Coverage report generated",
            extra={
                "source_framework": src_name,
                "total": total_source,
                "matched": matched_count,
            },
        )
        return report

# -*- coding: utf-8 -*-
"""Similarity calculation engine for embedding vectors.

Supports cosine and Euclidean distance metrics.  Returns ranked
``SimilarityMatch`` results filtered by a configurable threshold
and top-k limit.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration and result models
# ---------------------------------------------------------------------------


class SimilarityConfig(BaseModel):
    """Configuration for the similarity calculator.

    Attributes:
        threshold: Minimum similarity score to include a result (0.0–1.0).
        top_k: Maximum number of results to return.
        metric: Distance metric — ``"cosine"`` or ``"euclidean"``.
    """

    model_config = ConfigDict(frozen=True)

    threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Max results to return",
    )
    metric: Literal["cosine", "euclidean"] = Field(
        default="cosine",
        description="Distance metric",
    )


class SimilarityMatch(BaseModel):
    """A single similarity match result.

    Attributes:
        candidate_id: Identifier of the matched candidate.
        score: Similarity score between 0.0 and 1.0.
        rank: 1-based rank among returned results.
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., description="Matched candidate identifier")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    rank: int = Field(..., ge=1, description="1-based rank")


# ---------------------------------------------------------------------------
# Similarity calculator
# ---------------------------------------------------------------------------


class SimilarityCalculator:
    """Calculates similarity between embedding vectors.

    Uses either cosine similarity or Euclidean-distance-based similarity
    depending on the configured metric.

    Args:
        config: A ``SimilarityConfig`` controlling threshold, top_k, and metric.
    """

    def __init__(self, config: SimilarityConfig) -> None:
        # Store config for threshold, top_k, and metric selection
        self._config: SimilarityConfig = config

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_similarity(
        self,
        embedding_a: np.ndarray,
        embedding_b: np.ndarray,
    ) -> float:
        """Compute pairwise similarity between two 1-D or 2-D arrays.

        Returns a float clamped to [0.0, 1.0].
        """
        # Reshape to 2-D if needed for sklearn functions
        a = embedding_a.reshape(1, -1)
        b = embedding_b.reshape(1, -1)

        if self._config.metric == "cosine":
            # Cosine similarity returns values in [-1, 1]; clamp to [0, 1]
            raw_score: float = float(cosine_similarity(a, b)[0][0])
            return max(0.0, min(1.0, raw_score))

        # Euclidean: convert distance to similarity via 1 / (1 + distance)
        distance: float = float(euclidean_distances(a, b)[0][0])
        return 1.0 / (1.0 + distance)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(
        self,
        embedding_a: np.ndarray,
        embedding_b: np.ndarray,
    ) -> float:
        """Calculate similarity score between two embeddings.

        Args:
            embedding_a: First embedding vector.
            embedding_b: Second embedding vector.

        Returns:
            A float between 0.0 and 1.0.
        """
        # Delegate to the internal similarity computation
        score = self._compute_similarity(embedding_a, embedding_b)

        logger.debug(
            "Similarity calculated",
            extra={"metric": self._config.metric, "score": round(score, 4)},
        )
        return score

    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        candidate_ids: list[str],
    ) -> list[SimilarityMatch]:
        """Find the top-k most similar candidates above the threshold.

        Args:
            query_embedding: 1-D embedding of the query control.
            candidate_embeddings: 2-D array of candidate embeddings.
            candidate_ids: Identifiers corresponding to each row of
                ``candidate_embeddings``.

        Returns:
            A list of ``SimilarityMatch`` objects sorted by score descending.
        """
        scored: list[tuple[str, float]] = []

        # Compute similarity for every candidate
        for idx, cid in enumerate(candidate_ids):
            score = self._compute_similarity(query_embedding, candidate_embeddings[idx])
            # Filter out candidates below the threshold
            if score >= self._config.threshold:
                scored.append((cid, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Limit to top_k results
        top_results = scored[: self._config.top_k]

        # Build ranked SimilarityMatch list (rank starts at 1)
        matches: list[SimilarityMatch] = [
            SimilarityMatch(candidate_id=cid, score=round(s, 6), rank=rank)
            for rank, (cid, s) in enumerate(top_results, start=1)
        ]

        logger.info(
            "Similar candidates found",
            extra={
                "total_candidates": len(candidate_ids),
                "above_threshold": len(scored),
                "returned": len(matches),
            },
        )
        return matches

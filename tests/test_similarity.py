"""Tests for SimilarityCalculator — math correctness with real numpy arrays.

No mocking is needed here; the tests exercise actual cosine and Euclidean
similarity computations on small vectors.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.ml.similarity import SimilarityCalculator, SimilarityConfig, SimilarityMatch


# ---------------------------------------------------------------------------
# Tests — cosine metric (default)
# ---------------------------------------------------------------------------


class TestCosineCalculate:
    """Tests for the calculate() method using cosine similarity."""

    # Test: identical embeddings return similarity score of 1.0
    def test_identical_embeddings(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig())
        vec = np.array([1.0, 2.0, 3.0])

        score = calc.calculate(vec, vec)

        assert score == pytest.approx(1.0, abs=1e-6)

    # Test: opposite embeddings return similarity score of 0.0
    def test_opposite_embeddings(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig())
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([-1.0, 0.0, 0.0])

        score = calc.calculate(vec_a, vec_b)

        # Cosine similarity of opposite vectors is -1, clamped to 0.0
        assert score == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Tests — find_similar
# ---------------------------------------------------------------------------


class TestFindSimilar:
    """Tests for find_similar() ranking, filtering, and limiting."""

    # Test: find_similar() returns results sorted by score descending
    def test_results_sorted_descending(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig(threshold=0.0, top_k=10))
        query = np.array([1.0, 0.0, 0.0])
        candidates = np.array([
            [0.5, 0.5, 0.0],   # moderate similarity
            [1.0, 0.0, 0.0],   # perfect match
            [0.0, 1.0, 0.0],   # orthogonal
        ])
        ids = ["A", "B", "C"]

        matches = calc.find_similar(query, candidates, ids)

        # Scores should be in descending order
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    # Test: results below threshold are excluded
    def test_threshold_filtering(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig(threshold=0.9, top_k=10))
        query = np.array([1.0, 0.0, 0.0])
        candidates = np.array([
            [1.0, 0.0, 0.0],   # score ≈ 1.0 — above threshold
            [0.5, 0.5, 0.0],   # score ≈ 0.707 — below threshold
            [0.0, 1.0, 0.0],   # score ≈ 0.0 — below threshold
        ])
        ids = ["A", "B", "C"]

        matches = calc.find_similar(query, candidates, ids)

        # Only the perfect match should survive at threshold 0.9
        assert len(matches) == 1
        assert matches[0].candidate_id == "A"

    # Test: top_k limits number of results returned
    def test_top_k_limit(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig(threshold=0.0, top_k=2))
        query = np.array([1.0, 0.0, 0.0])
        candidates = np.array([
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.8, 0.2, 0.0],
            [0.7, 0.3, 0.0],
        ])
        ids = ["A", "B", "C", "D"]

        matches = calc.find_similar(query, candidates, ids)

        # Only top 2 should be returned
        assert len(matches) == 2

    # Test: SimilarityMatch rank starts at 1
    def test_rank_starts_at_one(self) -> None:
        calc = SimilarityCalculator(config=SimilarityConfig(threshold=0.0, top_k=5))
        query = np.array([1.0, 0.0, 0.0])
        candidates = np.array([
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
        ])
        ids = ["A", "B"]

        matches = calc.find_similar(query, candidates, ids)

        # First result should have rank 1
        assert matches[0].rank == 1
        assert matches[1].rank == 2


# ---------------------------------------------------------------------------
# Tests — euclidean metric
# ---------------------------------------------------------------------------


class TestEuclideanMetric:
    """Tests for the Euclidean distance-based similarity."""

    # Test: euclidean metric returns score between 0.0 and 1.0
    def test_euclidean_score_range(self) -> None:
        calc = SimilarityCalculator(
            config=SimilarityConfig(metric="euclidean", threshold=0.0)
        )
        vec_a = np.array([1.0, 2.0, 3.0])
        vec_b = np.array([4.0, 5.0, 6.0])

        score = calc.calculate(vec_a, vec_b)

        # Score must be between 0.0 and 1.0 (inclusive)
        assert 0.0 <= score <= 1.0

    # Test: identical vectors produce euclidean similarity of 1.0
    def test_euclidean_identical(self) -> None:
        calc = SimilarityCalculator(
            config=SimilarityConfig(metric="euclidean")
        )
        vec = np.array([1.0, 2.0, 3.0])

        score = calc.calculate(vec, vec)

        # distance = 0 → similarity = 1 / (1 + 0) = 1.0
        assert score == pytest.approx(1.0, abs=1e-6)

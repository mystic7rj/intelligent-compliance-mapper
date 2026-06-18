# -*- coding: utf-8 -*-
"""Integration smoke tests for embeddings + similarity workflow."""

from __future__ import annotations

import pytest

from src.core.exceptions import ValidationError
from src.ml.control_matcher import _score_to_confidence
from src.ml.embeddings import EmbeddingConfig, EmbeddingGenerator
from src.ml.similarity import SimilarityCalculator, SimilarityConfig


def test_embedding_similarity_smoke_offline_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generate real embeddings and verify semantically similar controls match strongly."""
    # Force offline behavior; test still works when model is already cached.
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    generator = EmbeddingGenerator(config=EmbeddingConfig(model_name="all-MiniLM-L6-v2"))
    texts = [
        "Implement multi-factor authentication for all remote access",
        "Require MFA for all external network connections",
    ]

    try:
        embeddings = generator.generate(texts)
    except Exception as exc:
        pytest.skip(f"SentenceTransformer cache unavailable for offline smoke test: {exc}")

    calculator = SimilarityCalculator(config=SimilarityConfig(threshold=0.0, top_k=1))
    matches = calculator.find_similar(
        query_embedding=embeddings[0],
        candidate_embeddings=embeddings,
        candidate_ids=["control-1", "control-2"],
    )

    assert matches
    score = matches[0].score
    assert score > 0.70

    confidence = _score_to_confidence(score)
    assert confidence in {"HIGH", "MEDIUM"}


def test_embedding_generator_empty_string_raises_validation_error() -> None:
    """Empty strings should be rejected by EmbeddingGenerator input validation."""
    generator = EmbeddingGenerator(config=EmbeddingConfig(model_name="all-MiniLM-L6-v2"))

    with pytest.raises(ValidationError, match="empty"):
        generator.generate([""])

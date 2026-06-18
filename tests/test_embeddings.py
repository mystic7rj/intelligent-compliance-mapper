# -*- coding: utf-8 -*-
"""Tests for EmbeddingGenerator — validation, caching, and shape checks.

SentenceTransformer is mocked via ``unittest.mock.patch`` so no real ML
model is downloaded during testing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.exceptions import ValidationError
from src.ml.embeddings import EmbeddingConfig, EmbeddingGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Embedding dimension used across all mock returns
_MOCK_DIM = 384


def _make_mock_model(dim: int = _MOCK_DIM) -> MagicMock:
    """Create a MagicMock that behaves like SentenceTransformer."""
    mock_model = MagicMock()
    # encode() returns a numpy array whose first axis matches input length
    mock_model.encode.side_effect = lambda texts, **kw: np.random.default_rng(42).random(
        (len(texts), dim)
    )
    # get_sentence_embedding_dimension() returns the fixed dim
    mock_model.get_sentence_embedding_dimension.return_value = dim
    return mock_model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerate:
    """Tests for the generate() batch method."""

    # Test: generate() returns numpy array with correct shape
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_returns_correct_shape(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        result = gen.generate(["hello", "world"])

        assert isinstance(result, np.ndarray)
        assert result.shape == (2, _MOCK_DIM)

    # Test: generate() with batch of 5 texts returns array of shape (5, dim)
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_batch_of_five(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        texts = ["text one", "text two", "text three", "text four", "text five"]
        result = gen.generate(texts)

        assert result.shape == (5, _MOCK_DIM)


class TestGenerateSingle:
    """Tests for the generate_single() method."""

    # Test: generate_single() returns 1D numpy array
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_returns_1d_array(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        result = gen.generate_single("hello world")

        assert isinstance(result, np.ndarray)
        assert result.ndim == 1
        assert result.shape == (_MOCK_DIM,)


class TestInputValidation:
    """Tests for empty / whitespace-only input rejection."""

    # Test: empty string input raises ValidationError
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_empty_string_raises(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        with pytest.raises(ValidationError, match="empty"):
            gen.generate([""])

    # Test: whitespace-only string raises ValidationError
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_whitespace_only_raises(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        with pytest.raises(ValidationError, match="empty"):
            gen.generate(["   "])


class TestModelCaching:
    """Tests for lazy model loading and caching."""

    # Test: model is cached after first call — SentenceTransformer constructor called only once
    @patch("src.ml.embeddings.SentenceTransformer")
    def test_model_loaded_once(self, mock_st_cls: MagicMock) -> None:
        mock_st_cls.return_value = _make_mock_model()
        gen = EmbeddingGenerator(config=EmbeddingConfig())

        # Call generate twice
        gen.generate(["first call"])
        gen.generate(["second call"])

        # SentenceTransformer constructor should be called exactly once
        assert mock_st_cls.call_count == 1

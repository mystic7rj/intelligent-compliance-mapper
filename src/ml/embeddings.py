"""Sentence-transformer embedding generator for compliance control texts.

Wraps ``sentence_transformers.SentenceTransformer`` behind a thin interface
with input validation, model caching, and batch encoding support.  The
underlying model is loaded lazily on the first call and reused thereafter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sentence_transformers import SentenceTransformer

from src.core.exceptions import ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------


class EmbeddingConfig(BaseModel):
    """Configuration for the embedding generator.

    Attributes:
        model_name: HuggingFace model identifier for sentence-transformers.
        batch_size: Number of texts to encode per batch (1–512).
        cache_dir: Optional local directory for cached model weights.
        normalize_embeddings: Whether to L2-normalize output vectors.
    """

    model_config = ConfigDict(frozen=True)

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformer model name",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
        description="Encoding batch size",
    )
    cache_dir: Optional[Path] = Field(
        default=None,
        description="Local cache directory for model weights",
    )
    normalize_embeddings: bool = Field(
        default=True,
        description="L2-normalize output embeddings",
    )


# ---------------------------------------------------------------------------
# Embedding generator
# ---------------------------------------------------------------------------


class EmbeddingGenerator:
    """Generates sentence embeddings using a cached SentenceTransformer model.

    The model is loaded lazily on the first ``generate`` / ``generate_single``
    call and is never reloaded afterwards.

    Args:
        config: An ``EmbeddingConfig`` instance controlling model and batching.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        # Store config and initialise the model slot to None (lazy loading)
        self._config: EmbeddingConfig = config
        self._model: SentenceTransformer | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_model(self) -> SentenceTransformer:
        """Return the cached model, loading it on first access."""
        if self._model is None:
            # Load model once and cache for all subsequent calls
            logger.info(
                "Loading SentenceTransformer model",
                extra={"model_name": self._config.model_name},
            )
            self._model = SentenceTransformer(
                self._config.model_name,
                cache_folder=str(self._config.cache_dir) if self._config.cache_dir else None,
            )
        return self._model

    @staticmethod
    def _validate_texts(texts: list[str]) -> list[str]:
        """Strip whitespace from each text and reject empty strings."""
        cleaned: list[str] = []
        for text in texts:
            stripped = text.strip()
            # Raise immediately if any text is empty after stripping
            if not stripped:
                msg = "Input text must not be empty or whitespace-only"
                raise ValidationError(msg)
            cleaned.append(stripped)
        return cleaned

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: Non-empty strings to encode.

        Returns:
            A numpy array of shape ``(len(texts), embedding_dim)``.

        Raises:
            ValidationError: If any text is empty after stripping.
        """
        # Validate and clean all input texts
        cleaned = self._validate_texts(texts)

        # Encode using the cached model
        model = self._get_model()
        embeddings: np.ndarray = model.encode(
            cleaned,
            batch_size=self._config.batch_size,
            normalize_embeddings=self._config.normalize_embeddings,
            show_progress_bar=False,
        )

        logger.info(
            "Embeddings generated",
            extra={"count": len(cleaned), "dim": embeddings.shape[1]},
        )
        return embeddings

    def generate_single(self, text: str) -> np.ndarray:
        """Generate an embedding for a single text.

        Args:
            text: A non-empty string to encode.

        Returns:
            A 1-D numpy array of shape ``(embedding_dim,)``.

        Raises:
            ValidationError: If text is empty after stripping.
        """
        # Delegate to generate() and flatten to 1-D
        result = self.generate([text])
        return result[0]

    def get_embedding_dim(self) -> int:
        """Return the dimensionality of embeddings for the configured model."""
        # Access the model's internal dimension attribute
        model = self._get_model()
        dim: int = model.get_sentence_embedding_dimension()
        return dim

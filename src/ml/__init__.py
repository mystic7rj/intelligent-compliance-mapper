# -*- coding: utf-8 -*-
"""ML sub-package — sentence-transformer-based control similarity engine.

Exports embedding generation, similarity calculation, and control matching
classes for cross-framework compliance control mapping.
"""

from __future__ import annotations

from src.ml.control_matcher import ControlMatch, ControlMatcher
from src.ml.embeddings import EmbeddingConfig, EmbeddingGenerator
from src.ml.similarity import SimilarityCalculator, SimilarityConfig, SimilarityMatch

__all__ = [
    "ControlMatch",
    "ControlMatcher",
    "EmbeddingConfig",
    "EmbeddingGenerator",
    "SimilarityCalculator",
    "SimilarityConfig",
    "SimilarityMatch",
]

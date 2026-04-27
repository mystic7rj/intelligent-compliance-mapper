"""Abstract base class for all report generators.

Provides shared validation (``validate_output_path``) and sanitisation
(``sanitize_text``) logic.  Subclasses must implement ``generate()``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from markupsafe import escape

from src.core.gap_analyzer import GapAnalysisResult
from src.core.risk_scorer import RiskReport
from src.utils.logger import get_logger
from src.utils.security import SecurityError, safe_path

logger = get_logger(__name__)


class BaseReporter(ABC):
    """Abstract reporter that all format-specific reporters inherit from.

    Provides:
        - ``validate_output_path`` — security-checked path resolution.
        - ``sanitize_text`` — HTML-escape any user-facing string.

    Subclasses must implement ``generate()``.
    """

    # ------------------------------------------------------------------
    # Abstract API
    # ------------------------------------------------------------------

    @abstractmethod
    def generate(
        self,
        gap_result: GapAnalysisResult,
        risk_report: RiskReport,
        output_path: Path,
    ) -> Path:
        """Generate a report file and return the written path.

        Args:
            gap_result: Result of a gap analysis run.
            risk_report: Risk scoring report for the same analysis.
            output_path: Directory where the report file should be written.

        Returns:
            Absolute ``Path`` to the generated report file.
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_output_path(output_path: Path) -> Path:
        """Resolve and validate *output_path*, creating parents if needed.

        Delegates to ``safe_path()`` to prevent directory traversal.
        When *output_path* is already absolute the base directory for the
        safety check is the path itself (resolved), which still catches
        embedded ``..`` segments.  Relative paths are resolved against
        ``Path.cwd()``.

        Args:
            output_path: User-supplied output directory path.

        Returns:
            Resolved, validated ``Path``.

        Raises:
            SecurityError: If the path contains traversal attempts.
        """
        # Determine the appropriate base for safe_path
        if output_path.is_absolute():
            base_dir = output_path.resolve()
        else:
            base_dir = Path.cwd()

        try:
            validated = safe_path(base_dir, output_path)
        except SecurityError:
            logger.warning(
                "Output path failed security validation",
                extra={"output_path": str(output_path)},
            )
            raise

        # Create parent directories if they do not exist
        validated.mkdir(parents=True, exist_ok=True)
        logger.debug(
            "Output path validated",
            extra={"validated_path": str(validated)},
        )
        return validated

    @staticmethod
    def sanitize_text(text: str) -> str:
        """HTML-escape a string to prevent XSS in rendered templates.

        Uses ``markupsafe.escape()`` which converts ``<``, ``>``, ``&``,
        ``"`` and ``'`` to their HTML entity equivalents.

        Args:
            text: Raw text to sanitise.

        Returns:
            Escaped text safe for HTML embedding.
        """
        return str(escape(text))

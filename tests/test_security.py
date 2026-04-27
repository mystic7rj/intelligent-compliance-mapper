"""Tests for the security module — safe_path traversal protection."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.security import SecurityError, safe_path


class TestSafePath:
    """Tests for the safe_path() function."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        """A simple relative path within base_dir should resolve correctly."""
        target = tmp_path / "file.txt"
        target.touch()
        result = safe_path(tmp_path, "file.txt")
        assert result == target.resolve()

    def test_valid_subdirectory_path(self, tmp_path: Path) -> None:
        """Nested relative paths within base_dir should resolve correctly."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        target = subdir / "data.json"
        target.touch()
        result = safe_path(tmp_path, "sub/data.json")
        assert result == target.resolve()

    def test_dotdot_traversal_raises_security_error(self, tmp_path: Path) -> None:
        """Paths with '..' should be rejected immediately."""
        with pytest.raises(SecurityError, match="traversal"):
            safe_path(tmp_path, "../etc/passwd")

    def test_embedded_dotdot_traversal_raises_security_error(self, tmp_path: Path) -> None:
        """Embedded '..' components should also be caught."""
        with pytest.raises(SecurityError, match="traversal"):
            safe_path(tmp_path, "data/../../secret")

    def test_null_byte_raises_security_error(self, tmp_path: Path) -> None:
        """Paths containing null bytes should be rejected."""
        with pytest.raises(SecurityError, match="null bytes"):
            safe_path(tmp_path, "file.txt\x00.jpg")

    def test_resolved_path_stays_within_base(self, tmp_path: Path) -> None:
        """The resolved result must be inside the base_dir."""
        result = safe_path(tmp_path, "frameworks/nist_csf.json")
        resolved_base = tmp_path.resolve()
        assert str(result).startswith(str(resolved_base))

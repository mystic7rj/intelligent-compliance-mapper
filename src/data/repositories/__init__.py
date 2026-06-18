# -*- coding: utf-8 -*-
"""Repository sub-package — data-access-only classes for ORM entities."""

from __future__ import annotations

from src.data.repositories.control_repository import ControlRepository
from src.data.repositories.framework_repository import FrameworkRepository

__all__ = [
    "ControlRepository",
    "FrameworkRepository",
]

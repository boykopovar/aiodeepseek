from __future__ import annotations

from enum import Enum


class ModelType(str, Enum):
    DEFAULT = "default"
    EXPERT = "expert"
    VISION = "vision"

    def __str__(self) -> str:
        return self.value
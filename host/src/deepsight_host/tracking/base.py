from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TrackingResult:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized 0-1)
    center_x: float
    center_y: float
    confidence: float
    track_id: int
    visible: bool
    lost: bool
    mask: Any | None = None
    pose_landmarks: list | None = None


class TrackingEngine(ABC):
    @abstractmethod
    def process_frame(self, frame: Any) -> TrackingResult:
        ...

    @abstractmethod
    def reset(self):
        ...

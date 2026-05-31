"""FileVideoSource — plays a video file for mock testing."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger("host.video.file")


class FileVideoSource:
    def __init__(self, file_path: str, fps: int = 30, loop: bool = True):
        import cv2

        self._path = Path(file_path)
        if not self._path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video: {file_path}")

        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._source_fps = self._cap.get(cv2.CAP_PROP_FPS) or fps
        self.fps = self._source_fps
        self._loop = loop
        self._frame_count = 0

        logger.info("FileVideoSource: %s (%dx%d @ %.1ffps)",
                     self._path.name, self.width, self.height, self._source_fps)

    def read(self) -> np.ndarray | None:
        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None

        self._frame_count += 1
        return frame

    def frame_age_ms(self) -> float:
        return 0.0

    def stale(self, threshold: float = 3.0) -> bool:
        return False

    def close(self):
        if self._cap:
            self._cap.release()
            self._cap = None

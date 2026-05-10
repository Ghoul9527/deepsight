"""Mock video source — generates synthetic test patterns with moving target."""

from __future__ import annotations

import logging
import math
import time

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger("host.video.mock")


class MockVideoSource:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._frame_count = 0
        self._start_time = time.monotonic()
        self._actual_fps = 0.0

    def read(self) -> np.ndarray | None:
        elapsed = time.monotonic() - self._start_time
        expected_frame = int(elapsed * self.fps)
        if expected_frame <= self._frame_count:
            return None
        self._frame_count = expected_frame

        if elapsed > 0:
            self._actual_fps = self._frame_count / elapsed

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Blue water gradient
        for y in range(self.height):
            intensity = int(80 + 40 * (1 - y / self.height))
            frame[y, :] = [intensity, int(intensity * 0.6), 180 + int(40 * y / self.height)]

        # Grid lines for reference
        for i in range(0, self.width, 160):
            frame[:, i:i + 1] = [60, 40, 140]
        for i in range(0, self.height, 90):
            frame[i:i + 1, :] = [60, 40, 140]

        # Crosshair at center
        cx, cy = self.width // 2, self.height // 2
        frame[cy - 20:cy + 20, cx - 1:cx + 2] = [255, 255, 255]
        frame[cy - 1:cy + 2, cx - 20:cx + 20] = [255, 255, 255]
        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), 2)

        # Moving target (simulated freediver)
        t = elapsed
        tx = int(cx + 200 * math.sin(t * 0.5))
        ty = int(cy + 150 * math.cos(t * 0.3))
        cv2.circle(frame, (tx, ty), 30, (0, 255, 255), 2)
        cv2.circle(frame, (tx, ty), 3, (0, 255, 255), -1)

        # Target label
        bbox_size = 60
        x1, y1 = tx - bbox_size // 2, ty - bbox_size // 2
        x2, y2 = tx + bbox_size // 2, ty + bbox_size // 2
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Resolution + FPS overlay (top-left)
        cv2.putText(frame, f"{self.width}x{self.height} @ {self._actual_fps:.0f}fps",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "MOCK",
                    (10, self.height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2)

        return frame

    @property
    def actual_fps(self) -> float:
        return self._actual_fps

    def close(self):
        pass

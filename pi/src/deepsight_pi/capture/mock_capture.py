from __future__ import annotations

import logging
import time

import numpy as np

from deepsight_pi.capture.base import CaptureDevice

logger = logging.getLogger("pi.capture.mock")


class MockCapture(CaptureDevice):
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 60):
        self.width = width
        self.height = height
        self.fps = fps
        self._running = False
        self._frame_count = 0
        self._start_time = 0.0

    async def start(self) -> bool:
        logger.debug("[MOCK] HDMI capture started")
        self._running = True
        self._start_time = time.monotonic()
        return True

    async def stop(self) -> bool:
        logger.debug("[MOCK] HDMI capture stopped")
        self._running = False
        return True

    async def read_frame(self) -> np.ndarray | None:
        if not self._running:
            return None
        # Generate test pattern
        self._frame_count += 1
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Color bars
        w = self.width // 7
        colors = [(255, 255, 255), (255, 255, 0), (0, 255, 255),
                   (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255)]
        for i, color in enumerate(colors):
            frame[:, i * w:(i + 1) * w] = color

        try:
            import cv2
            cv2.putText(frame, "MOCK HDMI CAPTURE",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1.5, (0, 0, 0), 3)
        except Exception:
            pass

        return frame

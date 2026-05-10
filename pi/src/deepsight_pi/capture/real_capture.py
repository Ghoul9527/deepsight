"""Real HDMI capture via V4L2 + OpenCV.

Captures frames from a USB HDMI capture dongle (e.g., Elgato Cam Link,
no-name UVC device) exposed as a V4L2 device at /dev/videoX.
"""

from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from deepsight_pi.capture.base import CaptureDevice

logger = logging.getLogger("pi.capture.real")


class RealCapture(CaptureDevice):
    """Captures frames from /dev/video0 (USB HDMI dongle) using OpenCV."""

    def __init__(self, device: str = "/dev/video0", width: int = 1920,
                 height: int = 1080, fps: int = 60):
        self._device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._running = False
        self._frame_count = 0
        self._last_frame: np.ndarray | None = None

    async def start(self) -> bool:
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed — cannot capture HDMI")
            return False

        self._cap = cv2.VideoCapture(self._device)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        if not self._cap.isOpened():
            logger.error("Failed to open capture device: %s", self._device)
            return False

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        logger.info("HDMI capture started: %dx%d @ %.1f fps (%s)",
                     actual_w, actual_h, actual_fps, self._device)
        self._running = True
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("HDMI capture stopped")
        return True

    async def read_frame(self) -> np.ndarray | None:
        if not self._running or self._cap is None:
            return None

        # OpenCV read() is blocking — run in thread
        loop = asyncio.get_event_loop()
        ret, frame = await loop.run_in_executor(None, self._cap.read)

        if not ret or frame is None:
            logger.warning("HDMI capture read failure")
            return self._last_frame

        self._frame_count += 1
        self._last_frame = frame
        return frame

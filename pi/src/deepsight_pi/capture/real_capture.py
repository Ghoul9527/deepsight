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

RECONNECT_DELAY = 1.0
MAX_FAILURES = 5
READ_TIMEOUT = 3.0  # seconds


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
        self._failures = 0
        self._last_frame: np.ndarray | None = None
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._last_reconnect_time = 0.0

    async def start(self) -> bool:
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed — cannot capture HDMI")
            return False

        self._cv2 = cv2
        self._running = True
        self._disable_usb_autosuspend()
        return self._open_device()

    def _disable_usb_autosuspend(self):
        """Disable USB autosuspend for the capture device to prevent
        periodic 5-minute timeouts caused by USB power management."""
        import glob
        # The capture device is at a specific V4L2 path; find its USB device
        v4l_path = self._device
        # Resolve symlink to get actual device node
        try:
            import os
            real_path = os.path.realpath(v4l_path)
            # Extract USB device from sysfs: /sys/class/video4linux/videoX/device
            video_name = os.path.basename(real_path)  # e.g. "video0"
            power_control = f"/sys/class/video4linux/{video_name}/device/power/control"
            if os.path.exists(power_control):
                with open(power_control, "w") as f:
                    f.write("on")
                logger.info("USB autosuspend disabled for %s", v4l_path)
        except (OSError, PermissionError) as e:
            logger.debug("Could not disable USB autosuspend: %s", e)

    def _open_device(self) -> bool:
        cv2 = self._cv2
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        cap = cv2.VideoCapture(self._device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        if not cap.isOpened():
            logger.error("Failed to open capture device: %s", self._device)
            return False

        self._cap = cap
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        self._failures = 0

        logger.info("HDMI capture started: %dx%d @ %.1f fps (%s)",
                     actual_w, actual_h, actual_fps, self._device)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("HDMI capture stopped")
        return True

    async def read_frame(self) -> np.ndarray | None:
        if not self._running:
            return None

        if self._cap is None or self._reconnecting:
            await asyncio.sleep(0.001)
            return self._last_frame

        # OpenCV read() is blocking — run in thread with timeout
        loop = asyncio.get_event_loop()
        try:
            ret, frame = await asyncio.wait_for(
                loop.run_in_executor(None, self._cap.read),
                timeout=READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("HDMI capture read timed out (%.1fs), reconnecting...",
                           READ_TIMEOUT)
            # Reconnect in background to avoid blocking the video loop
            asyncio.create_task(self._reconnect_async())
            return self._last_frame

        if not ret or frame is None:
            self._failures += 1
            logger.debug("HDMI capture read failed (%d/%d): ret=%s",
                         self._failures, MAX_FAILURES, ret)
            if self._failures >= MAX_FAILURES:
                logger.warning("HDMI capture lost (%d failures), reconnecting...",
                               self._failures)
                asyncio.create_task(self._reconnect_async())
            return self._last_frame

        self._failures = 0
        self._frame_count += 1
        self._last_frame = frame
        return frame

    async def _reconnect_async(self):
        """Reopen capture device with exponential backoff."""
        if self._reconnecting:
            return
        self._reconnecting = True
        try:
            while self._running:
                self._reconnect_attempts += 1
                delay = min(1.0 * (2 ** min(self._reconnect_attempts - 1, 4)),
                            RECONNECT_DELAY * 10)
                await asyncio.sleep(delay)
                if self._open_device():
                    self._reconnect_attempts = 0
                    self._last_reconnect_time = time.time()
                    logger.info("HDMI capture reconnected successfully")
                    break
                logger.debug("HDMI capture reconnect attempt %d failed, retrying in %.1fs",
                             self._reconnect_attempts, delay)
        finally:
            self._reconnecting = False

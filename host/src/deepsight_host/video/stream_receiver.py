"""Receives video stream from Raspberry Pi.

Supports MJPEG-over-HTTP, RTSP, and TCP MPEG-TS via OpenCV.
Falls back to a mock frame generator when no stream source is available.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

import numpy as np

logger = logging.getLogger("host.video.receiver")

BUFFER_SIZE = 65536


class StreamReceiver:
    """Async video stream receiver.

    Usage:
        receiver = StreamReceiver("http://192.168.1.100:8080/stream")
        receiver.set_frame_callback(lambda frame: display(frame))
        await receiver.start()
        ...
        await receiver.stop()
    """

    def __init__(self, url: str = "http://127.0.0.1:8080/stream"):
        self._url = url
        self._callback: Callable[[np.ndarray], None] | None = None
        self._connected = False
        self._task: asyncio.Task | None = None
        self._mock = False
        self._latest_frame: np.ndarray | None = None
        self._last_frame_time: float = 0.0
        self.width = 640
        self.height = 480

    def set_frame_callback(self, cb: Callable[[np.ndarray], None]):
        self._callback = cb

    async def start(self):
        if "mock" in self._url or self._url == "":
            self._mock = True
        self._connected = True
        self._task = asyncio.create_task(self._recv_loop())

    async def stop(self):
        self._connected = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _recv_loop(self):
        if self._mock:
            await self._mock_loop()
        elif self._url.startswith("rtsp://") or self._url.startswith("tcp://"):
            await self._opencv_loop()
        else:
            await self._mjpeg_loop()

    async def _mock_loop(self):
        """Generate synthetic test frames for development."""
        import time
        w, h = 640, 480
        t = 0.0
        while self._connected:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            # Moving circle target
            cx = int(w / 2 + 80 * np.sin(t * 0.5))
            cy = int(h / 2 + 60 * np.cos(t * 0.35))
            cv2 = None
            try:
                import cv2
            except ImportError:
                pass
            if cv2:
                cv2.circle(frame, (cx, cy), 30, (0, 255, 0), -1)
                cv2.putText(frame, "MOCK STREAM", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                # Fallback: draw a simple rectangle as target
                frame[cy-20:cy+20, cx-20:cx+20] = (0, 255, 0)

            self._latest_frame = frame
            self._last_frame_time = time.time()
            if self._callback:
                self._callback(frame)
            t += 0.033
            await asyncio.sleep(0.033)

    async def _mjpeg_loop(self):
        """Read MJPEG stream over HTTP."""
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp not installed, falling back to mock")
            await self._mock_loop()
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._url) as resp:
                    if resp.status != 200:
                        logger.error("MJPEG stream returned %d", resp.status)
                        return
                    boundary = None
                    ct = resp.headers.get("Content-Type", "")
                    if "boundary=" in ct:
                        boundary = ct.split("boundary=")[-1].strip().encode()
                    if not boundary:
                        boundary = b"--frame"

                    buf = b""
                    async for chunk in resp.content.iter_chunked(BUFFER_SIZE):
                        if not self._connected:
                            break
                        buf += chunk
                        while boundary in buf:
                            self._parse_mjpeg_frame(buf, boundary)
                            # Advance past parsed frame
                            idx = buf.find(boundary)
                            next_idx = buf.find(boundary, idx + len(boundary))
                            if next_idx == -1:
                                buf = buf[idx:]
                                break
                            buf = buf[next_idx:]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("MJPEG stream error: %s", e)
        except Exception as e:
            logger.error("MJPEG stream unexpected: %s", e)

    def _parse_mjpeg_frame(self, buf: bytes, boundary: bytes):
        """Extract a single JPEG frame from MJPEG multipart buffer."""
        try:
            import cv2
        except ImportError:
            return

        idx = buf.find(boundary)
        if idx == -1:
            return
        head_end = buf.find(b"\r\n\r\n", idx)
        if head_end == -1:
            head_end = buf.find(b"\n\n", idx)
        if head_end == -1:
            return

        next_boundary = buf.find(boundary, head_end + 4)
        if next_boundary == -1:
            return

        jpg_data = buf[head_end + 4:next_boundary]
        if len(jpg_data) < 128:
            return

        arr = np.frombuffer(jpg_data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            self._latest_frame = frame
            self._last_frame_time = time.time()
            if self._callback:
                self._callback(frame)

    async def _opencv_loop(self):
        """Read video stream via OpenCV VideoCapture (RTSP, TCP MPEG-TS, etc.)."""
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not installed, falling back to mock")
            await self._mock_loop()
            return

        import threading
        cap_lock = threading.Lock()
        cap = None
        loop = asyncio.get_running_loop()

        def _read_frame():
            """Read a single frame with cap protected by lock."""
            nonlocal cap
            with cap_lock:
                if cap is None:
                    return False, None
                ret, frame = cap.read()
            return ret, frame

        while self._connected:
            if cap is None:
                with cap_lock:
                    cap = cv2.VideoCapture(self._url)
                await asyncio.sleep(0.5)
                with cap_lock:
                    ok = cap.isOpened()
                if not ok:
                    logger.debug("Waiting for video stream: %s", self._url)
                    with cap_lock:
                        cap.release()
                        cap = None
                    await asyncio.sleep(2.0)
                    continue
                logger.info("Video stream opened: %s", self._url)

            try:
                ret, frame = await asyncio.wait_for(
                    loop.run_in_executor(None, _read_frame), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Video frame read timed out, reconnecting...")
                with cap_lock:
                    cap.release()
                    cap = None
                await asyncio.sleep(1)
                continue
            if not ret or frame is None:
                logger.warning("Video frame read failed, reconnecting...")
                with cap_lock:
                    cap.release()
                    cap = None
                await asyncio.sleep(1)
                continue
            self._latest_frame = frame
            self._last_frame_time = time.time()
            self.width = frame.shape[1]
            self.height = frame.shape[0]
            if self._callback:
                self._callback(frame)
            await asyncio.sleep(0)

        if cap:
            with cap_lock:
                cap.release()

    def read(self) -> np.ndarray | None:
        """Return the latest received frame (pollable, for Qt timer integration)."""
        frame = self._latest_frame
        self._latest_frame = None
        return frame

    def stale(self, threshold: float = 0.5) -> bool:
        """True if no frame received for `threshold` seconds."""
        if self._last_frame_time == 0.0:
            return True
        return (time.time() - self._last_frame_time) > threshold

    def close(self):
        pass

    @property
    def connected(self) -> bool:
        return self._connected

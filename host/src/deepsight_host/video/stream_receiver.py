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
        """Read TCP MPEG-TS via raw socket + ffmpeg pipe.

        Avoids OpenCV VideoCapture's built-in FFmpeg backend which
        disconnects every ~30s when reading MPEG-TS over TCP.
        Instead: raw TCP socket -> ffmpeg demuxer -> raw BGR frames -> Python.
        """
        import numpy as np

        # Default frame size (updated when first frame arrives)
        frame_w, frame_h = 1920, 1080
        frame_bytes = frame_w * frame_h * 3
        reconnect_delay = 1.0

        while self._connected:
            reader: asyncio.StreamReader | None = None
            writer: asyncio.StreamWriter | None = None
            ffmpeg_proc: asyncio.subprocess.Process | None = None
            relay_task: asyncio.Task | None = None

            try:
                # Parse host:port from URL
                url = self._url
                if url.startswith("tcp://"):
                    url = url[6:]
                host, port_str = url.rsplit(":", 1)
                port = int(port_str)

                # Connect to Pi stream relay
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=5.0
                )
                logger.info("TCP stream connected: %s:%d", host, port)

                # Spawn ffmpeg to decode MPEG-TS → raw BGR frames
                # Low-latency: nobuffer + low_delay keep per-frame decode fast.
                # probesize/analyzeduration need headroom for initial SPS/PPS
                # detection on the MPEG-TS stream (32/0 was too aggressive —
                # ffmpeg failed to determine resolution and exited immediately).
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-loglevel", "warning",
                    "-fflags", "nobuffer",
                    "-flags", "low_delay",
                    "-probesize", "500000",
                    "-analyzeduration", "1000000",
                    "-f", "mpegts",
                    "-i", "pipe:0",
                    "-f", "rawvideo",
                    "-pix_fmt", "bgr24",
                    "pipe:1",
                ]
                ffmpeg_proc = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                # Relay: TCP → ffmpeg stdin (background task)
                async def relay_tcp_to_ffmpeg():
                    try:
                        while self._connected and ffmpeg_proc.stdin is not None:
                            data = await asyncio.wait_for(
                                reader.read(65536), timeout=5.0
                            )
                            if not data:
                                break
                            ffmpeg_proc.stdin.write(data)
                            await ffmpeg_proc.stdin.drain()
                    except (asyncio.TimeoutError, ConnectionError, OSError):
                        pass
                    finally:
                        # Close ffmpeg stdin so it flushes and exits
                        try:
                            if ffmpeg_proc.stdin is not None:
                                ffmpeg_proc.stdin.close()
                        except OSError:
                            pass

                relay_task = asyncio.create_task(relay_tcp_to_ffmpeg())

                # Read decoded frames from ffmpeg stdout
                while self._connected and ffmpeg_proc.stdout is not None:
                    try:
                        raw = await asyncio.wait_for(
                            ffmpeg_proc.stdout.readexactly(frame_bytes),
                            timeout=5.0,
                        )
                    except asyncio.IncompleteReadError:
                        break  # ffmpeg closed stdout
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (frame_h, frame_w, 3)
                    )
                    # Update resolution from actual frame size
                    if frame.shape[1] != frame_w or frame.shape[0] != frame_h:
                        frame_w, frame_h = frame.shape[1], frame.shape[0]
                        frame_bytes = frame_w * frame_h * 3

                    # .copy() — ffmpeg stdout buffer is read-only
                    self._latest_frame = frame.copy()
                    self._last_frame_time = time.time()
                    self.width = frame_w
                    self.height = frame_h
                    if self._callback:
                        # .copy() required — ffmpeg stdout buffer is read-only
                        self._callback(frame.copy())

                relay_task.cancel()

            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                logger.debug("TCP stream error: %s", e)
            except Exception as e:
                logger.warning("Stream decode error: %s", e)
            finally:
                if relay_task is not None:
                    relay_task.cancel()
                if ffmpeg_proc is not None:
                    try:
                        if ffmpeg_proc.stdin is not None:
                            ffmpeg_proc.stdin.close()
                    except OSError:
                        pass
                    try:
                        await ffmpeg_proc.wait()
                    except OSError:
                        ffmpeg_proc.kill()
                        await ffmpeg_proc.wait()
                if writer is not None:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except OSError:
                        pass

            if self._connected:
                await asyncio.sleep(reconnect_delay)

    def read(self) -> np.ndarray | None:
        """Return the latest received frame (pollable, for Qt timer integration)."""
        frame = self._latest_frame
        self._latest_frame = None
        return frame

    def frame_age_ms(self) -> float:
        """Return age of the latest frame in milliseconds.

        Measures time since the last frame was decoded — a proxy for
        end-to-end latency (GoPro → Pi → Host decode).
        """
        if self._last_frame_time == 0.0:
            return 0.0
        return (time.time() - self._last_frame_time) * 1000.0

    def stale(self, threshold: float = 3.0) -> bool:
        """True if no frame received for `threshold` seconds.

        Uses a 3s default — long enough to ride out brief encoder/capture
        interruptions on the Pi side without showing the placeholder.
        """
        if self._last_frame_time == 0.0:
            return True
        return (time.time() - self._last_frame_time) > threshold

    def close(self):
        pass

    @property
    def connected(self) -> bool:
        return self._connected

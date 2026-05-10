"""Video encoder — ffmpeg subprocess pipeline.

Encodes raw frames to H.264 via ffmpeg stdin pipe.
Supports file output, RTMP/SRT streaming, and TCP MPEG-TS serving.

Pi 5 hardware encode: codec="h264_v4l2m2m" (VideoCore VII GPU, ~5% CPU).
Software fallback: codec="libx264".
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np

logger = logging.getLogger("pi.encoder")


class VideoEncoder:
    """Encodes frames using an ffmpeg subprocess.

    Frames are fed via stdin in raw RGB24 format. ffmpeg handles
    encoding, muxing, and output.
    """

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 60,
                 codec: str = "h264_v4l2m2m", output: str = "",
                 bitrate: str = "8M"):
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.output = output
        self.bitrate = bitrate
        self._proc: asyncio.subprocess.Process | None = None
        self._running = False
        self._frame_count = 0

    def _build_cmd(self) -> list[str]:
        """Build ffmpeg command line."""
        cmd = [
            "ffmpeg",
            "-loglevel", "warning",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",
            "-c:v", self.codec,
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-g", str(self.fps * 2),
            "-b:v", self.bitrate,
            "-maxrate", "12M",
            "-bufsize", "4M",
        ]
        # Hardware-specific flags
        if "v4l2m2m" in self.codec:
            cmd += ["-num_output_buffers", "8", "-num_capture_buffers", "8"]
        # Output format
        if self.output:
            if self.output.startswith("rtmp"):
                cmd += ["-f", "flv"]
            elif self.output.startswith("srt"):
                cmd += ["-f", "mpegts"]
            elif self.output.startswith("tcp://"):
                # TCP MPEG-TS server mode — Host connects to this
                cmd += ["-f", "mpegts"]
                if "?" not in self.output:
                    self.output += "?listen=1"
            elif self.output.endswith(".mp4"):
                cmd += ["-f", "mp4"]
            else:
                cmd += ["-f", "mpegts"]
            cmd += [self.output]
        else:
            cmd += ["-f", "null", "-"]

        return cmd

    async def start(self) -> bool:
        if self._running:
            return True

        cmd = self._build_cmd()
        logger.info("Encoder: %s %dx%d@%d → %s",
                      self.codec, self.width, self.height, self.fps,
                      self._obfuscate_output())
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            self._running = True
            self._frame_count = 0
            return True
        except FileNotFoundError:
            logger.error("ffmpeg not found — install: sudo apt install ffmpeg")
            return False
        except Exception as e:
            logger.error("Encoder start failed: %s", e)
            return False

    async def encode_frame(self, frame: np.ndarray) -> bool:
        """Feed a raw frame into the encoder. Non-blocking after write."""
        if not self._running or self._proc is None:
            return False
        if frame.shape[2] == 3:
            rgb = frame
        else:
            rgb = frame[:, :, :3]
        if not rgb.flags['C_CONTIGUOUS']:
            rgb = rgb.copy()

        try:
            self._proc.stdin.write(rgb.tobytes())
            await self._proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            logger.error("Encoder pipe broken")
            await self.stop()
            return False

        self._frame_count += 1
        return True

    async def stop(self):
        if not self._running or self._proc is None:
            return
        self._running = False
        try:
            self._proc.stdin.close()
            await self._proc.wait()
        except Exception:
            self._proc.kill()
            await self._proc.wait()
        logger.info("Encoder stopped (%d frames)", self._frame_count)
        self._proc = None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def running(self) -> bool:
        return self._running

    def _obfuscate_output(self) -> str:
        o = self.output
        if not o:
            return "null"
        if "rtmp" in o and "/" in o:
            return o.rsplit("/", 1)[0] + "/***"
        return o

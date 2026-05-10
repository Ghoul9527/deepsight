"""Livestream output — RTMP / SRT streaming via ffmpeg.

Supports:
- RTMP push to YouTube Live, Twitch, or custom nginx-rtmp server
- SRT for low-latency point-to-point streaming
- Local recording + streaming simultaneously via ffmpeg tee muxer
"""

from __future__ import annotations

import asyncio
import logging

from deepsight_pi.encoder import VideoEncoder

logger = logging.getLogger("pi.streaming")


class StreamOutput:
    """Manages a livestream output using VideoEncoder.

    Wraps an encoder configured with an RTMP/SRT URL as output.
    """

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 60,
                 codec: str = "h264_v4l2m2m"):
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self._encoder: VideoEncoder | None = None
        self._stream_url: str = ""
        self._streaming = False

    @property
    def streaming(self) -> bool:
        return self._streaming

    @property
    def stream_url(self) -> str:
        return self._stream_url

    async def start_rtmp(self, rtmp_url: str) -> bool:
        """Start streaming to an RTMP server.

        Args:
            rtmp_url: e.g. 'rtmp://a.rtmp.youtube.com/live2/your-stream-key'
        """
        self._stream_url = rtmp_url
        self._encoder = VideoEncoder(
            width=self.width, height=self.height, fps=self.fps,
            codec=self.codec, output=rtmp_url,
        )
        ok = await self._encoder.start()
        if ok:
            self._streaming = True
            logger.info("RTMP stream started → %s", self._obfuscate_url(rtmp_url))
        return ok

    async def start_srt(self, srt_url: str, latency_us: int = 200000) -> bool:
        """Start SRT streaming (low-latency UDP-based).

        Args:
            srt_url: e.g. 'srt://192.168.1.100:9000'
            latency_us: Target latency in microseconds (default 200ms).
        """
        self._stream_url = srt_url
        self._encoder = VideoEncoder(
            width=self.width, height=self.height, fps=self.fps,
            codec=self.codec,
            output=f"{srt_url}?latency={latency_us}&mode=caller",
        )
        ok = await self._encoder.start()
        if ok:
            self._streaming = True
            logger.info("SRT stream started → %s", srt_url)
        return ok

    async def start_recording(self, file_path: str, stream_url: str = "") -> bool:
        """Record to file while optionally streaming.

        Uses ffmpeg tee muxer to output to both file and stream.
        """
        outputs = [file_path]
        if stream_url:
            outputs.append(stream_url)

        # Build tee output: [f=mp4]file.mp4|[f=flv]rtmp://...
        tee_parts = []
        if stream_url and file_path:
            tee = f"[f=mp4:onfail=ignore]{file_path}|[f=flv:onfail=ignore]{stream_url}"
            output = tee
        elif file_path:
            output = file_path
        else:
            output = stream_url

        self._stream_url = stream_url or file_path
        self._encoder = VideoEncoder(
            width=self.width, height=self.height, fps=self.fps,
            codec=self.codec, output=output,
        )
        ok = await self._encoder.start()
        if ok:
            self._streaming = True
            logger.info("Recording + stream started → %s", file_path)
        return ok

    async def push_frame(self, frame) -> bool:
        """Enqueue a frame for encoding/streaming. Non-blocking."""
        if not self._streaming or self._encoder is None:
            return False
        await self._encoder.encode_frame(frame)
        return True

    async def stop(self):
        if self._encoder:
            await self._encoder.stop()
            self._encoder = None
        self._streaming = False
        self._stream_url = ""
        logger.info("Stream stopped")

    @staticmethod
    def _obfuscate_url(url: str) -> str:
        """Hide stream key in logs."""
        if "rtmp" in url and "/" in url:
            parts = url.rsplit("/", 1)
            if len(parts) == 2:
                return f"{parts[0]}/***"
        return url

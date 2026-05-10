"""Video server — serves MPEG-TS over TCP to Host.

Modes:
  - off:      No video server running. Host shows "No Video Signal".
  - passthrough: TCP proxy to real Pi's video stream.
  - camera:   Capture from local camera → ffmpeg H.264 encode → TCP serve.
  - file:     Loop a video file → ffmpeg H.264 encode → TCP serve.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

logger = logging.getLogger("emu.video")

PORT = 8554


class VideoServer:
    def __init__(self, port: int = PORT):
        self._port = port
        self._mode = "off"            # off | passthrough | camera | file
        self._pi_host = "127.0.0.1"
        self._pi_port = 8554
        self._camera_id = 0
        self._file_path = ""
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task | None = None
        self._proxy_task: asyncio.Task | None = None
        self._proxy_server = None

    # ── Configuration ──

    def set_mode(self, mode: str):
        assert mode in ("off", "passthrough", "camera", "file")
        self._mode = mode

    def set_pi_address(self, host: str, port: int = 8554):
        self._pi_host = host
        self._pi_port = port

    def set_camera(self, camera_id: int = 0):
        self._camera_id = camera_id

    def set_file(self, path: str):
        self._file_path = path

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def port(self) -> int:
        return self._port

    # ── Lifecycle ──

    async def start(self):
        if self._mode == "off":
            logger.info("Video server: off")
            return
        elif self._mode == "passthrough":
            await self._start_passthrough()
        elif self._mode == "camera":
            await self._start_camera()
        elif self._mode == "file":
            await self._start_file()

    async def stop(self):
        if self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None

        if self._proxy_task:
            self._proxy_task.cancel()
            try:
                await self._proxy_task
            except asyncio.CancelledError:
                pass
            self._proxy_task = None

        if self._proxy_server:
            self._proxy_server.close()
            await self._proxy_server.wait_closed()
            self._proxy_server = None

        if self._proc:
            try:
                self._proc.send_signal(signal.SIGTERM)
                await asyncio.wait_for(self._proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            except ProcessLookupError:
                pass
            self._proc = None

    # ── Passthrough: TCP proxy to real Pi ──

    async def _start_passthrough(self):
        logger.info("Video passthrough: :%d → %s:%d",
                      self._port, self._pi_host, self._pi_port)
        self._proxy_server = await asyncio.start_server(
            self._handle_passthrough, "0.0.0.0", self._port)
        self._proxy_task = asyncio.create_task(self._proxy_server.serve_forever())

    async def _handle_passthrough(self, client_r, client_w):
        """Bidirectional TCP pipe: Host ↔ Pi."""
        peer = client_w.get_extra_info('peername')
        logger.debug("Video passthrough client: %s", peer)
        try:
            pi_r, pi_w = await asyncio.open_connection(self._pi_host, self._pi_port)
        except (ConnectionRefusedError, OSError) as e:
            logger.warning("Pi video not reachable: %s", e)
            client_w.close()
            return

        async def pipe(src_r, dst_w, label):
            try:
                while True:
                    data = await src_r.read(65536)
                    if not data:
                        break
                    dst_w.write(data)
                    await dst_w.drain()
            except Exception:
                pass

        await asyncio.gather(
            pipe(client_r, pi_w, "H→P"),
            pipe(pi_r, client_w, "P→H"),
        )
        client_w.close()
        pi_w.close()

    # ── Camera mode ──

    async def _start_camera(self):
        logger.info("Video: camera %d → tcp://0.0.0.0:%d", self._camera_id, self._port)
        self._proc = await self._launch_ffmpeg(
            input_args=["-f", "avfoundation",
                        "-framerate", "30",
                        "-video_size", "1280x720",
                        "-i", str(self._camera_id)])

    # ── File mode ──

    async def _start_file(self):
        if not self._file_path or not os.path.exists(self._file_path):
            logger.error("Video file not found: %s", self._file_path)
            return
        logger.info("Video: file loop %s → tcp://0.0.0.0:%d",
                      self._file_path, self._port)
        self._proc = await self._launch_ffmpeg(
            input_args=["-stream_loop", "-1",
                        "-re",
                        "-i", self._file_path])

    async def _launch_ffmpeg(self, input_args: list[str]):
        """Launch ffmpeg: input → H.264 → MPEG-TS → TCP listen."""
        cmd = [
            "ffmpeg",
            "-loglevel", "warning",
            *input_args,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "4M",
            "-maxrate", "8M",
            "-bufsize", "2M",
            "-f", "mpegts",
            f"tcp://0.0.0.0:{self._port}?listen=1",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            # Drain stderr continuously so the pipe never fills and blocks ffmpeg
            self._stderr_task = asyncio.create_task(self._drain_stderr(proc))
            return proc
        except FileNotFoundError:
            logger.error("ffmpeg not found — install: brew install ffmpeg")
            return None

    async def _drain_stderr(self, proc: asyncio.subprocess.Process):
        """Read and log ffmpeg stderr lines to prevent pipe buffer from filling."""
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    logger.debug("ffmpeg: %s", decoded)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("ffmpeg stderr drain: %s", e)

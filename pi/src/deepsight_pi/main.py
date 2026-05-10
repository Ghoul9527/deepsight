"""DeepSight Pi 5 — main entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from deepsight_pi.config import PiConfig
from deepsight_pi.api import PiApi
from deepsight_pi.bridge.host_link import HostLink
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.bridge.stm32_link import Stm32Link
from deepsight_pi.bridge.message_router import MessageRouter
from deepsight_pi.gopro import create_gopro
from deepsight_pi.capture import create_capture
from deepsight_pi.encoder import VideoEncoder
from deepsight_pi.watchdog import Watchdog

logger = logging.getLogger("pi")


class PiNode:
    def __init__(self):
        self.config = PiConfig()
        self._setup_logging()

        # Hardware (config-driven: mock or real)
        self.gopro = create_gopro(mock=self.config.gopro_mock)
        self.capture = create_capture(
            mock=self.config.capture_mock,
            width=self.config.capture_width,
            height=self.config.capture_height,
            fps=self.config.capture_fps,
            device=self.config.capture_device,
        )

        # Video encoder (Pi 5 hardware H.264 → TCP MPEG-TS stream)
        stream_output = f"tcp://0.0.0.0:{self.config.video_stream_port}"
        self.encoder = VideoEncoder(
            width=self.config.capture_width,
            height=self.config.capture_height,
            fps=self.config.capture_fps,
            codec=self.config.video_codec,
            bitrate=self.config.video_bitrate,
            output=stream_output,
        )

        # Communication
        self.host_link = HostLink(self.config)
        self.pico_link = PicoLink(self.config)
        self.stm32_link = Stm32Link(self.config)
        self.router = MessageRouter(
            self.host_link, self.pico_link, self.stm32_link,
            self.gopro, self.capture,
        )

        # API
        self.api = PiApi(self.config, self)

        # Watchdog
        self.watchdog = Watchdog(self.config, self.host_link)

    def _setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="[%(asctime)s] %(levelname)-8s [pi.%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    async def run(self):
        logger.info("Starting DeepSight Pi Node...")

        # Start comm links
        await self.host_link.start()
        if self.config.pico_port != "mock":
            await self.pico_link.start()
        if self.config.stm32_port != "mock":
            await self.stm32_link.start()

        # Start router
        await self.router.start()

        # Start watchdog
        await self.watchdog.start()

        # Start API
        await self.api.start()

        # Start video pipeline (capture + encoder)
        await self.capture.start()
        if await self.encoder.start():
            self._video_task = asyncio.create_task(self._video_loop())

        # Block until shutdown is requested (keeps the asyncio loop alive)
        self._shutdown_event = asyncio.Event()
        await self._shutdown_event.wait()

    async def _video_loop(self):
        """Read frames from capture, feed to encoder, repeat."""
        logger.info("Video loop started (%dx%d@%d)",
                      self.config.capture_width,
                      self.config.capture_height,
                      self.config.capture_fps)
        while self.encoder.running:
            frame = await self.capture.read_frame()
            if frame is None:
                await asyncio.sleep(0.001)
                continue
            await self.encoder.encode_frame(frame)
            await asyncio.sleep(0)

    async def shutdown(self):
        logger.info("Shutting down Pi node...")
        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()
        if hasattr(self, '_video_task'):
            self._video_task.cancel()
        await self.encoder.stop()
        await self.capture.stop()
        await self.watchdog.stop()
        await self.router.stop()
        await self.host_link.stop()
        await self.api.stop()


def main():
    node = PiNode()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(node.run())
    except KeyboardInterrupt:
        loop.run_until_complete(node.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

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
from deepsight_pi.stream_relay import StreamRelay
from deepsight_pi.gopro_stream import GoProStreamManager
from deepsight_pi.watchdog import Watchdog

logger = logging.getLogger("pi")


class PiNode:
    def __init__(self):
        self.config = PiConfig()
        self._setup_logging()

        # Hardware (config-driven: mock or real)
        self.gopro = create_gopro(
            mock=self.config.gopro_mock,
            wifi_ssid=self.config.gopro_wifi_ssid,
            wifi_password=self.config.gopro_wifi_password,
            wifi_interface=self.config.gopro_wifi_interface,
            usb_iface=self.config.gopro_usb_iface,
        )
        self.capture = create_capture(
            mock=self.config.capture_mock,
            width=self.config.capture_width,
            height=self.config.capture_height,
            fps=self.config.capture_fps,
            device=self.config.capture_device,
        )

        # Video encoder (Pi 5 H.264 → stdout → Python TCP relay)
        stream_output = f"tcp://0.0.0.0:{self.config.video_stream_port}"
        self.encoder = VideoEncoder(
            width=self.config.capture_width,
            height=self.config.capture_height,
            fps=self.config.capture_fps,
            codec=self.config.video_codec,
            bitrate=self.config.video_bitrate,
            output=stream_output,
        )
        self.stream_relay = StreamRelay(port=self.config.video_stream_port)

        # GoPro USB stream manager (Viewfinder / Webcam modes)
        self.stream_manager = GoProStreamManager()

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

        # Start video pipeline: GoPro USB stream → relay → Host
        asyncio.create_task(self._start_gopro_stream())

        # Open GoPro USB connection (background, don't block startup)
        asyncio.create_task(self._connect_gopro())

        # Block until shutdown is requested (keeps the asyncio loop alive)
        self._shutdown_event = asyncio.Event()
        await self._shutdown_event.wait()

    async def _start_gopro_stream(self):
        """Detect GoPro IP on USB Ethernet, then start viewfinder stream."""
        await asyncio.sleep(3)  # Let USB Ethernet settle
        gopro_ip = await self._detect_gopro_ip()
        if gopro_ip:
            self.stream_manager.set_gopro_ip(gopro_ip)
            logger.info("GoPro detected at %s, starting viewfinder stream...", gopro_ip)
            await self.stream_manager.start_viewfinder(self.stream_relay)
        else:
            logger.warning("GoPro not detected on USB Ethernet, "
                           "stream will start once GoPro connects")

    async def _connect_gopro(self):
        """Connect to GoPro in the background with exponential backoff.

        Uses USB-C Ethernet (GoPro Connect mode) — camera must be set to
        GoPro Connect mode via Preferences > USB. Falls back to WiFi AP.
        """
        await asyncio.sleep(2)  # Let startup settle
        retry_delay = 5
        max_delay = 300  # 5 minutes max backoff
        while not hasattr(self, '_shutdown_event') or not self._shutdown_event.is_set():
            if await self.gopro.is_ready():
                break
            try:
                if await asyncio.wait_for(self.gopro.open(), timeout=10):
                    logger.info("GoPro connected")
                    retry_delay = 5  # reset backoff
                    break
            except asyncio.TimeoutError:
                pass
            logger.debug("GoPro not ready, retrying in %ds...", retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

    async def _detect_gopro_ip(self) -> str | None:
        """Find GoPro IP address from DHCP lease on USB Ethernet interface."""
        import struct, socket, fcntl, os

        # Try common GoPro USB-C Ethernet IPs
        common_ips = [
            "172.25.132.51",  # Known from previous session
            "172.28.128.51",
            "172.20.16.51",
            "172.20.17.51",
            "172.20.18.51",
            "172.20.19.51",
        ]
        for ip in common_ips:
            try:
                resp = await asyncio.get_event_loop().run_in_executor(
                    None, lambda i=ip: __import__('urllib.request').request.urlopen(
                        f"http://{i}:8080/gopro/camera/state", timeout=2
                    )
                )
                if resp.status == 200:
                    return ip
            except Exception:
                continue

        # Fallback: scan the eth1 subnet
        try:
            import subprocess
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "eth1"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "inet " in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip_net = parts[1]  # e.g., "172.25.132.53/24"
                        base_ip = ip_net.split("/")[0]
                        # Try .51 as GoPro IP (common DHCP server assignment)
                        parts = base_ip.rsplit(".", 1)
                        if len(parts) == 2:
                            candidate = f"{parts[0]}.51"
                            try:
                                resp = await asyncio.get_event_loop().run_in_executor(
                                    None, lambda: __import__('urllib.request').request.urlopen(
                                        f"http://{candidate}:8080/gopro/camera/state",
                                        timeout=2,
                                    )
                                )
                                if resp.status == 200:
                                    return candidate
                            except Exception:
                                pass
        except Exception:
            pass

        return None

    async def _video_loop(self):
        """Read frames from capture, feed to encoder. Auto-restart encoder on failure.

        NOTE: This is the legacy HDMI capture path, kept as fallback.
        The primary video path is now GoProStreamManager → StreamRelay.
        """
        logger.info("Video loop started (%dx%d@%d)",
                      self.config.capture_width,
                      self.config.capture_height,
                      self.config.capture_fps)
        while not hasattr(self, '_shutdown_event') or not self._shutdown_event.is_set():
            if not self.encoder.running:
                # Auto-restart encoder (handles broken pipe, ffmpeg crash)
                logger.warning("Encoder not running, restarting...")
                await asyncio.sleep(0.5)
                await self.encoder.start()
                await asyncio.sleep(0.5)
                continue

            frame = await self.capture.read_frame()
            if frame is None:
                await asyncio.sleep(0.001)
                continue

            ok = await self.encoder.encode_frame(frame)
            if not ok:
                # encode_frame returns False on pipe error
                logger.warning("Frame encode failed, pausing before retry...")
                await asyncio.sleep(0.5)
            await asyncio.sleep(0)

    async def shutdown(self):
        logger.info("Shutting down Pi node...")
        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()
        if hasattr(self, '_video_task'):
            self._video_task.cancel()
        await self.stream_manager.stop()
        await self.stream_relay.stop()
        await self.encoder.stop()
        await self.capture.stop()
        await self.gopro.close()
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

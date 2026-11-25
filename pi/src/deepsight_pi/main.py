"""DeepSight Pi — underwater network gateway and message bridge."""

from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from deepsight_pi.config import PiConfig
from deepsight_pi.api import PiApi
from deepsight_pi.bridge.host_link import HostLink
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.bridge.stm32_link import Stm32Link
from deepsight_pi.bridge.message_router import MessageRouter
from deepsight_pi.watchdog import Watchdog
from deepsight_pi.hardware.leak_sensor import PiLeakMonitor

logger = logging.getLogger("pi")


class PiNode:
    def __init__(self):
        self.config = PiConfig()
        self._setup_logging()

        # Communication links
        self.host_link = HostLink(self.config)
        self.pico_link = PicoLink(self.config)
        self.stm32_link = Stm32Link(self.config)
        self.router = MessageRouter(self.host_link, self.pico_link, self.stm32_link,
                                     servo_config=self.config.hardware,
                                     stabilizer_config=self.config.stabilizer,
                                     fin_config=self.config.fin_coupling)

        self.leak_monitor = PiLeakMonitor(
            self.host_link, self.config.leak_sensor, self.config.pi_id)

        # API
        self.api = PiApi(self.config)

        # Watchdog
        self.watchdog = Watchdog(self.config, self.host_link)

    def _setup_logging(self):
        # Persist incidents independently of journald's high-volume debug stream.
        path = Path(self.config.log_dir) / "deepsight-pi.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="[%(asctime)s] %(levelname)-8s [pi.%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.StreamHandler(), file_handler],
        )
        logger.info("Persistent log: %s (5 MiB x 4 files, INFO and above)", path.resolve())

    async def run(self):
        logger.info("Starting DeepSight Pi gateway...")

        await self.host_link.start()
        if self.config.pico_port != "mock":
            await self.pico_link.start()
        if self.config.stm32_port != "mock":
            await self.stm32_link.start()

        await self.leak_monitor.start()
        await self.router.start()
        await self.watchdog.start()
        await self.api.start()

        self._shutdown_event = asyncio.Event()
        await self._shutdown_event.wait()

    async def shutdown(self):
        logger.info("Shutting down Pi gateway...")
        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()
        await self.leak_monitor.stop()
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

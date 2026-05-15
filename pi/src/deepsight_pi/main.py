"""DeepSight Pi — underwater network gateway and message bridge."""

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
from deepsight_pi.watchdog import Watchdog

logger = logging.getLogger("pi")


class PiNode:
    def __init__(self):
        self.config = PiConfig()
        self._setup_logging()

        # Communication links
        self.host_link = HostLink(self.config)
        self.pico_link = PicoLink(self.config)
        self.stm32_link = Stm32Link(self.config)
        self.router = MessageRouter(self.host_link, self.pico_link, self.stm32_link)

        # API
        self.api = PiApi(self.config)

        # Watchdog
        self.watchdog = Watchdog(self.config, self.host_link)

    def _setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="[%(asctime)s] %(levelname)-8s [pi.%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    async def run(self):
        logger.info("Starting DeepSight Pi gateway...")

        await self.host_link.start()
        if self.config.pico_port != "mock":
            await self.pico_link.start()
        if self.config.stm32_port != "mock":
            await self.stm32_link.start()

        await self.router.start()
        await self.watchdog.start()
        await self.api.start()

        self._shutdown_event = asyncio.Event()
        await self._shutdown_event.wait()

    async def shutdown(self):
        logger.info("Shutting down Pi gateway...")
        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()
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

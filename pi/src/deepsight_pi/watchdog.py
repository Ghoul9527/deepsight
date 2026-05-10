"""Watchdog — monitors connection health and triggers reconnection."""

from __future__ import annotations

import asyncio
import logging

from deepsight_pi.config import PiConfig
from deepsight_pi.bridge.host_link import HostLink
from deepsight_shared.protocol import make_heartbeat

logger = logging.getLogger("pi.watchdog")


class Watchdog:
    def __init__(self, config: PiConfig, host_link: HostLink):
        self._interval = config.heartbeat_interval_s
        self._host_link = host_link
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._heartbeat_loop())
        logger.info("Watchdog started (interval=%.1fs)", self._interval)

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                msg = make_heartbeat("pi")
                await self._host_link.send(msg)
            except Exception as e:
                logger.error("Heartbeat send failed: %s", e)

    async def stop(self):
        self._running = False

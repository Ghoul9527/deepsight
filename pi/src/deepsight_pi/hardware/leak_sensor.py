"""Local 3.3V alarm input; BCM GPIO numbering, separate from Pico telemetry."""
from __future__ import annotations

import asyncio
import logging

from deepsight_shared.protocol import tel_leak

logger = logging.getLogger("pi.leak")


class PiLeakMonitor:
    def __init__(self, host_link, settings: dict, node_id="pi", input_factory=None):
        self._host = host_link
        self._settings = settings
        self._node_id = node_id
        self._input_factory = input_factory
        self._input = None
        self._task = None
        self._last_wet = None
        self._interval = max(0.05, float(settings.get("poll_interval_s", 0.2)))

    async def start(self):
        if not self._settings.get("enabled", False) or self._input is not None:
            return
        factory = self._input_factory
        if factory is None:
            from gpiozero import DigitalInputDevice
            factory = DigitalInputDevice
        gpio = int(self._settings.get("gpio", 22))
        active_high = bool(self._settings.get("active_high", True))
        self._input = factory(gpio, pull_up=not active_high, bounce_time=0.05)
        try:
            await self._publish()
        except Exception:
            self._input.close()
            self._input = None
            raise
        logger.info("Pi leak monitor started: BCM GPIO%d, active_high=%s", gpio, active_high)
        self._task = asyncio.create_task(self._run())

    async def _publish(self):
        wet = bool(self._input.is_active)
        await self._host.send(tel_leak(self._node_id, 0, wet))
        if wet != self._last_wet:
            logger.info("Pi leak GPIO%s: %s", self._settings.get("gpio", 22), "WET" if wet else "DRY")
            self._last_wet = wet

    async def _run(self):
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._publish()
            except Exception:
                logger.exception("Pi leak input/telemetry failed; no new state published")

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._input is not None:
            self._input.close()
            self._input = None

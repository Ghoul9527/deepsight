"""UART link to STM32 Winch Controller."""

from __future__ import annotations

import asyncio
import json
import logging

from deepsight_pi.config import PiConfig
from deepsight_shared.protocol import Message

logger = logging.getLogger("pi.bridge.stm32")


class Stm32Link:
    """UART link to STM32 over GPIO serial (/dev/ttyAMA1 or mock)."""

    def __init__(self, config: PiConfig):
        self._port = config.stm32_port
        self._baud = config.stm32_baud
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        self._running = True
        if self._port == "mock":
            logger.info("Stm32Link: mock mode (no serial)")
            return

        logger.info("Stm32Link: opening %s @ %d baud", self._port, self._baud)
        try:
            self._reader, self._writer = await asyncio.open_serial_connection(
                url=self._port, baudrate=self._baud,
            )
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info("Stm32Link: connected")
        except Exception as e:
            logger.warning("Stm32Link: failed to open %s — %s", self._port, e)

    async def send(self, msg: Message):
        """Send a JSONL-encoded message to the STM32 over UART."""
        if self._port == "mock" or self._writer is None:
            if self._port == "mock":
                logger.debug("[MOCK→STM32] %s", msg.type)
            return

        try:
            line = msg.to_json() + "\n"
            self._writer.write(line.encode("utf-8"))
            await self._writer.drain()
        except Exception as e:
            logger.error("Stm32Link send error: %s", e)

    async def _recv_loop(self):
        """Read JSONL lines from UART and push parsed Messages to the queue."""
        while self._running and self._reader is not None:
            try:
                line = await self._reader.readline()
            except Exception as e:
                logger.error("Stm32Link read error: %s", e)
                await asyncio.sleep(0.5)
                continue

            if not line:
                await asyncio.sleep(0.01)
                continue

            try:
                msg = Message.from_json(line.decode("utf-8").strip())
                await self._recv_queue.put(msg)
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug("Stm32Link parse error: %s", e)

    async def stop(self):
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None

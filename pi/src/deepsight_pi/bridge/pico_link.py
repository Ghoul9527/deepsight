"""UART link to Raspberry Pi Pico."""

from __future__ import annotations

import asyncio
import json
import logging

try:
    from serial_asyncio import open_serial_connection
except ImportError:
    from asyncio import open_serial_connection  # Python 3.12+

from deepsight_pi.config import PiConfig
from deepsight_shared.protocol import Message

logger = logging.getLogger("pi.bridge.pico")


class PicoLink:
    """UART link to Pico over GPIO serial (/dev/ttyAMA0 or mock)."""

    def __init__(self, config: PiConfig):
        self._port = config.pico_port
        self._baud = config.pico_baud
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None
        self._buffer = b""

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        self._running = True
        if self._port == "mock":
            logger.info("PicoLink: mock mode (no serial)")
            return

        logger.info("PicoLink: opening %s @ %d baud", self._port, self._baud)
        try:
            self._reader, self._writer = await open_serial_connection(
                url=self._port, baudrate=self._baud,
            )
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info("PicoLink: connected")
        except Exception as e:
            logger.warning("PicoLink: failed to open %s — %s", self._port, e)

    async def send(self, msg: Message):
        """Send a JSONL-encoded message to the Pico over UART."""
        if self._port == "mock" or self._writer is None:
            if self._port == "mock":
                logger.debug("[MOCK→Pico] %s", msg.type)
            return

        try:
            line = msg.to_json() + "\n"
            self._writer.write(line.encode("utf-8"))
            await self._writer.drain()
        except Exception as e:
            logger.error("PicoLink send error: %s", e)

    async def _recv_loop(self):
        """Read JSONL lines from UART and push parsed Messages to the queue."""
        while self._running and self._reader is not None:
            try:
                line = await self._reader.readline()
            except Exception as e:
                logger.error("PicoLink read error: %s", e)
                await asyncio.sleep(0.5)
                continue

            if not line:
                await asyncio.sleep(0.01)
                continue

            try:
                msg = Message.from_json(line.decode("utf-8").strip())
                await self._recv_queue.put(msg)
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug("PicoLink parse error: %s", e)

    async def stop(self):
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None

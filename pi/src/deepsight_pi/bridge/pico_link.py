"""Serial link to Raspberry Pi Pico.

Hybrid mode: commands sent via USB CDC, telemetry received via GPIO UART.
This prevents Pico's USB writes from blocking the USB protocol stack.
"""

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
    """Link to Pico: commands over USB, telemetry over UART."""

    def __init__(self, config: PiConfig):
        self._cmd_port = config.pico_port
        self._telem_port = config.pico_telemetry_port
        self._baud = config.pico_baud
        self._hybrid = self._cmd_port != self._telem_port

        self._cmd_reader: asyncio.StreamReader | None = None
        self._cmd_writer: asyncio.StreamWriter | None = None
        self._telem_reader: asyncio.StreamReader | None = None
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        self._running = True
        if self._cmd_port == "mock":
            logger.info("PicoLink: mock mode (no serial)")
            return

        # Open command link (USB CDC) for sending
        logger.info("PicoLink: cmd=%s telem=%s baud=%d hybrid=%s",
                     self._cmd_port, self._telem_port, self._baud, self._hybrid)
        try:
            self._cmd_reader, self._cmd_writer = await open_serial_connection(
                url=self._cmd_port,
                baudrate=self._baud,
                bytesize=8,
                parity="N",
                stopbits=1,
            )
            await asyncio.sleep(0.3)
            try:
                self._cmd_reader._transport.serial.reset_input_buffer()
            except Exception:
                pass
        except Exception as e:
            logger.warning("PicoLink: failed to open cmd port %s — %s", self._cmd_port, e)
            return

        # Open telemetry link (GPIO UART) for receiving
        if self._hybrid:
            try:
                self._telem_reader, telem_writer = await open_serial_connection(
                    url=self._telem_port,
                    baudrate=self._baud,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                )
                await asyncio.sleep(0.3)
                try:
                    self._telem_reader._transport.serial.reset_input_buffer()
                except Exception:
                    pass
                logger.info("PicoLink: telemetry UART connected on %s", self._telem_port)
            except Exception as e:
                logger.warning("PicoLink: failed to open telem port %s — %s", self._telem_port, e)
                self._cmd_writer.close()
                await self._cmd_writer.wait_closed()
                self._cmd_writer = None
                return

        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("PicoLink: connected")

    async def send(self, msg: Message):
        """Send a JSONL-encoded message to the Pico over USB CDC."""
        if self._cmd_port == "mock" or self._cmd_writer is None:
            if self._cmd_port == "mock":
                logger.debug("[MOCK->Pico] %s", msg.type)
            return

        try:
            line = msg.to_json() + "\n"
            self._cmd_writer.write(line.encode("utf-8"))
            await self._cmd_writer.drain()
            logger.debug("PicoLink send: %s", msg.type)
        except Exception as e:
            logger.error("PicoLink send error: %s", e)

    async def _recv_loop(self):
        """Read JSONL lines from telemetry port, push parsed Messages to queue."""
        reader = self._telem_reader if self._hybrid else self._cmd_reader
        if reader is None:
            logger.error("PicoLink: no reader available")
            return

        logger.info("PicoLink recv_loop started (hybrid=%s)", self._hybrid)
        loop_count = 0
        while self._running and reader is not None:
            loop_count += 1
            if loop_count <= 3 or loop_count % 50 == 0:
                logger.debug("PicoLink recv_loop iter %d", loop_count)
            try:
                line = await reader.readline()
            except Exception as e:
                logger.error("PicoLink read error: %s", e)
                await asyncio.sleep(0.5)
                continue

            if not line:
                await asyncio.sleep(0.01)
                continue

            logger.debug("PicoLink raw line: %r", line[:800])
            try:
                msg = Message.from_json(line.decode("utf-8").strip())
                await self._recv_queue.put(msg)
                logger.debug("PicoLink recv: %s", msg.type)
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError, KeyError) as e:
                logger.debug("PicoLink parse error: %s", e)

    async def stop(self):
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._cmd_writer:
            self._cmd_writer.close()
            await self._cmd_writer.wait_closed()
            self._cmd_writer = None

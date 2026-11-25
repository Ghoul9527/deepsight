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
        self._telem_writer = None
        self._reconnect_delay = max(0.1, float(config.reconnect_delay_s))
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        if self._running:
            return
        self._running = True
        if self._cmd_port == "mock":
            return
        self._recv_task = asyncio.create_task(self._supervise())

    async def _close_ports(self):
        writers = [self._cmd_writer, self._telem_writer]
        self._cmd_writer = self._telem_writer = None
        self._cmd_reader = self._telem_reader = None
        for writer in writers:
            if writer is None:
                continue
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1)
            except Exception:
                pass

    async def _supervise(self):
        while self._running:
            try:
                self._cmd_reader, self._cmd_writer = await open_serial_connection(
                    url=self._cmd_port, baudrate=self._baud,
                    bytesize=8, parity="N", stopbits=1)
                if self._hybrid:
                    self._telem_reader, self._telem_writer = await open_serial_connection(
                        url=self._telem_port, baudrate=self._baud,
                        bytesize=8, parity="N", stopbits=1)
                logger.info("PicoLink: connected on %s", self._cmd_port)
                await self._recv_loop()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("PicoLink disconnected: %s; retry in %.1fs",
                               e, self._reconnect_delay)
            finally:
                await self._close_ports()
            if self._running:
                await asyncio.sleep(self._reconnect_delay)

    async def send(self, msg: Message):
        """Send a JSONL-encoded message to the Pico over USB CDC."""
        if self._cmd_port == "mock" or self._cmd_writer is None:
            if self._cmd_port == "mock":
                logger.debug("[MOCK->Pico] %s", msg.type)
            return

        try:
            line = msg.to_json() + "\n"
            self._cmd_writer.write(line.encode("utf-8"))
            await asyncio.wait_for(self._cmd_writer.drain(), timeout=2)
            logger.debug("PicoLink send: %s", msg.type)
        except Exception as e:
            logger.warning("PicoLink send failed; closing stale connection: %s", e)
            writer = self._cmd_writer
            self._cmd_writer = None
            if writer is not None:
                writer.close()

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
                line = await asyncio.wait_for(reader.readline(), timeout=5)
            except Exception as e:
                raise ConnectionError("serial read failed or timed out") from e

            if not line:
                raise ConnectionError("serial EOF")

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
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        await self._close_ports()

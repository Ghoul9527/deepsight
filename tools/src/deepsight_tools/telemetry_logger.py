"""Standalone telemetry logger — captures UDP telemetry streams to JSONL files.

Listens on a UDP port for telemetry messages and writes them to timestamped
JSONL log files. Supports message-type filtering and automatic file rotation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger("tools.telemetry_logger")

ROTATION_BYTES = 50 * 1024 * 1024  # 50 MB per file


class TelemetryLogger:
    """Capture telemetry from UDP and write to rotating JSONL files.

    Usage:
        logger = TelemetryLogger("logs/telemetry/")
        logger.set_type_filter({"tel.imu", "tel.depth"})  # optional
        await logger.start()
        ...
        await logger.stop()
    """

    def __init__(self, output_dir: str = "logs/telemetry/",
                 listen_host: str = "0.0.0.0", listen_port: int = 9001):
        self._output_dir = output_dir
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._running = False
        self._transport: asyncio.DatagramTransport | None = None
        self._file = None
        self._bytes_written = 0
        self._file_index = 0
        self._type_filter: set[str] | None = None
        self._message_count = 0
        self._start_time: float | None = None
        self._on_message: Callable | None = None

    def set_type_filter(self, types: set[str] | None):
        """Only log messages whose type is in this set. None = log all."""
        self._type_filter = types

    def set_on_message(self, cb: Callable):
        """Set a callback invoked with each parsed message dict."""
        self._on_message = cb

    async def start(self):
        Path(self._output_dir).mkdir(parents=True, exist_ok=True)
        self._start_time = time.time()
        self._rotate_file()
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self._on_datagram),
            local_addr=(self._listen_host, self._listen_port),
        )
        self._running = True
        logger.info("Telemetry logger: listening on %s:%d → %s",
                     self._listen_host, self._listen_port, self._output_dir)

    async def stop(self):
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None
        if self._file:
            elapsed = time.time() - (self._start_time or time.time())
            logger.info("Telemetry logger stopped: %d messages in %.1fs",
                         self._message_count, elapsed)
            self._file.close()
            self._file = None

    def _rotate_file(self):
        if self._file:
            self._file.close()
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._file_index += 1
        fname = f"telemetry_{ts}_{self._file_index:03d}.jsonl"
        path = os.path.join(self._output_dir, fname)
        self._file = open(path, "w")
        self._bytes_written = 0
        logger.info("Rotated → %s", path)

    def _on_datagram(self, data: bytes):
        if not self._running:
            return
        try:
            for line in data.decode("utf-8").strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)

                # Type filter
                if self._type_filter is not None:
                    msg_type = msg.get("type", "")
                    if msg_type not in self._type_filter:
                        continue

                self._write_message(msg)
        except json.JSONDecodeError:
            logger.debug("Invalid JSON in datagram: %s", data[:120])
        except Exception as e:
            logger.error("Telemetry logger error: %s", e)

    def _write_message(self, msg: dict):
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self._file.write(line)
        self._bytes_written += len(line.encode("utf-8"))
        self._message_count += 1

        if self._bytes_written >= ROTATION_BYTES:
            self._rotate_file()

        if self._on_message:
            try:
                self._on_message(msg)
            except Exception:
                pass

    @property
    def message_count(self) -> int:
        return self._message_count

    @property
    def running(self) -> bool:
        return self._running


class _UDPProtocol(asyncio.DatagramProtocol):
    """Internal protocol handler for UDP datagrams."""

    def __init__(self, callback: Callable[[bytes], None]):
        self._callback = callback

    def datagram_received(self, data, addr):
        self._callback(data)

    def error_received(self, exc):
        logger.error("UDP error: %s", exc)

    def connection_lost(self, exc):
        if exc:
            logger.debug("UDP connection lost: %s", exc)

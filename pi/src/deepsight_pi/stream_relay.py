"""TCP stream relay — broadcasts MPEG-TS to multiple clients.

Reads from ffmpeg stdout and fans out to all connected TCP clients.
Survives individual client disconnections without affecting others.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("pi.stream_relay")

BUFFER_SIZE = 256 * 1024  # 256 KB ring buffer for new clients


class StreamRelay:
    """Reads from an asyncio stream and relays to TCP clients."""

    def __init__(self, port: int = 8554):
        self._port = port
        self._server: asyncio.Server | None = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._buffer = bytearray(BUFFER_SIZE)
        self._buffer_len = 0
        self._source: asyncio.StreamReader | None = None
        self._running = False
        self._bytes_relayed = 0

    async def start(self, source: asyncio.StreamReader) -> None:
        """Start the TCP server and begin relaying from *source*."""
        self._source = source
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port
        )
        self._running = True
        logger.info("Stream relay listening on tcp://0.0.0.0:%d", self._port)
        asyncio.create_task(self._relay_loop())

    async def _relay_loop(self) -> None:
        """Read from source and broadcast to all clients."""
        while self._running and self._source is not None:
            try:
                data = await asyncio.wait_for(
                    self._source.read(32768), timeout=2.0
                )
            except asyncio.TimeoutError:
                continue

            if not data:
                logger.warning("Stream source closed")
                break

            # Update ring buffer
            dlen = len(data)
            if dlen <= BUFFER_SIZE:
                if self._buffer_len + dlen > BUFFER_SIZE:
                    # Wrap around: shift out oldest data
                    discard = self._buffer_len + dlen - BUFFER_SIZE
                    self._buffer[: self._buffer_len - discard] = \
                        self._buffer[discard:self._buffer_len]
                    self._buffer_len -= discard
                self._buffer[self._buffer_len:self._buffer_len + dlen] = data
                self._buffer_len += dlen
            else:
                # Data chunk larger than buffer — keep only the tail
                self._buffer[:] = data[-BUFFER_SIZE:]
                self._buffer_len = BUFFER_SIZE

            self._bytes_relayed += dlen

            # Broadcast to clients (don't let one slow client block others)
            dead: list[asyncio.StreamWriter] = []
            for writer in self._clients:
                try:
                    writer.write(data)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    dead.append(writer)
            # Drain asynchronously — slow clients get dropped
            for writer in list(self._clients):
                if writer in dead:
                    continue
                try:
                    await asyncio.wait_for(writer.drain(), timeout=2.0)
                except (asyncio.TimeoutError, ConnectionResetError,
                        BrokenPipeError, OSError):
                    dead.append(writer)
            for w in dead:
                await self._remove_client(w)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Accept a new TCP client and start streaming."""
        addr = writer.get_extra_info("peername")
        logger.info("Stream client connected: %s", addr)
        self._clients.add(writer)

        # Send buffered data first
        if self._buffer_len > 0:
            try:
                writer.write(bytes(self._buffer[:self._buffer_len]))
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError, OSError):
                await self._remove_client(writer)
                return

        # Detect disconnect via TCP close. The host only reads (never sends),
        # so we can't use reader.read() — it would timeout for no reason.
        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            await self._remove_client(writer)

    async def _remove_client(self, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        logger.info("Stream client disconnected: %s", addr)
        self._clients.discard(writer)
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass

    async def stop(self) -> None:
        self._running = False
        for writer in list(self._clients):
            await self._remove_client(writer)
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("Stream relay stopped (%d bytes relayed)", self._bytes_relayed)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def bytes_relayed(self) -> int:
        return self._bytes_relayed

from __future__ import annotations

import asyncio
import logging
import socket

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.network.udp")


class UDPLink:
    def __init__(self, local_port: int, remote_addr: str, remote_port: int):
        self._local_port = local_port
        self._remote_addr = remote_addr
        self._remote_port = remote_port
        self._sock: socket.socket | None = None
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self._local_port))
        self._running = True
        logger.info("UDP link started on :%d → %s:%d",
                     self._local_port, self._remote_addr, self._remote_port)

    async def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()
            self._sock = None

    async def recv_loop(self):
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._sock, 65536)
                msg = Message.from_bytes(data)
                logger.debug("UDP recv: %s from %s", msg.type, addr)
                await self._recv_queue.put(msg)
            except BlockingIOError:
                await asyncio.sleep(0.001)
            except Exception as e:
                if self._running:
                    logger.error("UDP recv error: %s", e)
                await asyncio.sleep(0.01)

    async def send(self, msg: Message):
        if not self._sock or not self._running:
            logger.warning("UDP send skipped: link not running")
            return
        loop = asyncio.get_event_loop()
        data = msg.to_bytes()
        await loop.sock_sendto(self._sock, data, (self._remote_addr, self._remote_port))
        logger.debug("UDP send: %s", msg.type)

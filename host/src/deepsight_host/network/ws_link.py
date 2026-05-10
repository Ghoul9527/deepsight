from __future__ import annotations

import asyncio
import json
import logging

import aiohttp

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.network.ws")


class WsLink:
    def __init__(self, local_port: int, remote_url: str):
        self._local_port = local_port
        self._remote_url = remote_url
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    async def start(self):
        self._session = aiohttp.ClientSession()
        self._running = True
        await self._connect()

    async def _connect(self):
        while self._running:
            try:
                self._ws = await self._session.ws_connect(self._remote_url)
                logger.info("WS connected to %s", self._remote_url)
                await self._read_loop()
            except (aiohttp.ClientError, ConnectionRefusedError) as e:
                logger.warning("WS connection failed: %s, retrying...", e)
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.error("WS error: %s", e)
                await asyncio.sleep(2.0)

    async def _read_loop(self):
        while self._running and self._ws and not self._ws.closed:
            try:
                msg = await self._ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    m = Message.from_json(msg.data)
                    logger.debug("WS recv: %s", m.type)
                    await self._recv_queue.put(m)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WS closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WS error: %s", self._ws.exception())
                    break
            except Exception as e:
                logger.error("WS read error: %s", e)
                break

    async def send(self, msg: Message):
        if not self._ws or self._ws.closed:
            logger.warning("WS send skipped: not connected")
            return
        await self._ws.send_str(msg.to_json())

    async def stop(self):
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session:
            await self._session.close()

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiohttp
from deepsight_shared.host_registration import RENEW_SECONDS, pairing_key, registration_proof
from deepsight_shared.protocol import Message, new_message

logger = logging.getLogger("host.network.ws")


class WsLink:
    def __init__(self, local_port: int, remote_url: str, *, key_file: Path | None = None):
        self._local_port = local_port
        self._remote_url = remote_url
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._host_key = pairing_key(key_file)
        self.registered = False
        self._recv_queue: asyncio.Queue[Message] = asyncio.Queue()

    @property
    def recv_queue(self) -> asyncio.Queue[Message]:
        return self._recv_queue

    @property
    def registration_enabled(self) -> bool:
        return self._host_key is not None

    async def start(self):
        self._session = aiohttp.ClientSession()
        self._running = True
        await self._connect()

    async def _connect(self):
        while self._running:
            try:
                params = {"register_host": "1"} if self._host_key is not None else None
                async with self._session.ws_connect(
                    self._remote_url, params=params, heartbeat=5,
                ) as ws:
                    self._ws = ws
                    logger.info("WS connected to %s", self._remote_url)
                    if self._host_key is None:
                        await self._read_loop()
                    else:
                        await self._register(ws, self._host_key)
                        self.registered = True
                        async with asyncio.TaskGroup() as group:
                            renew = group.create_task(self._renew_registration(ws))
                            try:
                                await self._read_loop()
                            finally:
                                renew.cancel()
            except Exception as e:
                logger.error("WS error: %s", e)
            finally:
                self._ws = None
                self.registered = False
            if self._running:
                await asyncio.sleep(2.0)

    async def _register(self, ws: aiohttp.ClientWebSocketResponse, key: bytes):
        challenge = Message.from_json(await ws.receive_str(timeout=5))
        nonce = challenge.payload.get("nonce")
        if challenge.type != "host.challenge" or not isinstance(nonce, str):
            raise ValueError("Invalid Host registration challenge")
        local_address = ws.get_extra_info("sockname")
        if local_address is None:
            raise ValueError("Could not determine the WebSocket source address")
        proof = registration_proof(key, nonce, local_address[0])
        await ws.send_str(new_message("host", "host.proof", {"proof": proof}).to_json())
        reply = Message.from_json(await ws.receive_str(timeout=5))
        if reply.type != "host.registered":
            raise ValueError("Pi did not acknowledge Host registration")
        logger.info("Pi accepted automatic Host return address registration")

    async def _renew_registration(self, ws: aiohttp.ClientWebSocketResponse):
        renewal = new_message("host", "host.renew").to_json()
        while not ws.closed:
            await asyncio.sleep(RENEW_SECONDS)
            await ws.send_str(renewal)

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

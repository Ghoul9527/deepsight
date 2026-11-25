"""FastAPI / WebSocket API for the Pi gateway."""

from __future__ import annotations

import asyncio
import logging
import secrets
from ipaddress import IPv4Address

import uvicorn
from deepsight_shared.host_registration import registration_proof
from deepsight_shared.protocol import Message, new_message
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from deepsight_pi.bridge.host_link import HostLink
from deepsight_pi.config import PiConfig

logger = logging.getLogger("pi.api")

app = FastAPI(title="DeepSight Pi API")
_clients: list[WebSocket] = []


async def register_host(ws: WebSocket, link: HostLink, key: bytes) -> str | None:
    if ws.client is None:
        return None
    address = str(IPv4Address(ws.client.host))
    nonce = secrets.token_hex(32)
    await ws.send_text(new_message("pi", "host.challenge", {"nonce": nonce}).to_json())
    response = Message.from_json(await asyncio.wait_for(ws.receive_text(), timeout=5))
    proof = response.payload.get("proof")
    if response.type != "host.proof" or not isinstance(proof, str):
        return None
    expected = registration_proof(key, nonce, address)
    if not secrets.compare_digest(proof.encode(), expected.encode()):
        return None
    if not link.register(ws, address):
        return None
    await ws.send_text(new_message("pi", "host.registered").to_json())
    return address


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    link = getattr(ws.app.state, "host_link", None)
    key = getattr(ws.app.state, "host_key", None)
    address = None
    try:
        if ws.query_params.get("register_host") == "1":
            if link is not None and key is not None:
                address = await register_host(ws, link, key)
            if address is None:
                await ws.close(code=1008)
                return
        _clients.append(ws)
        logger.info("WebSocket client connected")
        while True:
            data = await ws.receive_text()
            msg = Message.from_json(data)
            if msg.type == "host.renew":
                if address is not None and not link.register(ws, address):
                    await ws.close(code=1008)
                    return
                continue
            if _ws_handler:
                await _ws_handler(msg)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except (ValueError, TypeError, KeyError, AttributeError, TimeoutError):
        await ws.close(code=1008)
    finally:
        if ws in _clients:
            _clients.remove(ws)
        if link is not None:
            link.release(ws)


@app.get("/health")
async def get_health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    return {"status": "online", "node": "pi"}


_ws_handler = None


class PiApi:
    def __init__(self, config: PiConfig, host_link: HostLink | None = None,
                 host_key: bytes | None = None):
        self._config = config
        self._server = None
        self._host_link = host_link
        self._host_key = host_key

    def set_ws_handler(self, handler):
        global _ws_handler
        _ws_handler = handler

    async def start(self):
        app.state.host_link = self._host_link
        app.state.host_key = self._host_key
        self._server = uvicorn.Server(
            config=uvicorn.Config(
                app, host="0.0.0.0", port=self._config.ws_port,
                log_level="info", proxy_headers=False,
            )
        )
        asyncio.create_task(self._server.serve())
        logger.info("Pi API started on :%d", self._config.ws_port)

    async def stop(self):
        if self._server:
            self._server.should_exit = True

    async def broadcast(self, msg: Message):
        for client in _clients:
            try:
                await client.send_text(msg.to_json())
            except Exception:
                pass

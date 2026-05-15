"""FastAPI / WebSocket API for the Pi gateway."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from deepsight_pi.config import PiConfig
from deepsight_shared.protocol import Message

logger = logging.getLogger("pi.api")

app = FastAPI(title="DeepSight Pi API")
_clients: list[WebSocket] = []


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    logger.info("WebSocket client connected")
    try:
        while True:
            data = await ws.receive_text()
            msg = Message.from_json(data)
            if _ws_handler:
                await _ws_handler(msg)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        _clients.remove(ws)


@app.get("/health")
async def get_health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    return {"status": "online", "node": "pi"}


_ws_handler = None


class PiApi:
    def __init__(self, config: PiConfig):
        self._config = config
        self._server = None

    def set_ws_handler(self, handler):
        global _ws_handler
        _ws_handler = handler

    async def start(self):
        self._server = uvicorn.Server(
            config=uvicorn.Config(
                app, host="0.0.0.0", port=self._config.ws_port,
                log_level="info",
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

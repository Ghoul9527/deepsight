"""HTTP reverse proxy — forwards Host requests to GoPro USB Ethernet API.

Pi listens on Ethernet interface, forwards to GoPro's IP:8080 over USB.
This turns Pi into a pure transparent proxy — Host controls GoPro directly.
"""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web, ClientSession, ClientTimeout

logger = logging.getLogger("pi.gopro_proxy")

GOPRO_TIMEOUT = ClientTimeout(total=10)


class GoProProxy:
    """Minimal async HTTP reverse proxy: Host → Pi → GoPro."""

    def __init__(self, listen_host: str = "0.0.0.0", listen_port: int = 8080):
        self._host = listen_host
        self._port = listen_port
        self._gopro_base: str | None = None
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._session: ClientSession | None = None

    @property
    def gopro_reachable(self) -> bool:
        return self._gopro_base is not None

    def set_gopro_ip(self, ip: str, port: int = 8080):
        self._gopro_base = f"http://{ip}:{port}"
        logger.info("GoPro proxy target: %s", self._gopro_base)

    async def start(self):
        self._session = ClientSession(timeout=GOPRO_TIMEOUT)
        self._app = web.Application()
        self._app.router.add_route("*", "/{tail:.*}", self._handle)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("GoPro HTTP proxy listening on %s:%d", self._host, self._port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("GoPro HTTP proxy stopped")

    async def _handle(self, request: web.Request):
        if self._gopro_base is None:
            return web.json_response(
                {"error": "GoPro not connected"}, status=502)

        target_url = f"{self._gopro_base}{request.path_qs}"
        try:
            async with self._session.request(
                request.method, target_url,
                headers={k: v for k, v in request.headers.items()
                         if k.lower() not in ("host", "content-length")},
                data=await request.read(),
            ) as resp:
                body = await resp.read()
                return web.Response(
                    status=resp.status,
                    body=body,
                    headers={k: v for k, v in resp.headers.items()
                             if k.lower() not in ("transfer-encoding", "content-encoding")},
                )
        except Exception as e:
            logger.debug("Proxy error: %s", e)
            return web.json_response(
                {"error": "GoPro unreachable", "detail": str(e)}, status=502)

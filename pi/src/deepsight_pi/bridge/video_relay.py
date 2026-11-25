"""Forward camera UDP packets to the same registered Host as telemetry."""

import asyncio
import logging

from deepsight_pi.bridge.host_link import HostLink

logger = logging.getLogger("pi.bridge.video")


class VideoRelay(asyncio.DatagramProtocol):
    def __init__(self, host: HostLink, camera_address: str, port: int):
        self._host = host
        self._camera_address = camera_address
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self, local_addr=("0.0.0.0", self._port))

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        destination = self._host.return_address
        if addr[0] == self._camera_address and destination and self._transport:
            self._transport.sendto(data, (destination, self._port))

    def error_received(self, exc: Exception):
        logger.warning("Video relay UDP error: %s", exc)

    def stop(self):
        if self._transport:
            self._transport.close()
            self._transport = None

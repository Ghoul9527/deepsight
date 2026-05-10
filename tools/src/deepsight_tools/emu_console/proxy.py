"""UDP MITM proxy — intercepts Host↔Pi traffic for signal injection/interception.

Sits between Host and Pi on the UDP command/telemetry channel:

    Host ──UDP──▶ proxy.py (:5100) ──UDP──▶ Pi (:pi_udp_port)
    Host ◀──UDP── proxy.py (:5100) ◀──UDP── Pi

When sensors are hijacked (upstream), fake telemetry replaces real Pi data.
When commands are hijacked (downstream), commands are logged but not forwarded.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from deepsight_shared.protocol import Message

logger = logging.getLogger("emu.proxy")

UPSTREAM_TYPES = {"tel.imu", "tel.depth", "tel.env", "tel.leak",
                  "tel.winch_state", "tel.gopro_status", "tel.pi_status"}

DOWNSTREAM_TYPES = {"cmd.servo.set", "cmd.winch.set", "cmd.winch.stop",
                    "cmd.lighting.set", "cmd.gopro.record", "cmd.gopro.mode",
                    "sys.safety"}


class UdpProxy:
    """Async UDP man-in-the-middle proxy.

    Usage:
        proxy = UdpProxy(
            listen_port=5100,        # Host sends here
            pi_addr="192.168.1.100", # Real Pi address
            pi_port=5100,            # Real Pi UDP port
        )
        proxy.set_injector(callback)  # called to get fake upstream messages
        proxy.set_interceptor(callback)  # called for downstream messages
        await proxy.start()
    """

    def __init__(self, listen_port: int = 5100,
                 pi_addr: str = "127.0.0.1", pi_port: int = 5100,
                 host_addr: str = "127.0.0.1", host_port: int = 5000):
        self._listen_port = listen_port
        self._pi_addr = pi_addr
        self._pi_port = pi_port
        self._host_addr = host_addr
        self._host_port = host_port
        self._running = False
        self._transport: asyncio.DatagramTransport | None = None

        # Hijack state
        self._upstream_hijack: set[str] = set()  # tel.* types to inject
        self._downstream_hijack: set[str] = set()  # cmd.* types to intercept

        # Callbacks
        self._on_upstream: Callable[[Message], None] | None = None
        self._on_downstream: Callable[[Message], None] | None = None
        self._injector: Callable[[], list[Message]] | None = None
        self._interceptor: Callable[[Message], bool] | None = None

        # Stats
        self.host_to_pi = 0
        self.pi_to_host = 0
        self.injected = 0
        self.intercepted = 0

    # ── Hijack configuration ──

    def set_upstream_hijack(self, msg_type_prefix: str, enabled: bool):
        if enabled:
            self._upstream_hijack.add(msg_type_prefix)
        else:
            self._upstream_hijack.discard(msg_type_prefix)

    def set_downstream_hijack(self, msg_type_prefix: str, enabled: bool):
        if enabled:
            self._downstream_hijack.add(msg_type_prefix)
        else:
            self._downstream_hijack.discard(msg_type_prefix)

    # ── Callbacks ──

    def set_on_upstream(self, cb: Callable[[Message], None]):
        """Called when real upstream message arrives (for logging)."""
        self._on_upstream = cb

    def set_on_downstream(self, cb: Callable[[Message], None]):
        """Called when a downstream command is forwarded (for logging)."""
        self._on_downstream = cb

    def set_injector(self, cb: Callable[[], list[Message]]):
        """Called periodically; should return fake upstream messages to inject."""
        self._injector = cb

    def set_interceptor(self, cb: Callable[[Message], bool]):
        """Called for each downstream command. Return False to block forwarding."""
        self._interceptor = cb

    # ── Lifecycle ──

    async def start(self):
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _ProxyProtocol(self),
            local_addr=("0.0.0.0", self._listen_port),
        )
        self._running = True
        logger.info("UDP proxy listening on :%d → Pi %s:%d",
                      self._listen_port, self._pi_addr, self._pi_port)

    async def stop(self):
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None

    async def inject(self, msg: Message):
        """Inject a fake upstream message to Host."""
        if self._transport:
            data = msg.to_bytes()
            self._transport.sendto(data, (self._host_addr, self._host_port))
            self.injected += 1

    @property
    def upstream_hijack_set(self) -> set[str]:
        return self._upstream_hijack

    @property
    def downstream_hijack_set(self) -> set[str]:
        return self._downstream_hijack

    def _handle_datagram(self, data: bytes, addr: tuple[str, int]):
        """Called by the protocol handler for each received datagram."""
        try:
            msg = Message.from_bytes(data)
        except Exception:
            return

        src_is_host = addr[1] == self._host_port

        if src_is_host:
            self._handle_from_host(msg)
        else:
            self._handle_from_pi(msg)

    def _handle_from_host(self, msg: Message):
        """Host → Pi direction (commands)."""
        # Check interceptor (returns False to block)
        if self._interceptor:
            forward = self._interceptor(msg)
        else:
            forward = not any(msg.type.startswith(p) for p in self._downstream_hijack)

        if forward:
            self._transport.sendto(msg.to_bytes(), (self._pi_addr, self._pi_port))
            self.host_to_pi += 1
        else:
            self.intercepted += 1

        if self._on_downstream:
            self._on_downstream(msg)

    def _handle_from_pi(self, msg: Message):
        """Pi → Host direction (telemetry)."""
        # Check if this telemetry type is hijacked
        hijacked = any(msg.type.startswith(p) for p in self._upstream_hijack)

        if not hijacked:
            self._transport.sendto(msg.to_bytes(), (self._host_addr, self._host_port))
            self.pi_to_host += 1

        if self._on_upstream:
            self._on_upstream(msg)


class _ProxyProtocol(asyncio.DatagramProtocol):
    """Internal protocol handler bridging asyncio UDP to UdpProxy."""

    def __init__(self, proxy: UdpProxy):
        self._proxy = proxy

    def connection_made(self, transport):
        pass

    def datagram_received(self, data, addr):
        self._proxy._handle_datagram(data, addr)

    def error_received(self, exc):
        logger.error("UDP proxy error: %s", exc)

    def connection_lost(self, exc):
        if exc:
            logger.error("UDP proxy connection lost: %s", exc)
        else:
            logger.debug("UDP proxy closed")

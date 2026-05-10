"""Inject test messages into the system for debugging."""

from __future__ import annotations

import logging
import socket

from deepsight_shared.protocol import Message, cmd_servo_set, cmd_winch_set

logger = logging.getLogger("tools.injector")


class MessageInjector:
    def __init__(self, host: str = "127.0.0.1", port: int = 5100):
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def inject(self, msg: Message):
        data = msg.to_bytes()
        self._sock.sendto(data, self._addr)
        logger.debug("Injected: %s", msg.type)

    def inject_servo(self, servo_id: int, angle: float):
        msg = cmd_servo_set("host", servo_id, angle)
        self.inject(msg)

    def inject_winch(self, speed: float):
        msg = cmd_winch_set("host", speed)
        self.inject(msg)

    def close(self):
        self._sock.close()

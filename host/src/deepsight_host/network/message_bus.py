from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Coroutine

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.network.bus")

Handler = Callable[[Message], Coroutine]


class MessageBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard_handlers: list[Handler] = []

    def subscribe(self, msg_type: str, handler: Handler):
        self._handlers[msg_type].append(handler)

    def subscribe_all(self, handler: Handler):
        self._wildcard_handlers.append(handler)

    async def publish(self, msg: Message):
        tasks = []
        for handler in self._handlers.get(msg.type, []):
            tasks.append(asyncio.create_task(handler(msg)))
        for handler in self._wildcard_handlers:
            tasks.append(asyncio.create_task(handler(msg)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

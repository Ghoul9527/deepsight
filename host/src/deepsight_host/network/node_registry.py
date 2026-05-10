from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from deepsight_shared.constants import (
    HEARTBEAT_DEGRADED_TIMEOUT,
    HEARTBEAT_LOST_TIMEOUT,
    SafetyState,
)


@dataclass
class NodeInfo:
    node_id: str
    last_heartbeat: float
    state: SafetyState = SafetyState.NOMINAL
    startup_time: float = 0.0


class NodeRegistry:
    def __init__(self):
        self._nodes: dict[str, NodeInfo] = {}
        self._callbacks: list[Callable[[str, SafetyState, SafetyState], None]] = []

    def register(self, node_id: str):
        now = time.monotonic()
        self._nodes[node_id] = NodeInfo(
            node_id=node_id,
            last_heartbeat=now,
            startup_time=now,
        )

    def heartbeat(self, node_id: str):
        now = time.monotonic()
        if node_id not in self._nodes:
            self.register(node_id)
        self._nodes[node_id].last_heartbeat = now
        self._nodes[node_id].state = SafetyState.NOMINAL

    def on_state_change(self, cb: Callable[[str, SafetyState, SafetyState], None]):
        self._callbacks.append(cb)

    def _transition(self, node_id: str, new_state: SafetyState):
        node = self._nodes.get(node_id)
        if not node or node.state == new_state:
            return
        old_state = node.state
        node.state = new_state
        for cb in self._callbacks:
            cb(node_id, old_state, new_state)

    def check_all(self):
        now = time.monotonic()
        for node_id, info in self._nodes.items():
            elapsed = now - info.last_heartbeat
            if elapsed > HEARTBEAT_LOST_TIMEOUT:
                self._transition(node_id, SafetyState.SAFE)
            elif elapsed > HEARTBEAT_DEGRADED_TIMEOUT:
                self._transition(node_id, SafetyState.DEGRADED)
            else:
                self._transition(node_id, SafetyState.NOMINAL)

    def get_all(self) -> dict[str, NodeInfo]:
        return dict(self._nodes)

    def get(self, node_id: str) -> NodeInfo | None:
        return self._nodes.get(node_id)

    def remove(self, node_id: str):
        self._nodes.pop(node_id, None)

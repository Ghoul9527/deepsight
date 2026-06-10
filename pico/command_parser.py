"""Parse incoming JSON commands from Pi."""

import json


class CommandParser:
    def __init__(self):
        self._handlers = {}

    def register(self, cmd_type: str, handler):
        self._handlers[cmd_type] = handler

    def parse(self, line: str) -> tuple[str, dict] | None:
        try:
            msg = json.loads(line)
            cmd_type = msg.get("type", "")
            payload = msg.get("payload", {})
            return (cmd_type, payload)
        except (ValueError, KeyError, TypeError, MemoryError):
            return None

    def dispatch(self, cmd_type: str, payload: dict) -> dict | None:
        handler = self._handlers.get(cmd_type)
        if handler:
            return handler(payload)
        else:
            print(f"[CMD] Unknown: {cmd_type}")
            return None

"""Serial link to Raspberry Pi over UART."""

import json
import config


class SerialLink:
    def __init__(self):
        self._buffer = ""
        self._mock_mode = config.MOCK_ENABLED
        self._mock_send_queue = []

    def init(self):
        if not self._mock_mode:
            # Future: initialize UART
            pass

    def read_line(self) -> str | None:
        if self._mock_mode:
            # In mock mode, read from stdin (for testing)
            import sys
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.readline().strip()
            return None
        # Future: read from UART
        return None

    def write(self, data: str):
        if self._mock_mode:
            self._mock_send_queue.append(data)
            print(f"[MOCK→Pi] {data}")
        else:
            # Future: write to UART
            pass

    def available(self) -> bool:
        return len(self._mock_send_queue) > 0

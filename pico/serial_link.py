"""Serial link to Raspberry Pi over UART."""

import json
import config


class SerialLink:
    def __init__(self):
        self._buffer = ""
        self._uart = None
        self._mock_mode = config.SERIAL_MOCK
        self._mock_send_queue = []

    def init(self):
        if not self._mock_mode:
            from machine import UART, Pin
            self._uart = UART(
                0,
                baudrate=config.SERIAL_BAUD,
                tx=Pin(16),
                rx=Pin(17),
                bits=8,
                parity=None,
                stop=1,
            )

    def read_line(self) -> str | None:
        if self._mock_mode:
            # In mock mode, read from stdin (for testing)
            import sys
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.readline().strip()
            return None

        if self._uart is None:
            return None
        while self._uart.any():
            b = self._uart.read(1)
            if b is None:
                break
            ch = chr(b[0]) if isinstance(b, bytes) else chr(b)
            if ch == "\n":
                line = self._buffer
                self._buffer = ""
                return line.strip()
            self._buffer += ch
        return None

    def write(self, data: str):
        if self._mock_mode:
            self._mock_send_queue.append(data)
            print(f"[MOCK→Pi] {data}")
        elif self._uart is not None:
            self._uart.write(data + "\n")

    def available(self) -> bool:
        if self._mock_mode:
            return len(self._mock_send_queue) > 0
        return self._uart is not None and self._uart.any() > 0

"""Serial link to Raspberry Pi over USB CDC or GPIO UART.

Hybrid mode: read commands from USB CDC (never blocks), write telemetry
to GPIO UART (never blocks USB protocol stack). Set by config.SERIAL_TELEMETRY.
"""

import gc
import config
from machine import Pin

_LED = Pin(25, Pin.OUT)


class SerialLink:
    def __init__(self):
        self._uart = None
        self._mock_mode = config.SERIAL_MOCK
        self._mock_send_queue = []
        self._usb_mode = getattr(config, "SERIAL_LINK", "uart") == "usb"
        self._telem_uart = (
            self._usb_mode
            and getattr(config, "SERIAL_TELEMETRY", "usb") == "uart"
        )

        # Pre-allocated bytearray buffer for UART mode
        self._buf = bytearray(1024)
        self._buf_len = 0

    def init(self):
        if self._mock_mode:
            return
        if self._usb_mode:
            if self._telem_uart:
                from machine import UART, Pin
                self._uart = UART(
                    0,
                    baudrate=config.SERIAL_BAUD,
                    tx=Pin(config.SERIAL_TX_PIN),
                    rx=Pin(config.SERIAL_RX_PIN),
                    bits=8,
                    parity=None,
                    stop=1,
                )
            return
        if not self._usb_mode:
            from machine import UART, Pin
            self._uart = UART(
                0,
                baudrate=config.SERIAL_BAUD,
                tx=Pin(config.SERIAL_TX_PIN),
                rx=Pin(config.SERIAL_RX_PIN),
                bits=8,
                parity=None,
                stop=1,
            )

    def flush_input(self):
        if self._mock_mode:
            return
        if self._usb_mode:
            import sys
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(64)
            return
        if self._uart is None:
            return
        for _ in range(4):
            if not self._uart.any():
                break
            self._uart.read(64)

    def read_line(self) -> str | None:
        if self._mock_mode:
            import sys
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.readline().strip()
            return None

        if self._usb_mode:
            import sys
            import select
            if not select.select([sys.stdin], [], [], 0)[0]:
                return None
            try:
                line = sys.stdin.readline()
                if line:
                    return line.strip()
            except Exception:
                pass
            return None

        if self._uart is None:
            return None

        # Bulk read all available bytes, then split by newline
        if self._uart.any():
            raw = self._uart.read(self._uart.any())
            if raw:
                if isinstance(raw, bytes):
                    new_len = self._buf_len + len(raw)
                    if new_len <= 1024:
                        self._buf[self._buf_len:new_len] = raw
                        self._buf_len = new_len
                    else:
                        self._buf_len = 0
                        gc.collect()
                        return None

        # Return first complete line in buffer
        if self._buf_len > 0:
            for i in range(self._buf_len):
                if self._buf[i] == 0x0A:
                    line_bytes = bytes(self._buf[:i])
                    tail_len = self._buf_len - i - 1
                    if tail_len > 0:
                        self._buf[0:tail_len] = self._buf[i + 1:self._buf_len]
                    self._buf_len = tail_len
                    try:
                        return line_bytes.decode("ascii", "ignore").strip()
                    except Exception:
                        return None
                    break

        # Overflow protection
        if self._buf_len >= 1024:
            self._buf_len = 0
            gc.collect()

        return None

    def write(self, data: str):
        if self._mock_mode:
            self._mock_send_queue.append(data)
            print("[MOCK->Pi] %s" % data)
            return
        _LED.off()
        if self._telem_uart and self._uart is not None:
            # Write to GPIO UART, never blocks USB
            self._uart.write(data + "\n")
            _LED.on()
            return
        if self._usb_mode:
            import sys
            sys.stdout.write(data + "\n")
            _LED.on()
            return
        if self._uart is not None:
            self._uart.write(data + "\n")
        _LED.on()

    def available(self) -> bool:
        if self._mock_mode:
            return len(self._mock_send_queue) > 0
        return self._uart is not None and self._uart.any() > 0

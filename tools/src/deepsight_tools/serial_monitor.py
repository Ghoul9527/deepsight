"""Serial port monitor for debugging MCU communications.

Supports real serial ports (pyserial) and mock mode (stdin/file replay).
Displays hex dump, ASCII, and parsed JSONL messages with timestamps.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("tools.serial")


class SerialMonitor:
    """Monitor and display serial port traffic.

    Usage:
        monitor = SerialMonitor("/dev/tty.usbserial-110", baud=115200)
        monitor.set_message_callback(lambda msg: print(msg))
        monitor.start()
    """

    def __init__(self, port: str, baud: int = 115200):
        self._port = port
        self._baud = baud
        self._running = False
        self._callback = None
        self._ser = None

    def set_message_callback(self, cb):
        """Set callback for parsed JSONL messages."""
        self._callback = cb

    def start(self):
        """Open port and begin monitoring. Blocks until stop() called from another thread."""
        self._running = True

        if self._port in ("mock", "stdin", "-"):
            self._monitor_mock()
        else:
            self._monitor_real()

    def stop(self):
        self._running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def _monitor_real(self):
        try:
            import serial
        except ImportError:
            logger.error("pyserial not installed. pip install pyserial")
            logger.info("Falling back to mock mode")
            self._monitor_mock()
            return

        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.5)
            logger.info("Serial monitor: %s @ %d baud (connected)", self._port, self._baud)
        except serial.SerialException as e:
            logger.error("Failed to open %s: %s", self._port, e)
            return

        buf = b""
        while self._running:
            try:
                data = self._ser.read(128)
                if data:
                    buf += data
                    buf = self._process_buffer(buf)
            except serial.SerialException as e:
                logger.error("Serial read error: %s", e)
                break

    def _monitor_mock(self):
        """Read from stdin in mock mode."""
        import sys

        logger.info("Serial monitor: mock mode (reading stdin). Ctrl+D to stop.")
        self._ser = None

        buf = b""
        while self._running:
            try:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                buf += line
                buf = self._process_buffer(buf)
            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def _process_buffer(self, buf: bytes) -> bytes:
        """Extract complete JSONL lines from buffer, print hex+ASCII dumps."""
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue

            ts = time.strftime("%H:%M:%S")
            try:
                text = line.decode("utf-8", errors="replace")
            except Exception:
                text = repr(line)

            # Print timestamp + raw
            print(f"[{ts}] {text}")

            # Try to parse as JSON and forward to callback
            if self._callback:
                try:
                    import json
                    msg = json.loads(line.decode("utf-8"))
                    self._callback(msg)
                except Exception:
                    pass

        return buf

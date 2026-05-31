"""Pico main - entry point for the control firmware.

USB CDC = runtime data (commands + telemetry), full duplex.
GPIO UART = development REPL via os.dupterm (mpremote access).
"""

import os
import sys
import time

import config
from machine import Pin
from serial_link import SerialLink
from control_loop import ControlLoop

_LED = Pin(25, Pin.OUT)


def _setup_dev_uart():
    """Duplicate REPL to GPIO UART for mpremote development access."""
    if config.MOCK_ENABLED:
        return
    try:
        from machine import UART, Pin
        uart = UART(
            0,
            baudrate=config.SERIAL_BAUD,
            tx=Pin(config.SERIAL_TX_PIN),
            rx=Pin(config.SERIAL_RX_PIN),
            bits=8,
            parity=None,
            stop=1,
        )
        os.dupterm(uart)
    except Exception as e:
        print("[PICO] dupterm failed: %s" % e)


def main():
    print("=== DeepSight Pico Controller ===")
    print("Mock mode: %s" % ("enabled" if config.MOCK_ENABLED else "disabled"))
    print("Link mode: %s" % getattr(config, "SERIAL_LINK", "uart"))
    print("Dev UART: REPL dupterm on GP%d/GP%d" % (config.SERIAL_TX_PIN, config.SERIAL_RX_PIN))
    print("")

    _LED.on()

    _setup_dev_uart()

    print("[PICO] creating SerialLink...")
    serial = SerialLink()
    print("[PICO] creating ControlLoop...")
    loop = ControlLoop(serial)
    print("[PICO] created")

    # Startup delay: give gateway time to connect before sending data
    if not config.MOCK_ENABLED:
        print("[PICO] waiting 0.5s...")
        time.sleep(0.5)

    try:
        loop.init()
        loop.run()
    except KeyboardInterrupt:
        print("\n[PICO] Shutting down...")
        loop.stop()
    except Exception as e:
        print("[PICO] FATAL: %s" % e)
        import sys
        sys.print_exception(e)


if __name__ == "__main__":
    main()

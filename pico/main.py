"""Pico main — entry point for the control firmware.

Runs on Raspberry Pi Pico with MicroPython or CPython (mock mode).
"""

import sys
import time

import config
from serial_link import SerialLink
from control_loop import ControlLoop


def main():
    print("=== DeepSight Pico Controller ===")
    print(f"Mock mode: {'enabled' if config.MOCK_ENABLED else 'disabled'}")
    print("Control loop: 50 Hz")
    print("")

    serial = SerialLink()
    loop = ControlLoop(serial)

    try:
        loop.init()
        loop.run()
    except KeyboardInterrupt:
        print("\n[PICO] Shutting down...")
        loop.stop()


if __name__ == "__main__":
    main()

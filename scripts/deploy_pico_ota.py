#!/usr/bin/env python3
"""Deploy Pico firmware via OTA over USB CDC.

Usage:
    python3 -m deepsight_pi.ota_sender pico/main.py pico/config.py [pico/lib/*.py ...]

The script stops the Pi service, runs the OTA transfer, then restarts the service.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
import time

from deepsight_pi.config import PiConfig
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.ota_sender import OTASender

logger = logging.getLogger("pi.ota.cli")

SERVICE_NAME = "deepsight-pi"
PICO_DEVICE = "/dev/ttyACM0"
PICO_REBOOT_TIMEOUT = 15.0


def main():
    parser = argparse.ArgumentParser(description="OTA deploy to Pico")
    parser.add_argument("files", nargs="+", help="Pico .py files to send")
    parser.add_argument("--no-restart", action="store_true",
                        help="Don't restart the Pi service after OTA")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Verify all files exist
    for path in args.files:
        if not os.path.isfile(path):
            print(f"ERROR: File not found: {path}")
            sys.exit(1)

    print(f"OTA deploy: {len(args.files)} file(s)")
    for f in args.files:
        size = os.path.getsize(f)
        print(f"  {os.path.basename(f):30s} {size:6d} bytes")

    # Stop the running service
    print(f"\nStopping {SERVICE_NAME} service...")
    subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME], check=True)
    subprocess.run(["sudo", "systemctl", "is-active", "--quiet", SERVICE_NAME],
                   check=False)
    print("Service stopped.")

    # Run OTA
    config = PiConfig()
    pico_link = PicoLink(config)

    async def run_ota() -> bool:
        try:
            await pico_link.start()
            sender = OTASender(pico_link)
            ok = await sender.execute(args.files)
            return ok
        finally:
            await pico_link.stop()

    success = False
    try:
        success = asyncio.run(run_ota())
    except Exception as e:
        logger.error("OTA failed: %s", e)

    # Restart service
    if not args.no_restart:
        if success:
            print(f"\nWaiting for Pico to reboot (checking {PICO_DEVICE})...")
            deadline = time.time() + PICO_REBOOT_TIMEOUT
            disappeared = False
            reappeared = False
            while time.time() < deadline:
                exists = os.path.exists(PICO_DEVICE)
                if not disappeared and not exists:
                    print("Pico device disappeared (resetting)...")
                    disappeared = True
                if disappeared and exists:
                    elapsed = PICO_REBOOT_TIMEOUT - (deadline - time.time())
                    print("Pico device reappeared after %.1fs" % elapsed)
                    reappeared = True
                    break
                time.sleep(0.3)
            if not reappeared:
                print("WARNING: Pico device did not return within %ds" %
                      PICO_REBOOT_TIMEOUT)
        print(f"\nRestarting {SERVICE_NAME} service...")
        subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)
        time.sleep(1)
        subprocess.run(["sudo", "systemctl", "is-active", "--quiet", SERVICE_NAME],
                       check=False)

    if success:
        print("OTA deploy complete. Pico is rebooting with new firmware.")
        sys.exit(0)
    else:
        print("OTA deploy FAILED.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Flash MicroPython firmware to Raspberry Pi Pico."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("tools.flash_pico")


def flash_pico(project_dir: str = "pico", drive: str = "/Volumes/RPI-RP2"):
    """Copy main.py and lib/ to Pico's MicroPython filesystem."""
    src = Path(project_dir)
    if not Path(drive).exists():
        logger.error("Pico drive not found: %s", drive)
        logger.info("Put Pico in bootloader mode (hold BOOTSEL while plugging in)")
        return False

    # Copy main.py
    shutil.copy2(src / "main.py", Path(drive) / "main.py")
    logger.info("Copied main.py")

    # Copy config
    shutil.copy2(src / "config.py", Path(drive) / "config.py")

    # Copy library
    lib_dest = Path(drive) / "lib"
    lib_dest.mkdir(exist_ok=True)
    for f in (src / "lib").glob("*.py"):
        shutil.copy2(f, lib_dest / f.name)
        logger.info("Copied lib/%s", f.name)

    # Copy core modules
    for f in src.glob("*.py"):
        if f.name not in ("main.py", "config.py"):
            shutil.copy2(f, Path(drive) / f.name)
            logger.info("Copied %s", f.name)

    logger.info("Pico flashed successfully!")
    return True

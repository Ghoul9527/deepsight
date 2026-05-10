"""Deploy Pi code to a remote Raspberry Pi."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("tools.deploy_pi")


def deploy_pi(host: str = "raspberrypi.local", user: str = "pi",
              src_dir: str = "pi", dest_dir: str = "~/deepsight/pi",
              restart: bool = True):
    """rsync Pi code and optionally restart the service."""
    src = Path(src_dir)

    cmd = [
        "rsync", "-avz", "--delete",
        "--exclude=__pycache__",
        "--exclude=*.pyc",
        "--exclude=.venv",
        f"{src}/",
        f"{user}@{host}:{dest_dir}/",
    ]

    logger.info("Deploying to %s@%s...", user, host)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("rsync failed: %s", result.stderr)
        return False

    logger.info("Deployed successfully!")

    if restart:
        restart_cmd = [
            "ssh", f"{user}@{host}",
            f"cd {dest_dir} && python -m deepsight_pi.main &"
        ]
        subprocess.run(restart_cmd)
        logger.info("Service restarted on Pi")

    return True

"""Structured JSON logging setup."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

import yaml


def setup_logging(config_path: str = "configs/logging.yaml",
                  log_dir: str | None = None):
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f)

        # Create log directories for all file handlers
        for handler_cfg in config.get("handlers", {}).values():
            filename = handler_cfg.get("filename", "")
            if filename:
                Path(filename).parent.mkdir(parents=True, exist_ok=True)

        logging.config.dictConfig(config)
    else:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

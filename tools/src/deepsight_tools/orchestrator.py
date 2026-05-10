"""Orchestrator — starts/stops all nodes for mock mode development."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("tools.orchestrator")


class NodeProcess:
    def __init__(self, name: str, cmd: list[str], cwd: str | None = None):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.process: subprocess.Popen | None = None

    def start(self):
        logger.info("Starting %s: %s", self.name, " ".join(self.cmd))
        self.process = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def stop(self):
        if self.process:
            logger.info("Stopping %s", self.name)
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None


class Orchestrator:
    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root) if project_root else Path.cwd()
        self._nodes: list[NodeProcess] = []

    def start_all_mock(self):
        """Start all nodes in mock mode (no hardware required)."""
        logger.info("Starting all nodes in mock mode...")

        # Host node (GUI — start first so network is ready)
        self._nodes.append(NodeProcess(
            "host",
            [sys.executable, "-m", "deepsight_host.main"],
            str(self._root),
        ))

        # Pi node
        self._nodes.append(NodeProcess(
            "pi",
            [sys.executable, "-m", "deepsight_pi.main"],
            str(self._root),
        ))

        # Pico node
        self._nodes.append(NodeProcess(
            "pico",
            [sys.executable, str(self._root / "pico" / "main.py")],
            str(self._root),
        ))

        # STM32 (mock, compiled)
        stm32_build_dir = self._root / "stm32" / "build"
        stm32_binary = stm32_build_dir / "stm32_winch.elf"
        if stm32_binary.exists():
            self._nodes.append(NodeProcess(
                "stm32",
                [str(stm32_binary)],
                str(self._root),
            ))
        else:
            logger.warning("STM32 binary not found, skipping (build with 'make -C stm32 MOCK_MODE=1')")

        # Start all
        for node in self._nodes:
            node.start()

        time.sleep(0.5)
        logger.info("All nodes started. Press Ctrl+C to stop.")

        # Monitor
        try:
            while True:
                time.sleep(1)
                for node in self._nodes:
                    if not node.running:
                        logger.warning("%s process exited (code=%s)", node.name, node.process.returncode)
        except KeyboardInterrupt:
            self.stop_all()

    def stop_all(self):
        logger.info("Stopping all nodes...")
        for node in reversed(self._nodes):
            node.stop()
        logger.info("All nodes stopped.")

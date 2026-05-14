"""Startup self-check — verifies Host→Pi→Camera→Video chain at boot."""

from __future__ import annotations

import logging
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger("host.diagnostics")


class Step:
    """Single check step."""
    def __init__(self, name: str, label: str):
        self.name = name
        self.label = label
        self.status: str = "pending"  # pending | checking | ok | fail
        self.detail: str = ""


class StartupCheck(QObject):
    """Runs a sequence of diagnostic checks after Host startup.

    Checks:
      1. UDP ping → Pi (round-trip)
      2. Pi startup status (GoPro + capture + host_link)
      3. Video preview (frames arriving)

    Results are emitted via signals; MainWindow shows them in the status bar.
    """

    check_started = Signal(str)   # step name
    check_result = Signal(str, str, str)  # name, status, detail
    all_done = Signal(bool)       # overall ok

    def __init__(self, parent=None):
        super().__init__(parent)
        self._send_udp: Callable | None = None
        self._send_startup_check: Callable | None = None
        self._steps: list[Step] = []
        self._ping_seq = 0
        self._pong_received = False
        self._pi_startup_ok = False
        self._got_frame = False
        self._started = False

    def set_send_udp(self, fn: Callable):
        """Register the function used to send UDP ping to Pi."""
        self._send_udp = fn

    def set_send_startup_check(self, fn: Callable):
        """Register the function used to request Pi startup status."""
        self._send_startup_check = fn

    def on_pong(self):
        """Called when sys.pong is received."""
        self._pong_received = True

    def on_startup_status(self, checks: dict):
        """Called when sys.startup_status is received from Pi."""
        self._pi_startup_ok = all(c.get("ok", False) for c in checks.values())

    def on_frame_received(self):
        """Called when the first video frame arrives."""
        self._got_frame = True

    def start(self):
        """Begin the startup check sequence."""
        if self._started:
            return
        self._started = True

        self._steps = [
            Step("ping", "Pi UDP"),
            Step("pi_status", "Pi → Camera"),
            Step("video", "Video Preview"),
        ]

        # Phase 1: UDP ping
        self._check_ping()

        # Phase 2: request Pi startup status after ping
        QTimer.singleShot(1500, lambda: (
            self._send_startup_check() if self._send_startup_check else None))
        QTimer.singleShot(3000, self._check_pi_status)

        # Phase 3: wait for video (delayed)
        QTimer.singleShot(6000, self._check_video)

    def _check_ping(self):
        step = self._steps[0]
        step.status = "checking"
        self.check_started.emit(step.name)

        # Wait 200ms for pong, then check
        QTimer.singleShot(300, lambda: self._evaluate_ping(step))

        if self._send_udp:
            self._send_udp()

    def _evaluate_ping(self, step: Step):
        if self._pong_received:
            step.status = "ok"
            step.detail = "connected"
        else:
            step.status = "fail"
            step.detail = "no response"
        self.check_result.emit(step.name, step.status, step.detail)

    def _check_pi_status(self):
        step = self._steps[1]
        if self._pi_startup_ok:
            step.status = "ok"
            step.detail = "GoPro ready"
        else:
            step.status = "fail"
            step.detail = "waiting for camera"
        self.check_result.emit(step.name, step.status, step.detail)

    def _check_video(self):
        step = self._steps[2]
        if self._got_frame:
            step.status = "ok"
            step.detail = "frames arriving"
        else:
            step.status = "fail"
            step.detail = "no frames"
        self.check_result.emit(step.name, step.status, step.detail)

        # Final evaluation
        all_ok = all(s.status == "ok" for s in self._steps)
        self.all_done.emit(all_ok)

    def summary(self) -> str:
        """Return a one-line status summary."""
        parts = []
        for s in self._steps:
            icon = {"ok": "✓", "fail": "✗", "checking": "…", "pending": "○"}.get(s.status, "?")
            parts.append(f"{icon} {s.label}")
        return "  ".join(parts)

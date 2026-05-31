#!/usr/bin/env python3
"""Visual gamepad tester — like hardwaretester.com/gamepad for F310 mapping verification.

Reads from pygame (or F310 USB bridge as fallback) and shows:
  - 6 analog axes as live bar graphs
  - 13 buttons as colored indicators (green=pressed)
  - D-pad as a 3x3 grid

Button indices are labeled so you can press each physical button and
see which index lights up — verifying the mapping at a glance.

Usage: python scripts/gamepad_tester.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QGridLayout, QGroupBox, QFrame,
)

BRIDGE_PATH = "/usr/local/bin/deepsight_f310_bridge"

# ── Button names (SDL2 order for F310 D-mode) ──
BUTTON_NAMES = ["X", "A", "B", "Y", "LB", "RB", "LT(d)", "RT(d)",
                "Back", "Start", "L3", "R3", "Logo"]

AXIS_NAMES = ["Left X", "Left Y", "Right X", "Right Y", "LT(analog)", "RT(analog)"]

# ── Colors ──
BAR_BG = QColor(40, 40, 40)
BAR_FG = QColor(0, 180, 255)
BUTTON_ON = QColor(0, 220, 80)
BUTTON_OFF = QColor(60, 60, 60)
DPAD_ON = QColor(255, 180, 0)
DPAD_OFF = QColor(50, 50, 50)
TEXT_COLOR = QColor(200, 200, 200)


class AxisBar(QWidget):
    """Horizontal bar showing axis value from -1 to 1."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self._value = 0.0
        self.setFixedHeight(32)

    def set_value(self, v: float):
        self._value = max(-1.0, min(1.0, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid = w // 2

        # Background
        p.fillRect(0, 0, w, h, BAR_BG)
        # Center line
        p.setPen(QPen(QColor(80, 80, 80), 1))
        p.drawLine(mid, 0, mid, h)

        # Value bar
        bar_w = int(abs(self._value) * mid)
        if bar_w > 0:
            if self._value > 0:
                p.fillRect(mid, 4, bar_w, h - 8, BAR_FG)
            else:
                p.fillRect(mid - bar_w, 4, bar_w, h - 8, BAR_FG)

        # Text
        p.setPen(TEXT_COLOR)
        p.setFont(QFont("Menlo", 10))
        text = f"{self._name}: {self._value:+.3f}"
        p.drawText(QRectF(8, 0, w - 16, h), Qt.AlignmentFlag.AlignVCenter, text)
        p.end()


class DPadWidget(QWidget):
    """3x3 grid showing D-pad direction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hat = (0, 0)  # (x, y)
        self.setFixedSize(100, 100)

    def set_hat(self, x: int, y: int):
        self._hat = (x, y)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width() // 3
        for row in range(3):
            for col in range(3):
                x, y = col * s, row * s
                # Map: row 0 = up, row 2 = down, col 0 = left, col 2 = right
                is_on = False
                if row == 0 and col == 1 and self._hat[1] == 1:
                    is_on = True  # Up
                elif row == 2 and col == 1 and self._hat[1] == -1:
                    is_on = True  # Down
                elif row == 1 and col == 0 and self._hat[0] == -1:
                    is_on = True  # Left
                elif row == 1 and col == 2 and self._hat[0] == 1:
                    is_on = True  # Right

                c = DPAD_ON if is_on else DPAD_OFF
                p.fillRect(x + 2, y + 2, s - 4, s - 4, c)

        p.end()


class GamepadTester(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gamepad Tester — DeepSight")
        self.setMinimumSize(520, 500)

        # State
        self._axes = [0.0] * 6
        self._buttons = [0] * 13
        self._hat = [0, 0]
        self._raw = "00000000"
        self._connected = False
        self._lock = threading.Lock()

        # Bridge process
        self._proc: subprocess.Popen | None = None

        self._build_ui()
        self._start_input()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Status
        self._status = QLabel("Searching for controller...")
        self._status.setStyleSheet("color: #888; font: 13px;")
        layout.addWidget(self._status)

        # Raw HID bytes
        self._raw_label = QLabel("raw: --")
        self._raw_label.setStyleSheet("color: #ff0; font: 14px; font-family: Menlo;")
        layout.addWidget(self._raw_label)

        # ── Axes ──
        axes_group = QGroupBox("Analog Axes")
        axes_layout = QVBoxLayout(axes_group)
        self._bars = []
        for name in AXIS_NAMES:
            bar = AxisBar(name)
            axes_layout.addWidget(bar)
            self._bars.append(bar)
        layout.addWidget(axes_group)

        # ── D-pad ──
        dpad_group = QGroupBox("D-Pad (Hat)")
        dpad_layout = QHBoxLayout(dpad_group)
        dpad_layout.addStretch()
        self._dpad = DPadWidget()
        dpad_layout.addWidget(self._dpad)
        self._hat_label = QLabel("center")
        self._hat_label.setStyleSheet("color: #aaa;")
        dpad_layout.addWidget(self._hat_label)
        dpad_layout.addStretch()
        layout.addWidget(dpad_group)

        # ── Buttons ──
        btn_group = QGroupBox("Buttons (press to identify)")
        btn_grid = QGridLayout(btn_group)
        btn_grid.setSpacing(6)
        self._btn_widgets = []
        for i, name in enumerate(BUTTON_NAMES):
            lbl = QLabel(f"[{i}] {name}")
            led = QFrame()
            led.setFixedSize(16, 16)
            led.setFrameStyle(QFrame.Shape.Box)
            led.setStyleSheet(f"background: {BUTTON_OFF.name()}; border-radius: 8px;")
            row, col = i // 4, i % 4
            hbox = QHBoxLayout()
            hbox.addWidget(led)
            hbox.addWidget(lbl)
            hbox.addStretch()
            btn_grid.addLayout(hbox, row, col)
            self._btn_widgets.append((led, lbl))
        layout.addWidget(btn_group)

        layout.addStretch()

    def _start_input(self):
        # Try pygame first
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
                name = self._joystick.get_name()
                self._status.setText(f"Connected: {name} (pygame)")
                self._connected = True
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._poll_pygame)
                self._timer.start(20)
                return
        except Exception:
            pass

        # Fall back to F310 USB bridge — start async, don't block
        if os.path.exists(BRIDGE_PATH):
            try:
                self._proc = subprocess.Popen(
                    [BRIDGE_PATH],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                self._bridge_ready = False
                # Use timer to check for first data without blocking
                QTimer.singleShot(200, self._check_bridge_ready)
                return
            except Exception as e:
                if self._proc:
                    self._proc.terminate()
                    self._proc = None
                self._status.setText(f"Bridge start failed: {e}")

        self._status.setText("No controller found (pygame + bridge both failed)")

    def _check_bridge_ready(self):
        """Check if bridge produced first JSON line (non-blocking)."""
        if self._bridge_ready:
            return
        if not self._proc or self._proc.poll() is not None:
            self._status.setText("Bridge exited — F310 not connected?")
            return

        try:
            import select
            ready, _, _ = select.select([self._proc.stdout], [], [], 0)
            if ready:
                line = self._proc.stdout.readline()
                if line:
                    state = json.loads(line)
                    with self._lock:
                        self._axes = state.get("axes", [0.0] * 6)
                        self._buttons = state.get("buttons", [0] * 13)
                        self._hat = state.get("hat", [0, 0])

                    self._bridge_ready = True
                    self._connected = True
                    self._status.setText("Connected: Logitech F310 (USB bridge)")
                    self._status.setStyleSheet("color: #0f0; font: 13px;")

                    self._reader_thread = threading.Thread(
                        target=self._read_bridge, daemon=True)
                    self._reader_thread.start()
                    self._timer = QTimer(self)
                    self._timer.timeout.connect(self._poll_bridge)
                    self._timer.start(20)
                    return
        except Exception:
            pass

        # Not ready yet — retry in 200ms
        QTimer.singleShot(200, self._check_bridge_ready)

    def _read_bridge(self):
        """Background thread: read JSON lines from bridge stdout."""
        while self._proc and self._proc.poll() is None:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    break
                state = json.loads(line)
                with self._lock:
                    self._axes = state.get("axes", [0.0] * 6)
                    self._buttons = state.get("buttons", [0] * 13)
                    self._hat = state.get("hat", [0, 0])
                    self._raw = state.get("raw", "")
            except Exception:
                pass

    def _poll_pygame(self):
        try:
            import pygame
            pygame.event.pump()
        except Exception:
            return

        for i in range(min(6, self._joystick.get_numaxes())):
            v = self._joystick.get_axis(i)
            if abs(v) < 0.05:
                v = 0.0
            self._axes[i] = v
        for i in range(min(13, self._joystick.get_numbuttons())):
            self._buttons[i] = int(self._joystick.get_button(i))
        if self._joystick.get_numhats() > 0:
            self._hat = list(self._joystick.get_hat(0))
        self._update_ui()

    def _poll_bridge(self):
        with self._lock:
            axes = list(self._axes)
            buttons = list(self._buttons)
            hat = list(self._hat)
            raw = self._raw
        self._axes = axes
        self._buttons = buttons
        self._hat = hat
        self._raw = raw
        self._update_ui()

    def _update_ui(self):
        # Raw HID bytes with byte labels
        raw = getattr(self, '_raw', '00000000')
        if len(raw) >= 16:
            parts = [f"b0={raw[0:2]}", f"b1={raw[2:4]}", f"b2={raw[4:6]}", f"b3={raw[6:8]}",
                     f"b4={raw[8:10]}", f"b5={raw[10:12]}", f"b6={raw[12:14]}", f"b7={raw[14:16]}"]
            self._raw_label.setText(" | ".join(parts))
        else:
            self._raw_label.setText(f"raw: {raw}")

        for i, bar in enumerate(self._bars):
            bar.set_value(self._axes[i] if i < len(self._axes) else 0.0)

        for i, (led, lbl) in enumerate(self._btn_widgets):
            on = bool(self._buttons[i]) if i < len(self._buttons) else False
            color = BUTTON_ON.name() if on else BUTTON_OFF.name()
            led.setStyleSheet(f"background: {color}; border-radius: 8px;")
            if on:
                lbl.setStyleSheet("color: #0f0; font-weight: bold;")
            else:
                lbl.setStyleSheet(f"color: {TEXT_COLOR.name()};")

        self._dpad.set_hat(self._hat[0], self._hat[1])
        hx, hy = self._hat
        hat_text = {
            (0, 0): "center", (0, 1): "UP", (0, -1): "DOWN",
            (-1, 0): "LEFT", (1, 0): "RIGHT",
            (1, 1): "UP-RIGHT", (-1, 1): "UP-LEFT",
            (1, -1): "DOWN-RIGHT", (-1, -1): "DOWN-LEFT",
        }.get((hx, hy), f"({hx},{hy})")
        self._hat_label.setText(hat_text)

    def closeEvent(self, event):
        if self._proc:
            self._proc.terminate()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    tester = GamepadTester()
    tester.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

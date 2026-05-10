"""Game controller / joystick input for manual servo and winch control.

Supports any USB gamepad recognised by pygame (Xbox, PlayStation, etc.).
Maps axes and buttons to the control panel signals.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QTimer, Signal, QObject

logger = logging.getLogger("host.control.controller")


class GameController(QObject):
    """Reads a USB game controller and emits control signals.

    Standard mapping (Xbox / PlayStation layout):
      Left stick X  → pan servo angle
      Left stick Y  → tilt servo angle
      Right stick Y → winch speed/position
      B / Circle    → emergency stop
      Start         → toggle tracking mode
    """

    pan_changed = Signal(float)
    tilt_changed = Signal(float)
    winch_speed_changed = Signal(float)
    e_stop = Signal()
    tracking_toggle = Signal()

    _PAN_CENTER = 90.0
    _PAN_RANGE = 60.0    # ±60° from center
    _TILT_CENTER = 90.0
    _TILT_RANGE = 60.0
    _DEAD_ZONE = 0.08

    def __init__(self, poll_hz: int = 50, parent=None):
        super().__init__(parent)
        self._joystick = None
        self._connected = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._poll_hz = poll_hz
        self._e_stop_pressed = False
        self._start_pressed = False

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> bool:
        """Initialise pygame joystick subsystem. Returns True on success."""
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
        except (ImportError, Exception) as e:
            logger.info("Game controller: %s", e)
            return False

        count = pygame.joystick.get_count()
        if count == 0:
            logger.info("Game controller: no joystick detected")
            return False

        self._joystick = pygame.joystick.Joystick(0)
        self._joystick.init()
        self._connected = True
        logger.info("Game controller connected: %s (axes=%d, buttons=%d)",
                     self._joystick.get_name(),
                     self._joystick.get_numaxes(),
                     self._joystick.get_numbuttons())

        self._timer.start(1000 // self._poll_hz)
        return True

    def stop(self):
        self._timer.stop()
        if self._joystick is not None:
            self._joystick.quit()
            self._joystick = None
        self._connected = False
        logger.info("Game controller: disconnected")

    def _poll(self):
        """Poll joystick axes and buttons."""
        if not self._connected or self._joystick is None:
            return

        try:
            import pygame
            pygame.event.pump()
        except Exception:
            return

        # ── Axes ──
        try:
            lx = self._joystick.get_axis(0)  # left X
            ly = self._joystick.get_axis(1)  # left Y
            rx = self._joystick.get_axis(2)  # right X
            ry = self._joystick.get_axis(3)  # right Y
        except Exception:
            return

        # Pan from left stick X
        if abs(lx) > self._DEAD_ZONE:
            pan = self._PAN_CENTER + lx * self._PAN_RANGE
            self.pan_changed.emit(float(pan))

        # Tilt from left stick Y (inverted: up = negative Y)
        if abs(ly) > self._DEAD_ZONE:
            tilt = self._TILT_CENTER + (-ly) * self._TILT_RANGE
            self.tilt_changed.emit(float(tilt))

        # Winch speed from right stick Y
        if abs(ry) > self._DEAD_ZONE:
            self.winch_speed_changed.emit(float(-ry))

        # ── Buttons ──
        try:
            buttons = self._joystick.get_numbuttons()
        except Exception:
            return

        if buttons > 1:
            # B button (index 1 on both Xbox and PS) → E-stop
            b_pressed = self._joystick.get_button(1)
            if b_pressed and not self._e_stop_pressed:
                self._e_stop_pressed = True
                self.e_stop.emit()
                logger.warning("Game controller: E-STOP triggered")
            elif not b_pressed:
                self._e_stop_pressed = False

        if buttons > 7:
            # Start button → toggle tracking mode
            start = self._joystick.get_button(7)
            if start and not self._start_pressed:
                self._start_pressed = True
                self.tracking_toggle.emit()
                logger.info("Game controller: tracking toggle")
            elif not start:
                self._start_pressed = False


def discover_controller() -> str | None:
    """Return the name of the first connected game controller, or None."""
    try:
        import pygame
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            j = pygame.joystick.Joystick(0)
            name = j.get_name()
            j.quit()
            return name
    except Exception:
        pass
    return None

"""Gamepad input service — config-driven mapping with multi-backend support.

All gamepad input flows through this layer. Business logic never touches pygame
or raw button indices directly — everything is mapped through config.

Backends (tried in order):
  1. pygame (SDL2) — primary backend on Windows/Linux for all controllers.
  2. GCController bridge (macOS) — native GameController.framework via signed
     Swift helper. Apple Development signing is sufficient.
  3. Chrome WebSocket bridge (macOS) — fallback using Chrome's Web Gamepad API.
     No signing required, but needs Chrome running.
  4. F310 USB bridge — deprecated (broken on macOS 26+, kernel HIDRM block).

Architecture:
  GameController (this file)  →  signals  →  Host app / control pipeline
  Config-driven mapping; no controller specifics hardcoded in business logic.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from enum import Enum
from typing import Any

from PySide6.QtCore import QTimer, Signal, QObject

logger = logging.getLogger("host.control.controller")

# Chrome WebSocket bridge — macOS 26+ HIDRM workaround.
# Uses Chrome's Web Gamepad API → local WebSocket → stdout JSON.
# Chrome has Developer ID signing, bypassing HIDRM entirely.
_CHROME_WS_BRIDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
    "scripts", "chrome_ws_bridge.py",
)

# F310 D-mode USB bridge — macOS-only fallback, F310-specific.
# Installed by scripts/setup_f310_bridge.sh with setuid root.
_USB_BRIDGE_PATH = "/usr/local/bin/deepsight_f310_bridge"

# GCController bridge — macOS native GameController.framework.
# Works with Apple Development signing (NSApplication run loop required).
# Compiled Swift binary, outputs SDL2-compatible JSON to stdout.
_GC_BRIDGE_PATH = "/usr/local/bin/deepsight_gc_bridge"


class LockState(Enum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"


# ── Fallback mapping (DirectInput / F310 layout, SDL2 button order) ──
# Button indices match SDL2 / pygame convention:
#   0=A, 1=B, 2=X, 3=Y, 4=LB, 5=RB, 6=Back, 7=Start, 8=L3, 9=R3, 10=Home,
#   11=LT (digital), 12=RT (digital)
_FALLBACK_MAPPING: dict[str, Any] = {
    "name_patterns": [],
    "axes": {
        "winch": {"axis": 1, "invert": False},
        "plate_yaw": {"axis": 0, "invert": False},
        "gimbal_pitch": {"axis": 3, "invert": True},
        "gimbal_yaw": {"axis": 2, "invert": False},
    },
    "buttons": {
        "drop_to_3m": 4, "body_recenter": 8, "gimbal_recenter": 9,
        "all_recenter": 10, "tracking": 5, "record": 1,
        "hud": 2, "roll_recenter": 3, "preset": 0,
        "e_stop": 6, "lock": 7,
        "light_down": 11, "light_up": 12,
    },
    "dpad": {
        "winch_sens_up": [0, 1], "winch_sens_down": [0, -1],
        "plate_sens_left": [-1, 0], "plate_sens_right": [1, 0],
    },
}


def _match_mapping(name: str, mappings: dict) -> dict[str, Any]:
    """Return the mapping whose name_patterns matches the controller name, or generic/fallback."""
    name_lower = name.lower()
    for key, m in mappings.items():
        patterns = m.get("name_patterns", [])
        for pat in patterns:
            if pat.lower() in name_lower:
                logger.info("Controller mapping: %s (matched '%s')", key, pat)
                return m
    if "generic" in mappings:
        return mappings["generic"]
    return _FALLBACK_MAPPING


def _get_axis_cfg(mapping: dict, name: str) -> dict:
    return mapping.get("axes", {}).get(name, {})


def _get_button_idx(mapping: dict, name: str) -> int | None:
    return mapping.get("buttons", {}).get(name)


class GameController(QObject):
    """Reads a USB gamepad and emits typed control signals.

    Mapping is selected automatically from the controller name via config patterns.
    Falls back to DirectInput/F310 layout when no pattern matches.

    Lock / safety:
      - System starts LOCKED; all stick inputs are ignored until Start is pressed.
      - Back (E-stop) is always active regardless of lock state.
      - All auto-actions are cancelled on E-stop or re-lock.
    """

    # ── Analog axes ──
    winch_speed_changed = Signal(float)       # -1..1, positive = reel in (ascend)
    plate_yaw_changed = Signal(float)          # -1..1
    gimbal_pitch_changed = Signal(float)       # angle degrees
    gimbal_yaw_changed = Signal(float)         # angle degrees

    # ── Light ──
    light_level_changed = Signal(int)          # 0..10, step by LT/RT triggers

    # ── Digital actions (edge-triggered, not held) ──
    e_stop = Signal()                          # Back — highest priority
    lock_state_changed = Signal(LockState)     # Start — LockState.UNLOCKED or LOCKED
    drop_to_3m = Signal()                      # LB
    body_recenter = Signal()                   # L3
    gimbal_recenter = Signal()                 # R3
    all_recenter = Signal()                    # Logo
    tracking_toggle = Signal()                 # RB
    record_toggle = Signal()                   # B
    hud_toggle = Signal()                      # X
    roll_recenter = Signal()                   # Y
    preset_cycle = Signal(int)                 # A: +1 short press, -1 long press

    # ── Sensitivity adjustment (D-pad steps, integer levels) ──
    winch_sensitivity_changed = Signal(int)    # ±1 step
    plate_sensitivity_changed = Signal(int)    # ±1 step

    # ── Sensitivity level limits ──
    SENSITIVITY_MIN = 1
    SENSITIVITY_MAX = 10

    def __init__(
        self,
        poll_hz: int = 50,
        dead_zone: float = 0.08,
        smoothing_alpha: float = 0.4,
        max_winch_speed: float = 100.0,
        max_servo_speed: float = 60.0,
        sensitivity_step: float = 0.1,
        sensitivity_min: float = 0.2,
        sensitivity_max: float = 2.0,
        mappings: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._joystick = None
        self._connected = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._poll_hz = poll_hz
        self._dead_zone = dead_zone
        self._smoothing_alpha = smoothing_alpha
        self._max_winch_speed = max_winch_speed
        self._max_servo_speed = max_servo_speed
        self._sensitivity_step = sensitivity_step
        self._sensitivity_min = sensitivity_min
        self._sensitivity_max = sensitivity_max
        self._mappings = mappings or {}
        self._mapping: dict[str, Any] = _FALLBACK_MAPPING

        # ── Bridge backends (macOS only) ──
        self._use_bridge = False
        self._bridge_proc: subprocess.Popen | None = None
        self._bridge_state: dict[str, Any] = {
            "axes": [0.0] * 6, "buttons": [0] * 13, "hat": [0, 0]}
        self._bridge_lock = threading.Lock()
        self._bridge_name = "Unknown (bridge)"

        # Lock state — system starts LOCKED
        self._locked = True

        # Winch direction: +1 ascending, -1 descending, 0 neutral
        self._winch_direction = 0.0

        # Plate direction sign: +1 or -1, set externally from winch direction
        self._plate_sign = 1.0

        # Light brightness level: 0..10 (0%=off, 10=100%, default 5=50%)
        self._light_level = 5

        # Smoothed axis values
        self._smooth_winch = 0.0
        self._smooth_plate = 0.0
        self._smooth_gimbal_pitch = 0.0
        self._smooth_gimbal_yaw = 0.0

        # Edge detection state for all digital buttons
        self._btn_prev: dict[str, bool] = {
            "drop_to_3m": False, "body_recenter": False, "gimbal_recenter": False,
            "all_recenter": False, "tracking": False, "record": False,
            "hud": False, "roll_recenter": False, "preset": False,
            "e_stop": False, "lock": False,
            "light_down": False, "light_up": False,
        }

        # A button short/long press tracking
        self._preset_press_time: float | None = None
        self._preset_long_fired = False
        self._PRESET_LONG_THRESHOLD = 0.5  # seconds

        # D-pad state and debounce
        self._dpad_state: dict[str, bool] = {
            "winch_sens_up": False, "winch_sens_down": False,
            "plate_sens_left": False, "plate_sens_right": False,
        }
        self._dpad_last_fire: dict[str, float] = {
            "winch_sens_up": 0.0, "winch_sens_down": 0.0,
            "plate_sens_left": 0.0, "plate_sens_right": 0.0,
        }
        self._DPAD_DEBOUNCE = 0.2  # seconds

        # Sensitivity levels (1-10)
        self._winch_sens_level = 5
        self._plate_sens_level = 5

    # ── Public properties ──

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def lock_state(self) -> LockState:
        return LockState.LOCKED if self._locked else LockState.UNLOCKED

    @property
    def winch_direction(self) -> float:
        """Current winch direction: +1 ascending, -1 descending, 0 neutral."""
        return self._winch_direction

    def set_plate_sign(self, sign: float):
        """Set the sign multiplier for plate yaw (±1) based on winch direction.

        Called externally by app.py when winch direction changes.
        plate_yaw = joystick_value × sign
        """
        self._plate_sign = 1.0 if sign >= 0 else -1.0

    @staticmethod
    def sensitivity_curve(level: int) -> float:
        """Convert sensitivity level (1-10) to multiplier.

        Level 5 = 1.0 (linear). Curve: 0.2 + (level/5.0) * 0.8
        """
        level = max(1, min(10, level))
        return 0.2 + (level / 5.0) * 0.8

    # ── Bridge backends (macOS only) ──
    #
    # Both GCController bridge and F310 USB bridge output the same
    # JSON format ({axes, buttons, hat}), so _read_bridge() and
    # _poll_bridge() are shared.
    #
    # GC bridge: Apple GameController.framework via signed helper.
    #   Needs one-time TCC permission grant.
    # USB bridge: IOUSBHostDevice DeviceCapture, setuid root.
    #   Last resort for F310 D-mode when GCController is blocked.

    def _try_start_bridge(self, path: str, name: str) -> bool:
        """Spawn a bridge subprocess and read the first JSON line."""
        if sys.platform != "darwin":
            logger.debug("Bridge: not on macOS, skipping %s", name)
            return False

        if not os.path.exists(path):
            logger.info("Bridge binary not found: %s", path)
            return False

        try:
            # .py scripts need explicit interpreter; binaries run directly
            cmd = [sys.executable, path] if path.endswith(".py") else [path]
            self._bridge_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # Stderr reader daemon thread — prevents pipe buffer fill
            def _drain_stderr():
                while self._bridge_proc and self._bridge_proc.poll() is None:
                    try:
                        line = self._bridge_proc.stderr.readline()
                        if line:
                            logger.debug("Bridge stderr: %s", line.rstrip())
                        else:
                            break
                    except Exception:
                        break

            stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
            stderr_thread.start()
            self._stderr_thread = stderr_thread

            line = self._bridge_proc.stdout.readline()
            if not line:
                raise RuntimeError("Bridge produced no output")

            state = json.loads(line)
            with self._bridge_lock:
                self._bridge_state = state

            self._use_bridge = True
            self._bridge_name = name
            logger.info("%s connected (%d buttons)", name, len(state.get("buttons", [])))
            return True

        except Exception as e:
            logger.info("%s unavailable: %s", name, e)
            if self._bridge_proc:
                self._bridge_proc.terminate()
                self._bridge_proc = None
            return False

    def _read_bridge(self):
        """Read available JSON lines from bridge stdout.

        Uses non-blocking I/O to drain all available lines without
        blocking the Qt event loop. select() cannot be used here
        because TextIOWrapper may have internally buffered data that
        select() won't see on the kernel fd.
        """
        if not self._bridge_proc or self._bridge_proc.poll() is not None:
            return

        try:
            import os, fcntl
            fd = self._bridge_proc.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            while True:
                line = self._bridge_proc.stdout.readline()
                if not line:
                    break
                try:
                    state = json.loads(line)
                    with self._bridge_lock:
                        self._bridge_state = state
                except json.JSONDecodeError:
                    pass
        except BlockingIOError:
            pass
        except Exception:
            pass

    # ── Lifecycle ──

    def start(self) -> bool:
        """Connect to a game controller, trying backends in order.

        Backend priority:
          1. pygame (SDL2) — primary on Windows/Linux, may work on macOS.
          2. Chrome WebSocket bridge (macOS) — Chrome's Web Gamepad API,
             works because Chrome has Developer ID signing + USB entitlement.
          3. GCController bridge (macOS) — native GameController.framework
             via signed Swift helper. Only works when launched via open/LaunchServices.
          4. F310 USB bridge — deprecated (macOS 26+ kernel HIDRM block).
        """
        # ── Tier 1: pygame / SDL2 ──
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()

            count = pygame.joystick.get_count()
            if count > 0:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()

                name = self._joystick.get_name()
                self._mapping = _match_mapping(name, self._mappings)

                self._connected = True
                self._locked = True
                logger.info(
                    "Game controller connected: %s (axes=%d, buttons=%d, hats=%d) — LOCKED",
                    name,
                    self._joystick.get_numaxes(),
                    self._joystick.get_numbuttons(),
                    self._joystick.get_numhats(),
                )
                self._timer.start(1000 // self._poll_hz)
                return True

            logger.info("Game controller: no joystick detected via pygame")
        except (ImportError, Exception) as e:
            logger.info("Game controller: pygame unavailable (%s)", e)

        # ── Tier 2: Chrome WebSocket bridge (macOS only) ──
        # Chrome has Developer ID signing + com.apple.security.device.usb
        # entitlement, so Web Gamepad API can read F310 from any context.
        if self._try_start_bridge(
            _CHROME_WS_BRIDGE_PATH, "Chrome WS bridge"
        ):
            self._mapping = _match_mapping(self._bridge_name, self._mappings)
            self._connected = True
            self._locked = True
            self._timer.start(1000 // self._poll_hz)
            return True

        # ── Tier 3: GCController bridge (macOS, GameController.framework) ──
        # Apple Development signing + NSApplication run loop is sufficient,
        # but ONLY when launched via open/LaunchServices. From terminal,
        # GCController delivers all zeros (macOS 26 HIDRM policy).
        if self._try_start_bridge(
            _GC_BRIDGE_PATH, "GCController bridge"
        ):
            self._mapping = _match_mapping(self._bridge_name, self._mappings)
            self._connected = True
            self._locked = True
            self._timer.start(1000 // self._poll_hz)
            return True

        # ── Tier 4: F310 USB bridge (deprecated, macOS 26+ HIDRM) ──
        if self._try_start_bridge(
            _USB_BRIDGE_PATH, "Logitech F310 (USB bridge)"
        ):
            self._mapping = _match_mapping(self._bridge_name, self._mappings)
            self._connected = True
            self._locked = True
            self._timer.start(1000 // self._poll_hz)
            return True

        return False

    def stop(self):
        self._timer.stop()
        if self._joystick is not None:
            self._joystick.quit()
            self._joystick = None
        if self._bridge_proc:
            self._use_bridge = False
            self._bridge_proc.terminate()
            try:
                self._bridge_proc.wait(timeout=2)
            except Exception:
                self._bridge_proc.kill()
            self._bridge_proc = None
            logger.info("Bridge: disconnected")
        self._connected = False
        self._locked = True

    # ── Main poll loop ──

    def _poll(self):
        if not self._connected:
            return

        if self._use_bridge:
            self._poll_bridge()
        elif self._joystick is not None:
            self._poll_pygame()

    def _poll_pygame(self):
        try:
            import pygame
            pygame.event.pump()
        except Exception:
            return

        self._poll_axes()
        self._poll_buttons()
        self._poll_dpad()

    def _poll_bridge(self):
        """Read bridge data and emit the same signals as the pygame path.

        Bridge outputs SDL2-compatible axis/button/hat indices in JSON,
        so the same config mapping layer applies.
        """
        self._read_bridge()

        with self._bridge_lock:
            state = dict(self._bridge_state)

        axes = state.get("axes", [0.0] * 6)
        buttons = state.get("buttons", [0] * 13)
        hat = state.get("hat", [0, 0])

        m = self._mapping
        dt = 1.0 / max(self._poll_hz, 1)
        now = time.monotonic()

        def bridge_axis(cfg_name: str, default: int = -1) -> float:
            cfg = _get_axis_cfg(m, cfg_name)
            idx = cfg.get("axis", default)
            if idx < 0 or idx >= len(axes):
                return 0.0
            raw = axes[idx]
            if abs(raw) < self._dead_zone:
                return 0.0
            sign = 1.0 if raw > 0 else -1.0
            normalized = sign * (abs(raw) - self._dead_zone) / (1.0 - self._dead_zone)
            if cfg.get("invert", False):
                normalized = -normalized
            return float(normalized)

        def bridge_button(name: str) -> bool:
            idx = _get_button_idx(m, name)
            if idx is None or idx >= len(buttons):
                return False
            return bool(buttons[idx])

        def bridge_edge(name: str) -> int:
            cur = bridge_button(name)
            prev = self._btn_prev.get(name, False)
            self._btn_prev[name] = cur
            if cur and not prev:
                return 1
            elif not cur and prev:
                return -1
            return 0

        # ── Axes ──
        raw_winch = bridge_axis("winch", 1)
        if self._locked:
            raw_winch = 0.0
        self._smooth_winch += (raw_winch - self._smooth_winch) * self._smoothing_alpha
        winch_val = self._smooth_winch * self._max_winch_speed
        self.winch_speed_changed.emit(winch_val)
        if abs(self._smooth_winch) > 0.01:
            self._winch_direction = 1.0 if self._smooth_winch > 0 else -1.0

        raw_plate = bridge_axis("plate_yaw", 0)
        if self._locked:
            raw_plate = 0.0
        self._smooth_plate += (raw_plate - self._smooth_plate) * self._smoothing_alpha
        self.plate_yaw_changed.emit(self._smooth_plate * self._plate_sign)

        raw_gp = bridge_axis("gimbal_pitch", 3)
        if self._locked:
            raw_gp = 0.0
        self._smooth_gimbal_pitch += (raw_gp - self._smooth_gimbal_pitch) * self._smoothing_alpha
        gimbal_pitch_angle = 90.0 + self._smooth_gimbal_pitch * self._max_servo_speed * dt
        self.gimbal_pitch_changed.emit(max(0.0, min(180.0, gimbal_pitch_angle)))

        raw_gy = bridge_axis("gimbal_yaw", 2)
        if self._locked:
            raw_gy = 0.0
        self._smooth_gimbal_yaw += (raw_gy - self._smooth_gimbal_yaw) * self._smoothing_alpha
        gimbal_yaw_angle = 90.0 + self._smooth_gimbal_yaw * self._max_servo_speed * dt
        self.gimbal_yaw_changed.emit(max(0.0, min(180.0, gimbal_yaw_angle)))

        # ── Buttons (edge-triggered) ──
        # E-stop (Back) — ALWAYS active
        if bridge_edge("e_stop") == 1:
            logger.warning("Game controller: E-STOP triggered (Back)")
            self.e_stop.emit()

        # Lock/Unlock (Start)
        if bridge_edge("lock") == 1:
            self._locked = not self._locked
            state = LockState.UNLOCKED if not self._locked else LockState.LOCKED
            self.lock_state_changed.emit(state)
            logger.info("Game controller: %s", state.value.upper())
            if self._locked:
                self._smooth_winch = 0.0
                self._smooth_plate = 0.0
                self._smooth_gimbal_pitch = 0.0
                self._smooth_gimbal_yaw = 0.0
                self.winch_speed_changed.emit(0.0)
                self.plate_yaw_changed.emit(0.0)

        # ── Light brightness stepping (LT down, RT up) ──
        # Active regardless of lock state (safety-neutral UI function).
        if bridge_edge("light_down") == 1:
            self._light_level = max(0, self._light_level - 1)
            self.light_level_changed.emit(self._light_level)
            logger.info("Light: %d0%%", self._light_level)
        if bridge_edge("light_up") == 1:
            self._light_level = min(10, self._light_level + 1)
            self.light_level_changed.emit(self._light_level)
            logger.info("Light: %d0%%", self._light_level)

        # Suppress non-safety buttons when locked
        if self._locked:
            for name in self._btn_prev:
                if name not in ("e_stop", "lock"):
                    cur = bridge_button(name)
                    self._btn_prev[name] = cur
            return

        # ── A: Preset cycle ──
        preset_pressed = bridge_button("preset")
        if preset_pressed and not self._btn_prev.get("preset", False):
            self._preset_press_time = now
            self._preset_long_fired = False
        elif preset_pressed and self._preset_press_time is not None:
            if not self._preset_long_fired and (now - self._preset_press_time) >= self._PRESET_LONG_THRESHOLD:
                self._preset_long_fired = True
                self.preset_cycle.emit(-1)
                logger.info("Game controller: Preset cycle BACKWARD (long press)")
        elif not preset_pressed and self._btn_prev.get("preset", False):
            if self._preset_press_time is not None and not self._preset_long_fired:
                elapsed = now - self._preset_press_time
                if elapsed < self._PRESET_LONG_THRESHOLD:
                    self.preset_cycle.emit(1)
                    logger.info("Game controller: Preset cycle FORWARD (short press)")
            self._preset_press_time = None
            self._preset_long_fired = False
        self._btn_prev["preset"] = preset_pressed

        # ── Remaining digital buttons ──
        if bridge_edge("drop_to_3m") == 1:
            self.drop_to_3m.emit()
            logger.info("Game controller: Drop to 3m")
        if bridge_edge("body_recenter") == 1:
            self.body_recenter.emit()
            logger.info("Game controller: Body recenter")
        if bridge_edge("gimbal_recenter") == 1:
            self.gimbal_recenter.emit()
            logger.info("Game controller: Gimbal recenter")
        if bridge_edge("all_recenter") == 1:
            self.all_recenter.emit()
            logger.info("Game controller: All recenter")
        if bridge_edge("tracking") == 1:
            self.tracking_toggle.emit()
            logger.info("Game controller: Tracking toggle")
        if bridge_edge("record") == 1:
            self.record_toggle.emit()
            logger.info("Game controller: Record toggle")
        if bridge_edge("hud") == 1:
            self.hud_toggle.emit()
            logger.info("Game controller: HUD toggle")
        if bridge_edge("roll_recenter") == 1:
            self.roll_recenter.emit()
            logger.info("Game controller: Roll recenter")

        # ── D-pad (hat) for sensitivity ──
        if self._locked:
            for key in self._dpad_state:
                self._dpad_state[key] = False
            return

        def dpad_edge(name: str, target: tuple) -> int:
            cur = (hat[0] == target[0] and hat[1] == target[1])
            prev = self._dpad_state.get(name, False)
            self._dpad_state[name] = cur
            if cur and not prev:
                return 1
            return 0

        def debounced(name: str) -> bool:
            last = self._dpad_last_fire.get(name, 0.0)
            if now - last < self._DPAD_DEBOUNCE:
                return False
            self._dpad_last_fire[name] = now
            return True

        dpad_map = m.get("dpad", {})
        if dpad_edge("winch_sens_up", dpad_map.get("winch_sens_up", [0, 1])) and debounced("winch_sens_up"):
            self._winch_sens_level = min(self.SENSITIVITY_MAX, self._winch_sens_level + 1)
            self.winch_sensitivity_changed.emit(self._winch_sens_level)
            logger.info("Winch sensitivity: %d", self._winch_sens_level)
        if dpad_edge("winch_sens_down", dpad_map.get("winch_sens_down", [0, -1])) and debounced("winch_sens_down"):
            self._winch_sens_level = max(self.SENSITIVITY_MIN, self._winch_sens_level - 1)
            self.winch_sensitivity_changed.emit(self._winch_sens_level)
            logger.info("Winch sensitivity: %d", self._winch_sens_level)
        if dpad_edge("plate_sens_left", dpad_map.get("plate_sens_left", [-1, 0])) and debounced("plate_sens_left"):
            self._plate_sens_level = max(self.SENSITIVITY_MIN, self._plate_sens_level - 1)
            self.plate_sensitivity_changed.emit(self._plate_sens_level)
            logger.info("Plate sensitivity: %d", self._plate_sens_level)
        if dpad_edge("plate_sens_right", dpad_map.get("plate_sens_right", [1, 0])) and debounced("plate_sens_right"):
            self._plate_sens_level = min(self.SENSITIVITY_MAX, self._plate_sens_level + 1)
            self.plate_sensitivity_changed.emit(self._plate_sens_level)
            logger.info("Plate sensitivity: %d", self._plate_sens_level)

    # ── Axes ──

    def _poll_axes(self):
        m = self._mapping
        num_axes = self._joystick.get_numaxes()
        dt = 1.0 / max(self._poll_hz, 1)

        def read_axis(cfg_name: str, default: int = -1) -> float:
            cfg = _get_axis_cfg(m, cfg_name)
            idx = cfg.get("axis", default)
            if idx < 0 or idx >= num_axes:
                return 0.0
            try:
                raw = self._joystick.get_axis(idx)
            except Exception:
                return 0.0
            if abs(raw) < self._dead_zone:
                return 0.0
            sign = 1.0 if raw > 0 else -1.0
            normalized = sign * (abs(raw) - self._dead_zone) / (1.0 - self._dead_zone)
            if cfg.get("invert", False):
                normalized = -normalized
            return float(normalized)

        # ── Winch (left stick Y) ──
        raw_winch = read_axis("winch", 1)
        if self._locked:
            raw_winch = 0.0
        self._smooth_winch += (raw_winch - self._smooth_winch) * self._smoothing_alpha
        winch_val = self._smooth_winch * self._max_winch_speed
        self.winch_speed_changed.emit(winch_val)

        # Track winch direction for external consumers
        if abs(self._smooth_winch) > 0.01:
            self._winch_direction = 1.0 if self._smooth_winch > 0 else -1.0

        # ── Plate yaw (left stick X) with external sign ──
        raw_plate = read_axis("plate_yaw", 0)
        if self._locked:
            raw_plate = 0.0
        self._smooth_plate += (raw_plate - self._smooth_plate) * self._smoothing_alpha
        plate_val = self._smooth_plate * self._plate_sign
        self.plate_yaw_changed.emit(plate_val)

        # ── Gimbal pitch (right stick Y) ──
        raw_gp = read_axis("gimbal_pitch", 3)
        if self._locked:
            raw_gp = 0.0
        self._smooth_gimbal_pitch += (raw_gp - self._smooth_gimbal_pitch) * self._smoothing_alpha
        gimbal_pitch_angle = 90.0 + self._smooth_gimbal_pitch * self._max_servo_speed * dt
        self.gimbal_pitch_changed.emit(max(0.0, min(180.0, gimbal_pitch_angle)))

        # ── Gimbal yaw (right stick X) ──
        raw_gy = read_axis("gimbal_yaw", 2)
        if self._locked:
            raw_gy = 0.0
        self._smooth_gimbal_yaw += (raw_gy - self._smooth_gimbal_yaw) * self._smoothing_alpha
        gimbal_yaw_angle = 90.0 + self._smooth_gimbal_yaw * self._max_servo_speed * dt
        self.gimbal_yaw_changed.emit(max(0.0, min(180.0, gimbal_yaw_angle)))

    # ── Buttons (edge-triggered) ──

    def _poll_buttons(self):
        m = self._mapping
        num_buttons = self._joystick.get_numbuttons()
        now = time.monotonic()

        def read_button(name: str) -> bool:
            idx = _get_button_idx(m, name)
            if idx is None or idx >= num_buttons:
                return False
            try:
                return bool(self._joystick.get_button(idx))
            except Exception:
                return False

        def edge(name: str) -> int:
            """Return 1 on rising edge, -1 on falling edge, 0 otherwise."""
            cur = read_button(name)
            prev = self._btn_prev.get(name, False)
            self._btn_prev[name] = cur
            if cur and not prev:
                return 1
            elif not cur and prev:
                return -1
            return 0

        # ── E-stop (Back) — ALWAYS active, regardless of lock state ──
        if edge("e_stop") == 1:
            logger.warning("Game controller: E-STOP triggered (Back)")
            self.e_stop.emit()

        # ── Lock/Unlock (Start) ──
        if edge("lock") == 1:
            self._locked = not self._locked
            state = LockState.UNLOCKED if not self._locked else LockState.LOCKED
            self.lock_state_changed.emit(state)
            logger.info("Game controller: %s", state.value.upper())
            if self._locked:
                self._smooth_winch = 0.0
                self._smooth_plate = 0.0
                self._smooth_gimbal_pitch = 0.0
                self._smooth_gimbal_yaw = 0.0
                self.winch_speed_changed.emit(0.0)
                self.plate_yaw_changed.emit(0.0)

        # ── Light brightness stepping (LT down, RT up) ──
        # Active regardless of lock state (safety-neutral UI function).
        if edge("light_down") == 1:
            self._light_level = max(0, self._light_level - 1)
            self.light_level_changed.emit(self._light_level)
            logger.info("Light: %d0%%", self._light_level)
        if edge("light_up") == 1:
            self._light_level = min(10, self._light_level + 1)
            self.light_level_changed.emit(self._light_level)
            logger.info("Light: %d0%%", self._light_level)

        # ── Below this point, locked state suppresses all non-safety buttons ──
        if self._locked:
            for name in self._btn_prev:
                if name not in ("e_stop", "lock", "light_down", "light_up"):
                    read_button(name)
                    self._btn_prev[name] = read_button(name)
            return

        # ── A: Preset cycle (short press +1, long press -1) ──
        preset_pressed = read_button("preset")
        if preset_pressed and not self._btn_prev.get("preset", False):
            # Rising edge — start timing
            self._preset_press_time = now
            self._preset_long_fired = False
        elif preset_pressed and self._preset_press_time is not None:
            # Held — check for long press threshold
            if not self._preset_long_fired and (now - self._preset_press_time) >= self._PRESET_LONG_THRESHOLD:
                self._preset_long_fired = True
                self.preset_cycle.emit(-1)
                logger.info("Game controller: Preset cycle BACKWARD (long press)")
        elif not preset_pressed and self._btn_prev.get("preset", False):
            # Falling edge — short press if long didn't fire
            if self._preset_press_time is not None and not self._preset_long_fired:
                elapsed = now - self._preset_press_time
                if elapsed < self._PRESET_LONG_THRESHOLD:
                    self.preset_cycle.emit(1)
                    logger.info("Game controller: Preset cycle FORWARD (short press)")
            self._preset_press_time = None
            self._preset_long_fired = False
        self._btn_prev["preset"] = preset_pressed

        # ── LB: Drop to 3m ──
        if edge("drop_to_3m") == 1:
            self.drop_to_3m.emit()
            logger.info("Game controller: Drop to 3m")

        # ── L3: Body recenter ──
        if edge("body_recenter") == 1:
            self.body_recenter.emit()
            logger.info("Game controller: Body recenter")

        # ── R3: Gimbal recenter ──
        if edge("gimbal_recenter") == 1:
            self.gimbal_recenter.emit()
            logger.info("Game controller: Gimbal recenter")

        # ── Logo: All recenter ──
        if edge("all_recenter") == 1:
            self.all_recenter.emit()
            logger.info("Game controller: All recenter")

        # ── RB: Tracking toggle ──
        if edge("tracking") == 1:
            self.tracking_toggle.emit()
            logger.info("Game controller: Tracking toggle")

        # ── B: Record toggle ──
        if edge("record") == 1:
            self.record_toggle.emit()
            logger.info("Game controller: Record toggle")

        # ── X: HUD toggle ──
        if edge("hud") == 1:
            self.hud_toggle.emit()
            logger.info("Game controller: HUD toggle")

        # ── Y: Roll recenter ──
        if edge("roll_recenter") == 1:
            self.roll_recenter.emit()
            logger.info("Game controller: Roll recenter")

    # ── D-pad (hat) for sensitivity ──

    def _poll_dpad(self):
        m = self._mapping
        try:
            num_hats = self._joystick.get_numhats()
        except Exception:
            return
        if num_hats == 0:
            return

        try:
            hat = self._joystick.get_hat(0)
        except Exception:
            return

        if self._locked:
            for key in self._dpad_state:
                self._dpad_state[key] = False
            return

        now = time.monotonic()

        def dpad_edge(name: str, target: tuple) -> int:
            cur = (hat[0] == target[0] and hat[1] == target[1])
            prev = self._dpad_state.get(name, False)
            self._dpad_state[name] = cur
            if cur and not prev:
                return 1
            return 0

        def debounced(name: str) -> bool:
            last = self._dpad_last_fire.get(name, 0.0)
            if now - last < self._DPAD_DEBOUNCE:
                return False
            self._dpad_last_fire[name] = now
            return True

        if dpad_edge("winch_sens_up", m.get("dpad", {}).get("winch_sens_up", [0, 1])) and debounced("winch_sens_up"):
            self._winch_sens_level = min(self.SENSITIVITY_MAX, self._winch_sens_level + 1)
            self.winch_sensitivity_changed.emit(self._winch_sens_level)
            logger.info("Winch sensitivity: %d", self._winch_sens_level)
        if dpad_edge("winch_sens_down", m.get("dpad", {}).get("winch_sens_down", [0, -1])) and debounced("winch_sens_down"):
            self._winch_sens_level = max(self.SENSITIVITY_MIN, self._winch_sens_level - 1)
            self.winch_sensitivity_changed.emit(self._winch_sens_level)
            logger.info("Winch sensitivity: %d", self._winch_sens_level)
        if dpad_edge("plate_sens_left", m.get("dpad", {}).get("plate_sens_left", [-1, 0])) and debounced("plate_sens_left"):
            self._plate_sens_level = max(self.SENSITIVITY_MIN, self._plate_sens_level - 1)
            self.plate_sensitivity_changed.emit(self._plate_sens_level)
            logger.info("Plate sensitivity: %d", self._plate_sens_level)
        if dpad_edge("plate_sens_right", m.get("dpad", {}).get("plate_sens_right", [1, 0])) and debounced("plate_sens_right"):
            self._plate_sens_level = min(self.SENSITIVITY_MAX, self._plate_sens_level + 1)
            self.plate_sensitivity_changed.emit(self._plate_sens_level)
            logger.info("Plate sensitivity: %d", self._plate_sens_level)


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

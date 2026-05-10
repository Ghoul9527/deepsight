"""Command interceptor — captures Host→Pi commands, logs them, generates fake feedback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from deepsight_shared.protocol import (
    Message, new_message,
)

logger = logging.getLogger("emu.interceptor")

FEEDBACK_DELAY = 0.05  # seconds — simulate MCU response time


@dataclass
class CommandEntry:
    """A captured command, displayed in the interceptor panel."""
    timestamp: float
    msg_type: str
    payload: dict
    forwarded: bool


class CommandInterceptor:
    """Intercepts Host→device commands, generates fake feedback.

    When a command type is hijacked:
      - The command is logged but NOT forwarded to the real device
      - A fake feedback message is generated (servo position, lighting state, etc.)
      - The feedback is queued for the proxy to send back to Host
    """

    def __init__(self):
        self._hijack: set[str] = set()  # hijacked message type prefixes
        self._log: list[CommandEntry] = []
        self._on_log: Callable[[CommandEntry], None] | None = None
        self._on_feedback: Callable[[Message], None] | None = None
        # State tracking for fake feedback
        self._servo_positions: dict[int, float] = {0: 90.0, 1: 90.0}
        self._lighting_brightness: float = 0.0
        self._gopro_recording: bool = False
        self._gopro_mode: str = "video"
        self._winch_speed: float = 0.0
        self._winch_position: float = 2500.0

    # ── Hijack control ──

    def set_hijack(self, msg_type_prefix: str, enabled: bool):
        if enabled:
            self._hijack.add(msg_type_prefix)
        else:
            self._hijack.discard(msg_type_prefix)

    def is_hijacked(self, msg_type: str) -> bool:
        for prefix in self._hijack:
            if msg_type.startswith(prefix):
                return True
        return False

    @property
    def hijacked_types(self) -> frozenset[str]:
        return frozenset(self._hijack)

    # ── Callbacks ──

    def set_on_log(self, cb: Callable[[CommandEntry], None]):
        self._on_log = cb

    def set_on_feedback(self, cb: Callable[[Message], None]):
        """Called when fake feedback is generated (to inject back to Host)."""
        self._on_feedback = cb

    # ── Command processing ──

    def process_command(self, msg: Message) -> bool:
        """Process a Host→device command.

        Returns True if the command should be forwarded to the real device,
        False if it was intercepted (and fake feedback was generated).
        """
        hijacked = self.is_hijacked(msg.type)

        entry = CommandEntry(
            timestamp=__import__('time').monotonic(),
            msg_type=msg.type,
            payload=dict(msg.payload),
            forwarded=not hijacked,
        )
        self._log.append(entry)
        if len(self._log) > 200:
            self._log = self._log[-100:]

        if self._on_log:
            self._on_log(entry)

        if hijacked:
            self._generate_feedback(msg)

        return not hijacked

    def _generate_feedback(self, msg: Message):
        """Generate fake feedback based on the intercepted command."""
        feedback = None

        if msg.type == "cmd.servo.set":
            servo_id = msg.payload.get("servo_id", 0)
            angle = msg.payload.get("angle", 90.0)
            self._servo_positions[servo_id] = angle
            feedback = new_message("pico", "tel.servo_position", {
                "servo_id": servo_id, "angle": angle,
            })

        elif msg.type == "cmd.lighting.set":
            brightness = msg.payload.get("brightness", 0.0)
            self._lighting_brightness = brightness
            feedback = new_message("pico", "tel.lighting_state", {
                "channel": msg.payload.get("channel", 0),
                "brightness": brightness,
            })

        elif msg.type == "cmd.winch.set":
            speed = msg.payload.get("speed", 0.0)
            self._winch_speed = speed
            direction = msg.payload.get("direction", "stop")
            if direction == "up":
                self._winch_speed = abs(speed)
            elif direction == "down":
                self._winch_speed = -abs(speed)
            else:
                self._winch_speed = 0.0

        elif msg.type == "cmd.winch.stop":
            self._winch_speed = 0.0

        elif msg.type == "cmd.gopro.record":
            start = msg.payload.get("start", False)
            self._gopro_recording = start
            from deepsight_shared.protocol import tel_gopro_status
            feedback = tel_gopro_status("pi", start, 85.0, 120.0, self._gopro_mode)

        elif msg.type == "cmd.gopro.mode":
            mode = msg.payload.get("mode", "video")
            self._gopro_mode = mode
            from deepsight_shared.protocol import tel_gopro_status
            feedback = tel_gopro_status("pi", self._gopro_recording, 85.0, 120.0, mode)

        # ACK for every intercepted command
        ack = new_message("pico", "sys.ack", {"ref_msg_id": msg.msg_id})
        if self._on_feedback:
            self._on_feedback(ack)
            if feedback:
                self._on_feedback(feedback)

    @property
    def log(self) -> list[CommandEntry]:
        return list(self._log)

    def clear_log(self):
        self._log.clear()

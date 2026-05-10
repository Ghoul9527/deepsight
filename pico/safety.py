"""Local safety fallback logic for the Pico."""

import time

import config


class SafetyMonitor:
    def __init__(self):
        self._last_command_time = time.time()
        self._safety_active = False

    def command_received(self):
        self._last_command_time = time.time()
        self._safety_active = False

    def check(self) -> bool:
        elapsed = time.time() - self._last_command_time
        if elapsed > config.NO_COMMAND_TIMEOUT_S:
            self._safety_active = True
            return True
        return False

    @property
    def safety_active(self) -> bool:
        return self._safety_active

    def get_default_angles(self) -> list:
        return [config.DEFAULT_SERVO_ANGLE] * config.SERVO_COUNT

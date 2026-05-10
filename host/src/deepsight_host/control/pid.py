"""PID controller for servo positioning from tracking error."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("host.control.pid")


@dataclass
class PIDGains:
    p: float = 0.8
    i: float = 0.05
    d: float = 0.2


class PIDController:
    def __init__(self, gains: PIDGains | None = None,
                 output_limit: float = 1.0, dead_zone: float = 0.0):
        self.gains = gains or PIDGains()
        self.output_limit = output_limit
        self.dead_zone = dead_zone
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

    def update(self, error: float, dt: float) -> float:
        if abs(error) < self.dead_zone:
            return 0.0

        self._integral += error * dt
        if dt > 0:
            derivative = (error - self._prev_error) / dt
        else:
            derivative = 0.0

        output = (self.gains.p * error
                  + self.gains.i * self._integral
                  + self.gains.d * derivative)

        # Clamp
        output = max(-self.output_limit, min(self.output_limit, output))

        # Anti-windup: don't accumulate integral if saturated
        if abs(output) < self.output_limit:
            pass  # integral already accumulated
        else:
            self._integral -= error * dt * 0.5  # back off

        self._prev_error = error
        self._initialized = True
        return output

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

"""Fin-yaw coupling controller — deflects both fins based on yaw + vertical speed."""

import logging
import time

logger = logging.getLogger("pi.fin")


class FinController:
    def __init__(self, servo_controller, config: dict):
        self._servo = servo_controller
        self._left_id = 3
        self._right_id = 4

        self._yaw_max = config.get("yaw_max_deg", 15.0)
        self._speed_min = config.get("speed_min", 0.1)
        self._speed_max = config.get("speed_max", 2.0)
        self._defl_slow = config.get("deflection_at_slow", 45.0)
        self._defl_fast = config.get("deflection_at_fast", 15.0)
        self._speed_deadband = config.get("speed_deadband", 0.05)
        self._ema_alpha = config.get("ema_alpha", 0.12)

        self._yaw_angle = 90.0
        self._yaw_sign = 0
        self._last_depth = None
        self._last_depth_time = None
        self._speed_ema = 0.0
        self._sim_active = False
        self._enabled = False

        logger.info("FinController: yaw_max=%.1f speed=[%.2f,%.1f] defl=[%.0f,%.0f]",
                     self._yaw_max, self._speed_min, self._speed_max,
                     self._defl_slow, self._defl_fast)

    def update_yaw(self, angle: float):
        self._yaw_angle = angle

    def update_depth(self, depth_m: float, sim: bool = False, speed_ms: float | None = None):
        if self._sim_active and not sim:
            return
        if sim:
            self._sim_active = True
            if speed_ms is not None:
                self._speed_ema = speed_ms
                return
        now = time.time()
        if self._last_depth is not None and self._last_depth_time is not None:
            dt = now - self._last_depth_time
            if dt > 0.01:
                raw_speed = (depth_m - self._last_depth) / dt
                self._speed_ema = self._ema_alpha * raw_speed + (1 - self._ema_alpha) * self._speed_ema
        self._last_depth = depth_m
        self._last_depth_time = now

    def enable_auto(self):
        self._enabled = True
        logger.info("Fin coupling: AUTO mode")

    def disable_auto(self):
        self._enabled = False
        logger.info("Fin coupling: MANUAL mode")

    def notify_manual(self, angle: float = 90.0):
        if self._enabled:
            self._enabled = False
            logger.info("Fin coupling: stick intervention → MANUAL mode")

    @property
    def hovering(self) -> bool:
        return abs(self._speed_ema) < self._speed_deadband

    def is_active(self) -> bool:
        if self.hovering:
            return True
        return self._enabled

    def step(self):
        if self.hovering:
            self._servo.set_angle(self._left_id, 90.0)
            self._servo.set_angle(self._right_id, 90.0)
            return
        if not self._enabled:
            return

        yaw_dev = self._yaw_angle - 90.0
        speed = self._speed_ema
        abs_speed = abs(speed)

        # Hysteresis: lock direction until yaw firmly crosses to the other side
        if yaw_dev > 3.0:
            self._yaw_sign = 1
        elif yaw_dev < -3.0:
            self._yaw_sign = -1

        if self._yaw_sign == 0 or abs_speed < self._speed_deadband:
            target = 0.0
        else:
            yaw_magnitude = min(abs(yaw_dev) / self._yaw_max, 1.0)
            max_defl = self._deflection_for_speed(abs_speed)
            direction = -1.0 if speed > 0 else 1.0
            target = yaw_magnitude * max_defl * self._yaw_sign * direction

        self._servo.set_angle(self._left_id, 90.0 + target)
        self._servo.set_angle(self._right_id, 90.0 + target)

    def _deflection_for_speed(self, speed: float) -> float:
        if speed <= self._speed_min:
            return self._defl_slow
        if speed >= self._speed_max:
            return self._defl_fast
        ratio = (speed - self._speed_min) / (self._speed_max - self._speed_min)
        return self._defl_slow + ratio * (self._defl_fast - self._defl_slow)

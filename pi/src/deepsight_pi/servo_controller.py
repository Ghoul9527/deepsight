"""Servo and lighting controller using PCA9685."""

import logging
import time

from deepsight_pi.hardware.pca9685 import PCA9685
from deepsight_pi.servo_calibration import DEFAULT_CALIBRATION, DEFAULT_DEFLECTION_LIMITS, calibrated_pulse

logger = logging.getLogger("pi.servo")


class ServoController:
    def __init__(self, hardware_config: dict):
        pca = hardware_config.get("pca9685", {})
        self._pca = PCA9685(
            bus=pca.get("i2c_bus", 1),
            address=pca.get("i2c_address", 0x40),
            freq=pca.get("pwm_freq", 50),
        )
        self._calibration = {**DEFAULT_CALIBRATION, **hardware_config.get("servo_calibration", {})}
        self._min_us = pca.get("pulse_min_us", 500)
        self._max_us = pca.get("pulse_max_us", 2500)
        self._min_deg = pca.get("angle_min", 0.0)
        self._max_deg = pca.get("angle_max", 180.0)
        self._default_angle = pca.get("default_angle", 90.0)

        self._servo_channels: dict[int, dict] = {}
        for ch_cfg in hardware_config.get("servos", []):
            sid = ch_cfg["id"]
            self._servo_channels[sid] = ch_cfg

        # Lighting channels: {channel: max_brightness}
        self._light_channels: dict[int, dict] = {}
        self._light_pwm_percent: dict[int, float] = {}
        for ch_cfg in hardware_config.get("lights", []):
            lid = ch_cfg["id"]
            self._light_channels[lid] = ch_cfg

        # Safety timeout
        self._timeout_s = pca.get("safety_timeout_s", 3.0)
        self._last_command = time.time()
        self._safety_triggered = False

        try:
            self._initialize_outputs()
        except Exception:
            self._pca.close()
            raise

        logger.info("ServoController: %d servos, %d lights, addr=0x%02X",
                     len(self._servo_channels), len(self._light_channels),
                     pca.get("i2c_address", 0x40))

    def _initialize_outputs(self):
        for sid in self._servo_channels:
            self.set_angle(sid, self._default_angle)
        for lid in self._light_channels:
            self.set_brightness(lid, 0.0)
        self._last_command = time.time()
        self._safety_triggered = False

    def recover(self):
        """Reapply device setup after a disconnect/power loss."""
        self._pca._write_reg(0x00, 0x00)
        self._pca.set_pwm_freq(self._pca._freq)
        self._initialize_outputs()

    def set_angle(self, servo_id: int, angle: float):
        ch_cfg = self._servo_channels.get(servo_id)
        if ch_cfg is None:
            logger.warning("Unknown servo: %d", servo_id)
            return

        calibration = {**self._calibration}
        for key in DEFAULT_CALIBRATION:
            if key in ch_cfg:
                calibration[key] = ch_cfg[key]
        limit = ch_cfg.get("max_deflection_deg", DEFAULT_DEFLECTION_LIMITS.get(servo_id, 15.0))
        pulse = calibrated_pulse(float(angle), calibration, float(limit))
        ch = ch_cfg.get("channel", servo_id)
        self._pca.set_pwm(ch, pulse)
        self._last_command = time.time()
        self._safety_triggered = False

    def set_brightness(self, light_id: int, brightness: float):
        ch_cfg = self._light_channels.get(light_id)
        if ch_cfg is None:
            logger.warning("Unknown light: %d", light_id)
            return

        brightness = max(0.0, min(1.0, brightness))
        ch = ch_cfg.get("channel", light_id)
        # Update reported state only after a successful hardware write.
        self._light_pwm_percent[light_id] = self._pca.set_duty_cycle(ch, brightness)
        self._last_command = time.time()

    def get_light_pwm_percent(self, light_id: int = 0) -> float | None:
        return self._light_pwm_percent.get(light_id)

    def check_safety(self) -> bool:
        """Return True if safety timeout triggered (servos reset to default)."""
        if self._safety_triggered:
            return False
        if time.time() - self._last_command > self._timeout_s:
            logger.warning("Safety timeout: resetting %d servos to %.1f",
                           len(self._servo_channels), self._default_angle)
            for sid in self._servo_channels:
                self.set_angle(sid, self._default_angle)
            self._safety_triggered = True
            return True
        return False

    def heartbeat(self):
        """Reset safety timer without moving servos."""
        self._last_command = time.time()

    def close(self):
        self._pca.close()

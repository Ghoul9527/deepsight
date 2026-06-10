"""Servo and lighting controller using PCA9685."""

import logging
import time

from deepsight_pi.hardware.pca9685 import PCA9685

logger = logging.getLogger("pi.servo")


class ServoController:
    def __init__(self, hardware_config: dict):
        pca = hardware_config.get("pca9685", {})
        self._pca = PCA9685(
            bus=pca.get("i2c_bus", 1),
            address=pca.get("i2c_address", 0x40),
            freq=pca.get("pwm_freq", 50),
        )
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
        for ch_cfg in hardware_config.get("lights", []):
            lid = ch_cfg["id"]
            self._light_channels[lid] = ch_cfg

        # Safety timeout
        self._timeout_s = pca.get("safety_timeout_s", 3.0)
        self._last_command = time.time()
        self._safety_triggered = False

        # Initialize all servos to default
        for sid in self._servo_channels:
            self.set_angle(sid, self._default_angle)

        logger.info("ServoController: %d servos, %d lights, addr=0x%02X",
                     len(self._servo_channels), len(self._light_channels),
                     pca.get("i2c_address", 0x40))

    def set_angle(self, servo_id: int, angle: float):
        ch_cfg = self._servo_channels.get(servo_id)
        if ch_cfg is None:
            logger.warning("Unknown servo: %d", servo_id)
            return

        a_min = ch_cfg.get("angle_min", self._min_deg)
        a_max = ch_cfg.get("angle_max", self._max_deg)
        p_min = ch_cfg.get("pulse_min_us", self._min_us)
        p_max = ch_cfg.get("pulse_max_us", self._max_us)

        angle = max(a_min, min(a_max, angle))
        ch = ch_cfg.get("channel", servo_id)
        self._pca.set_angle(ch, angle, min_us=p_min, max_us=p_max,
                            min_deg=a_min, max_deg=a_max)
        self._last_command = time.time()
        self._safety_triggered = False

    def set_brightness(self, light_id: int, brightness: float):
        ch_cfg = self._light_channels.get(light_id)
        if ch_cfg is None:
            logger.warning("Unknown light: %d", light_id)
            return

        brightness = max(0.0, min(1.0, brightness))
        ch = ch_cfg.get("channel", light_id)
        # Map 0.0-1.0 to 0-4095 PWM duty
        pulse_us = brightness * self._pca._period_us
        self._pca.set_pwm(ch, pulse_us)
        self._last_command = time.time()

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

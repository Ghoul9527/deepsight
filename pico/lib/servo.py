"""Servo driver — PCA9685 + mock implementation."""

import config
from lib.driver_base import ServoDriver


# ── Mock ─────────────────────────────────────────────────

class MockServoDriver(ServoDriver):
    def __init__(self):
        super().__init__("servo_mock")
        self._positions = [config.DEFAULT_SERVO_ANGLE] * config.SERVO_COUNT

    def init(self) -> bool:
        super().init()
        return True

    def set_angle(self, servo_id: int, angle_deg: float):
        angle_deg = max(config.MIN_SERVO_ANGLE, min(config.MAX_SERVO_ANGLE, angle_deg))
        self._positions[servo_id] = angle_deg

    def get_angle(self, servo_id: int) -> float:
        return self._positions[servo_id]

    def get_all_positions(self) -> list:
        return list(self._positions)


# ── Real PCA9685 ─────────────────────────────────────────

class PCA9685ServoDriver(ServoDriver):
    """PCA9685 16-channel PWM servo driver over I2C.

    Works on MicroPython (machine.I2C) or CPython with adafruit-blinka.
    """

    def __init__(self):
        super().__init__("servo_pca9685")
        self._i2c = None
        self._pca = None
        self._positions = [config.DEFAULT_SERVO_ANGLE] * config.SERVO_COUNT
        self._pulse_range_us = (config.SERVO_PULSE_MIN_US, config.SERVO_PULSE_MAX_US)

    def init(self) -> bool:
        try:
            from machine import I2C, Pin
            self._i2c = I2C(
                0,
                scl=Pin(config.SERVO_I2C_SCL_PIN),
                sda=Pin(config.SERVO_I2C_SDA_PIN),
                freq=config.SERVO_I2C_FREQ,
            )
            self._pca = _PCA9685(self._i2c, config.SERVO_I2C_ADDR)
            self._pca.set_pwm_freq(config.SERVO_PWM_FREQ)
        except ImportError:
            # CPython fallback — use adafruit-circuitpython-pca9685
            try:
                import board
                import busio
                from adafruit_pca9685 import PCA9685
                self._i2c = busio.I2C(board.SCL, board.SDA)
                self._pca = PCA9685(self._i2c, address=config.SERVO_I2C_ADDR)
                self._pca.frequency = config.SERVO_PWM_FREQ
            except (ImportError, NotImplementedError):
                return False
        except Exception:
            return False

        super().init()
        # Centre all servos on startup
        for i in range(config.SERVO_COUNT):
            self.set_angle(i, config.DEFAULT_SERVO_ANGLE)
        return True

    def deinit(self):
        if self._pca:
            try:
                self._pca.deinit()
            except AttributeError:
                pass
        super().deinit()

    def set_angle(self, servo_id: int, angle_deg: float):
        angle_deg = max(config.MIN_SERVO_ANGLE, min(config.MAX_SERVO_ANGLE, angle_deg))
        self._positions[servo_id] = angle_deg
        if self._pca is not None:
            pulse_us = self._angle_to_pulse(angle_deg)
            self._pca.set_pwm(servo_id, pulse_us)

    def get_angle(self, servo_id: int) -> float:
        return self._positions[servo_id]

    def get_all_positions(self) -> list:
        return list(self._positions)

    def _angle_to_pulse(self, angle_deg: float) -> int:
        """Map 0–180 degrees to pulse width in microseconds."""
        frac = angle_deg / 180.0
        return int(self._pulse_range_us[0] + frac * (self._pulse_range_us[1] - self._pulse_range_us[0]))


# ── MicroPython-native PCA9685 driver ────────────────────

class _PCA9685:
    """Minimal MicroPython PCA9685 driver — no external dependencies."""

    _MODE1 = 0x00
    _PRESCALE = 0xFE
    _LED0_ON_L = 0x06
    _RESTART = 0x80
    _SLEEP = 0x10

    def __init__(self, i2c, address: int):
        self._i2c = i2c
        self._addr = address
        self._freq_hz = 50
        self.reset()

    def reset(self):
        self._write_reg(self._MODE1, 0x00)

    def set_pwm_freq(self, freq_hz: float):
        prescale = int(25_000_000 / (4096 * freq_hz) - 1)
        prescale = max(3, min(255, prescale))
        old_mode = self._read_reg(self._MODE1)
        self._write_reg(self._MODE1, (old_mode & 0x7F) | self._SLEEP)
        self._write_reg(self._PRESCALE, prescale)
        self._write_reg(self._MODE1, old_mode)
        self._write_reg(self._MODE1, old_mode | self._RESTART)
        self._freq_hz = freq_hz

    def set_pwm(self, channel: int, pulse_us: int):
        """Set PWM output for *channel* to *pulse_us* microseconds."""
        period_us = 1_000_000 / self._freq_hz
        off = int((pulse_us / period_us) * 4095)
        off = max(0, min(4095, off))
        self._write_reg(self._LED0_ON_L + 4 * channel, 0)
        self._write_reg(self._LED0_ON_L + 4 * channel + 2, off & 0xFF)
        self._write_reg(self._LED0_ON_L + 4 * channel + 3, off >> 8)

    def _read_reg(self, reg: int) -> int:
        return self._i2c.readfrom_mem(self._addr, reg, 1)[0]

    def _write_reg(self, reg: int, value: int):
        self._i2c.writeto_mem(self._addr, reg, bytes([value]))


# ── Factory ──────────────────────────────────────────────

def create_servo_driver() -> ServoDriver:
    if config.MOCK_ENABLED:
        return MockServoDriver()
    return PCA9685ServoDriver()

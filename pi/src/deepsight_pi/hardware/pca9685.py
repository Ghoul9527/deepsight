"""PCA9685 16-channel PWM driver via I2C (smbus2)."""

import math
import time


_MODE1 = 0x00
_PRESCALE = 0xFE
_LED0_ON_L = 0x06
_SLEEP = 0x10
_AI = 0x20
_RESTART = 0x80
_ALLCALL = 0x01


class PCA9685:
    def __init__(self, bus: int = 1, address: int = 0x40, freq: float = 50):
        from smbus2 import SMBus
        self._bus = SMBus(bus)
        self._addr = address
        self._freq = freq
        self._period_us = 1_000_000.0 / freq

        self._write_reg(_MODE1, 0x00)  # reset
        self.set_pwm_freq(freq)

    def set_pwm_freq(self, freq: float):
        self._freq = freq
        self._period_us = 1_000_000.0 / freq

        prescale = max(3, min(255,
            round(25_000_000.0 / (4096.0 * freq)) - 1))

        old_mode = self._read_reg(_MODE1)
        self._write_reg(_MODE1, (old_mode | _SLEEP) & 0x7F)
        self._write_reg(_PRESCALE, prescale)
        self._write_reg(_MODE1, old_mode & ~_SLEEP)
        time.sleep(0.001)
        self._write_reg(_MODE1, old_mode | _RESTART | _AI | _ALLCALL)

    def set_pwm(self, channel: int, pulse_us: float):
        """Set PWM pulse width in microseconds on a channel (0-15)."""
        counts_per_us = 4096.0 / self._period_us
        off_count = int(counts_per_us * pulse_us)
        off_count = max(0, min(4095, off_count))

        buf = [
            0x00, 0x00,                    # ON_L, ON_H (always 0)
            off_count & 0xFF,              # OFF_L
            (off_count >> 8) & 0x0F,       # OFF_H
        ]
        reg = _LED0_ON_L + 4 * channel
        self._bus.write_i2c_block_data(self._addr, reg, buf)

    def set_angle(self, channel: int, angle: float,
                  min_us: float = 500, max_us: float = 2500,
                  min_deg: float = 0.0, max_deg: float = 180.0):
        """Set servo angle in degrees, mapped to pulse width range."""
        angle = max(min_deg, min(max_deg, angle))
        pulse_us = min_us + (angle - min_deg) / (max_deg - min_deg) * (max_us - min_us)
        self.set_pwm(channel, pulse_us)

    def _write_reg(self, reg: int, value: int):
        self._bus.write_byte_data(self._addr, reg, value)

    def _read_reg(self, reg: int) -> int:
        return self._bus.read_byte_data(self._addr, reg)

    def close(self):
        self._bus.close()

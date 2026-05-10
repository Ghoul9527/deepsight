"""BME280 environment sensor driver + mock implementation."""

import time

import config
from lib.driver_base import EnvSensorDriver


# ── Mock ─────────────────────────────────────────────────

class MockBME280Driver(EnvSensorDriver):
    def __init__(self):
        super().__init__("bme280_mock")

    def read(self) -> tuple:
        return (32.0, 75.0, 1013.25)


# ── Real BME280 ──────────────────────────────────────────

class BME280Driver(EnvSensorDriver):
    """BME280 temperature / humidity / pressure sensor over I2C.

    Works on MicroPython (machine.I2C) and CPython.
    Implements forced-mode single-shot reading with compensation.
    """

    _REG_ID = 0xD0
    _REG_RESET = 0xE0
    _REG_CTRL_HUM = 0xF2
    _REG_STATUS = 0xF3
    _REG_CTRL_MEAS = 0xF4
    _REG_CONFIG = 0xF5
    _REG_PRESS_MSB = 0xF7

    _CHIP_ID = 0x60
    _CMD_RESET = 0xB6

    def __init__(self):
        super().__init__("bme280_bme280")
        self._i2c = None
        self._addr = config.BME280_I2C_ADDR
        self._cal = {}  # Calibration coefficients parsed at init

    def init(self) -> bool:
        try:
            from machine import I2C, Pin
            self._i2c = I2C(
                0,
                scl=Pin(config.BME280_I2C_SCL_PIN),
                sda=Pin(config.BME280_I2C_SDA_PIN),
                freq=config.BME280_I2C_FREQ,
            )
        except ImportError:
            try:
                import board
                import busio
                self._i2c = busio.I2C(board.SCL, board.SDA)
            except (ImportError, NotImplementedError):
                return False
        except Exception:
            return False

        # Verify chip ID
        try:
            chip_id = self._read_u8(self._REG_ID)
            if chip_id != self._CHIP_ID:
                return False
        except Exception:
            return False

        # Soft reset
        self._write_u8(self._REG_RESET, self._CMD_RESET)
        time.sleep(0.01)

        # Read calibration data
        if not self._load_calibration():
            return False

        # Configure: forced mode, 1x oversampling for all (fast)
        self._write_u8(self._REG_CTRL_HUM, 0x01)
        self._write_u8(self._REG_CTRL_MEAS, 0x01 | 0x01 << 2 | 0x01 << 5)

        super().init()
        return True

    def deinit(self):
        if self._i2c:
            try:
                self._i2c.deinit()
            except AttributeError:
                pass
        super().deinit()

    def read(self) -> tuple:
        """Return (temperature_c, humidity_pct, pressure_hpa)."""
        raw = self._read_raw()
        if raw is None:
            return (25.0, 50.0, 1013.25)

        raw_t, raw_p, raw_h = raw
        temp_c = self._compensate_T(raw_t)
        pressure_hpa = self._compensate_P(raw_p) / 100.0
        humidity_pct = self._compensate_H(raw_h)

        # Humidity depends on temperature
        humidity_pct = self._compensate_H(raw_h, temp_c)

        return (round(temp_c, 1), round(humidity_pct, 1), round(pressure_hpa, 2))

    def _read_raw(self) -> tuple | None:
        """Trigger forced conversion, wait, read 8 bytes."""
        # Trigger measurement
        self._write_u8(self._REG_CTRL_MEAS, 0x01 | 0x01 << 2 | 0x01 << 5 | 0x01)
        time.sleep(0.01)  # ~9.3ms for 1x oversampling

        try:
            data = self._read_bytes(self._REG_PRESS_MSB, 8)
        except Exception:
            return None
        if data is None or len(data) < 8:
            return None

        raw_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_h = (data[6] << 8) | data[7]
        return (raw_t, raw_p, raw_h)

    def _load_calibration(self) -> bool:
        """Read factory calibration coefficients from NVM."""
        try:
            cal1 = self._read_bytes(0x88, 26)
            cal2 = self._read_bytes(0xE1, 7)
        except Exception:
            return False
        if cal1 is None or cal2 is None:
            return False

        c = self._cal
        c['dig_T1'] = _u16(cal1, 0)
        c['dig_T2'] = _s16(cal1, 2)
        c['dig_T3'] = _s16(cal1, 4)
        c['dig_P1'] = _u16(cal1, 6)
        c['dig_P2'] = _s16(cal1, 8)
        c['dig_P3'] = _s16(cal1, 10)
        c['dig_P4'] = _s16(cal1, 12)
        c['dig_P5'] = _s16(cal1, 14)
        c['dig_P6'] = _s16(cal1, 16)
        c['dig_P7'] = _s16(cal1, 18)
        c['dig_P8'] = _s16(cal1, 20)
        c['dig_P9'] = _s16(cal1, 22)
        c['dig_H1'] = cal1[25]
        c['dig_H2'] = _s16(cal2, 0)
        c['dig_H3'] = cal2[2]
        c['dig_H4'] = (cal2[3] << 4) | (cal2[4] & 0x0F)
        c['dig_H5'] = ((cal2[4] >> 4) & 0x0F) | (cal2[5] << 4)
        c['dig_H6'] = _s8(cal2[6])
        return True

    def _compensate_T(self, adc_T: int) -> float:
        c = self._cal
        var1 = ((adc_T / 16384.0) - (c['dig_T1'] / 1024.0)) * c['dig_T2']
        var2 = ((adc_T / 131072.0) - (c['dig_T1'] / 8192.0)) ** 2 * c['dig_T3']
        self._t_fine = var1 + var2
        return (var1 + var2) / 5120.0

    def _compensate_P(self, adc_P: int) -> float:
        c = self._cal
        var1 = self._t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * c['dig_P6'] / 32768.0
        var2 = var2 + var1 * c['dig_P5'] * 2.0
        var2 = var2 / 4.0 + c['dig_P4'] * 65536.0
        var1 = (c['dig_P3'] * var1 * var1 / 524288.0 + c['dig_P2'] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * c['dig_P1']
        if var1 == 0.0:
            return 0.0
        p = 1048576.0 - adc_P
        p = (p - var2 / 4096.0) * 6250.0 / var1
        var1 = c['dig_P9'] * p * p / 2147483648.0
        var2 = p * c['dig_P8'] / 32768.0
        return p + (var1 + var2 + c['dig_P7']) / 16.0

    def _compensate_H(self, adc_H: int, temp_c: float = None) -> float:
        c = self._cal
        h = self._t_fine - 76800.0
        h = (adc_H - (c['dig_H4'] * 64.0 + c['dig_H5'] / 16384.0 * h)) * (
            c['dig_H2'] / 65536.0 * (1.0 + c['dig_H6'] / 67108864.0 * h * (
                1.0 + c['dig_H3'] / 67108864.0 * h))
        )
        h = h * (1.0 - c['dig_H1'] * h / 524288.0)
        return max(0.0, min(100.0, h))

    def _write_u8(self, reg: int, value: int):
        self._i2c.writeto_mem(self._addr, reg, bytes([value]))

    def _read_u8(self, reg: int) -> int:
        return self._i2c.readfrom_mem(self._addr, reg, 1)[0]

    def _read_bytes(self, reg: int, length: int) -> bytes | None:
        try:
            return self._i2c.readfrom_mem(self._addr, reg, length)
        except Exception:
            return None


# ── Helpers ──────────────────────────────────────────────

def _u16(b: bytes, idx: int) -> int:
    return int.from_bytes(b[idx:idx+2], 'little', False)

def _s16(b: bytes, idx: int) -> int:
    val = _u16(b, idx)
    return val - 65536 if val >= 32768 else val

def _s8(v: int) -> int:
    return v - 256 if v >= 128 else v


# ── Factory ──────────────────────────────────────────────

def create_bme280_driver() -> EnvSensorDriver:
    if config.MOCK_ENABLED:
        return MockBME280Driver()
    return BME280Driver()

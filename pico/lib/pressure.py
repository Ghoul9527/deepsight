"""Pressure / depth sensor driver — MS5837-30BA + mock implementation."""

import math
import time

import config
from lib.driver_base import PressureDriver


# ── Mock ─────────────────────────────────────────────────

class MockPressureDriver(PressureDriver):
    def __init__(self):
        super().__init__("pressure_mock")
        self._start_time = time.time()
        self._depth_m = 0.0

    def read(self) -> tuple:
        t = time.time() - self._start_time
        # Simulated freedive profile: 0m → 20m → 0m, 120s cycle
        self._depth_m = 10.0 + 10.0 * math.sin(t * 2 * math.pi / 120.0 - math.pi / 2)
        pressure_mbar = 1013.25 + self._depth_m * 100  # ~10 mbar per cm water
        temp_c = 27.0 - self._depth_m * 0.1
        return (self._depth_m, pressure_mbar, temp_c)


# ── Real MS5837-30BA ─────────────────────────────────────

class MS5837Driver(PressureDriver):
    """MS5837-30BA pressure/depth sensor over I2C (30 bar, 300m rated).

    Works on MicroPython (machine.I2C) or CPython.
    Implements the standard oversampling-and-conversion sequence.
    """

    _CMD_RESET = 0x1E
    _CMD_ADC_READ = 0x00
    _CMD_ADC_CONV = 0x40  # + D1/D2 + OSR bits
    _CMD_PROM_READ = 0xA0  # + 2*idx

    OSR = 8192  # OSR=8192 → 17.2ms conversion time

    def __init__(self):
        super().__init__("pressure_ms5837")
        self._i2c = None
        self._addr = config.PRESSURE_I2C_ADDR
        self._cal = [0] * 8  # 7 calibration coefficients (1-7, 0 unused)

        # Second-order temperature compensation (stateful)
        self._t2 = 0
        self._off2 = 0
        self._sens2 = 0

    def init(self) -> bool:
        try:
            from machine import I2C, Pin
            self._i2c = I2C(
                0,
                scl=Pin(config.PRESSURE_I2C_SCL_PIN),
                sda=Pin(config.PRESSURE_I2C_SDA_PIN),
                freq=config.PRESSURE_I2C_FREQ,
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

        # Reset
        try:
            self._write(self._CMD_RESET)
            time.sleep(0.01)
        except Exception:
            return False

        # Read calibration PROM
        for i in range(1, 8):
            data = self._read(self._CMD_PROM_READ + 2 * i, 2)
            if data is None:
                return False
            self._cal[i] = int.from_bytes(data, 'big')

        # Verify CRC (simple — just check values are non-zero)
        if self._cal[1] == 0:
            return False

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
        """Return (depth_m, pressure_mbar, temperature_c)."""
        if not self.initialized:
            return (0.0, 1013.25, 25.0)
        # Read raw pressure (D1)
        raw_p = self._read_adc(0)  # D1 = pressure
        if raw_p is None:
            return (0.0, 1013.25, 25.0)

        # Read raw temperature (D2)
        raw_t = self._read_adc(1)  # D2 = temperature
        if raw_t is None:
            return (0.0, 1013.25, 25.0)

        c = self._cal
        dT = raw_t - c[5] * 256

        TEMP = 2000 + dT * c[6] // 2 ** 23
        OFF = c[2] * 2 ** 16 + (c[4] * dT) // 2 ** 7
        SENS = c[1] * 2 ** 15 + (c[3] * dT) // 2 ** 8

        # Second-order compensation for low temperatures
        if TEMP < 2000:
            Ti = 3 * dT * dT // 2 ** 33
            OFFi = 3 * (TEMP - 2000) * (TEMP - 2000) // 2
            SENSi = 5 * (TEMP - 2000) * (TEMP - 2000) // 2 ** 3
            if TEMP < -1500:
                OFFi += 7 * (TEMP + 1500) * (TEMP + 1500)
                SENSi += 4 * (TEMP + 1500) * (TEMP + 1500)
        else:
            Ti = 2 * dT * dT // 2 ** 37
            OFFi = (TEMP - 2000) * (TEMP - 2000) // 2 ** 4
            SENSi = 0

        OFF2 = OFF - OFFi
        SENS2 = SENS - SENSi

        # Compensated pressure in mbar (0.01 mbar precision → mbar)
        P = (raw_p * SENS2 // 2 ** 21 - OFF2) // 2 ** 13
        pressure_mbar = P / 10.0  # 0.01 mbar → mbar

        # Compensated temperature in °C
        temp_c = (TEMP - Ti) / 100.0

        # Depth from pressure (freshwater: 1 m = 97.9 mbar, seawater: ~99.6 mbar)
        depth_m = (pressure_mbar - 1013.25) / 97.9
        depth_m = max(0.0, depth_m)

        return (round(depth_m, 2), round(pressure_mbar, 2), round(temp_c, 2))

    def _read_adc(self, d: int) -> int | None:
        """Trigger conversion for D1 (d=0) or D2 (d=1), wait, read 24-bit result."""
        # Determine OSR bits
        osr_map = {256: 0, 512: 2, 1024: 4, 2048: 6, 4096: 8, 8192: 10}
        osr = osr_map.get(self.OSR, 10)
        cmd = self._CMD_ADC_CONV | (d << 4) | osr

        self._write(cmd)
        # Wait: OSR=8192 → ~17.2ms
        time.sleep(0.02)

        data = self._read(self._CMD_ADC_READ, 3)
        if data is None:
            return None
        return int.from_bytes(data, 'big')

    def _write(self, cmd: int):
        self._i2c.writeto(self._addr, bytes([cmd]))

    def _read(self, cmd: int, length: int) -> bytes | None:
        try:
            self._i2c.writeto(self._addr, bytes([cmd]))
            return self._i2c.readfrom(self._addr, length)
        except Exception:
            return None


# ── Factory ──────────────────────────────────────────────

def create_pressure_driver() -> PressureDriver:
    if config.MOCK_ENABLED:
        return MockPressureDriver()
    return MS5837Driver()

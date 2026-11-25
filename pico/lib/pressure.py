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

    OSR = 8192  # Maximum conversion time 18.08 ms; allow 20 ms below.

    def __init__(self):
        super().__init__("pressure_ms5837")
        self._i2c = None
        self._addr = config.PRESSURE_I2C_ADDR
        self._cal = [0] * 8  # W0: factory/CRC; W1-W6: coefficients; W7: CRC padding.
        self.last_error = None

        # Second-order temperature compensation (stateful)
        self._t2 = 0
        self._off2 = 0
        self._sens2 = 0

    def init(self) -> bool:
        self._initialized = False
        self.last_error = None
        try:
            from machine import I2C, Pin
            scl = Pin(config.PRESSURE_I2C_SCL_PIN)
            sda = Pin(config.PRESSURE_I2C_SDA_PIN)
            self._i2c = I2C(
                getattr(config, "PRESSURE_I2C_BUS", 1),
                scl=scl,
                sda=sda,
                freq=config.PRESSURE_I2C_FREQ,
            )
            if config.PRESSURE_I2C_INTERNAL_PULLUP:
                # Only change pulls: preserve the hardware I2C pin function.
                scl.init(pull=Pin.PULL_UP)
                sda.init(pull=Pin.PULL_UP)
        except ImportError:
            try:
                import board
                import busio
                self._i2c = busio.I2C(board.SCL, board.SDA)
            except (ImportError, NotImplementedError) as exc:
                self.last_error = "I2C backend unavailable: %s" % exc
                return False
        except Exception as exc:
            self.last_error = "I2C setup failed: %s" % exc
            return False

        # Reset
        try:
            self._write(self._CMD_RESET)
            time.sleep(0.01)
        except Exception as exc:
            self.last_error = "Reset failed: %s" % exc
            return False

        # Read calibration PROM
        self._cal = [0] * 8
        for i in range(7):
            data = self._read(self._CMD_PROM_READ + 2 * i, 2)
            if data is None:
                self.last_error = "PROM W%d: %s" % (i, self.last_error)
                return False
            self._cal[i] = int.from_bytes(data, 'big')

        # Reject an empty PROM even if its all-zero CRC happens to match.
        if all(c == 0 for c in self._cal[1:7]) or all(c == 0xFFFF for c in self._cal[1:7]):
            self.last_error = "Empty or invalid calibration PROM"
            return False
        expected = self._cal[0] >> 12
        actual = self._crc4(self._cal)
        if actual != expected:
            self.last_error = "PROM CRC mismatch: expected %d, calculated %d" % (expected, actual)
            return False

        super().init()
        return True

    @staticmethod
    def _crc4(coefficients):
        """MS5837 CRC-4 over W0-W6 and a zero padding word; preserve input."""
        words = list(coefficients[:7]) + [0]
        words[0] &= 0x0FFF
        remainder = 0
        for byte_index in range(16):
            word = words[byte_index // 2]
            remainder ^= (word & 0xFF) if byte_index % 2 else (word >> 8)
            for _ in range(8):
                if remainder & 0x8000:
                    remainder = (remainder << 1) ^ 0x3000
                else:
                    remainder <<= 1
                remainder &= 0xFFFF
        return (remainder >> 12) & 0x0F

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
            raise OSError(self.last_error or "Pressure sensor not initialized")
        # Read raw pressure (D1)
        raw_p = self._read_adc(0)  # D1 = pressure
        if raw_p is None:
            raise OSError(self.last_error or "Pressure ADC read failed")

        # Read raw temperature (D2)
        raw_t = self._read_adc(1)  # D2 = temperature
        if raw_t is None:
            raise OSError(self.last_error or "Temperature ADC read failed")

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

        # MS5837-30BA pressure result has 0.1 mbar units.
        P = (raw_p * SENS2 // 2 ** 21 - OFF2) // 2 ** 13
        pressure_mbar = P / 10.0

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

        try:
            self._write(cmd)
        except Exception as exc:
            self.last_error = "ADC conversion command 0x%02X failed: %s" % (cmd, exc)
            return None
        # OSR=8192 maximum is 18.08 ms.
        time.sleep(0.02)

        data = self._read(self._CMD_ADC_READ, 3)
        if data is None:
            return None
        value = int.from_bytes(data, 'big')
        if value in (0, 0xFFFFFF):
            self.last_error = "Invalid ADC result: 0x%06X" % value
            return None
        self.last_error = None
        return value

    def _write(self, cmd: int):
        self._i2c.writeto(self._addr, bytes([cmd]))

    def _read(self, cmd: int, length: int) -> bytes | None:
        try:
            # Keep the transaction open for a repeated START into the read.
            self._i2c.writeto(self._addr, bytes([cmd]), False)
            data = self._i2c.readfrom(self._addr, length)
            if len(data) != length:
                self.last_error = "Short read at 0x%02X" % cmd
                return None
            return data
        except Exception as exc:
            self.last_error = "Read 0x%02X failed: %s" % (cmd, exc)
            return None


# ── Factory ──────────────────────────────────────────────

def create_pressure_driver() -> PressureDriver:
    if config.MOCK_ENABLED:
        return MockPressureDriver()
    return MS5837Driver()

"""IMU driver — MPU6050 (6-axis) + mock implementation."""

import math
import time

import config
from lib.driver_base import IMUDriver


# ── Mock ─────────────────────────────────────────────────

class MockIMUDriver(IMUDriver):
    def __init__(self):
        super().__init__("imu_mock")
        self._start_time = time.time()
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0

    def read(self) -> tuple:
        t = time.time() - self._start_time
        self._yaw = math.sin(t * 0.2) * 2.0
        self._pitch = math.sin(t * 0.15 + 0.5) * 5.0
        self._roll = math.sin(t * 0.1 + 1.0) * 3.0
        return (self._yaw, self._pitch, self._roll, 0.0, 0.0, 9.81)


# ── Real MPU6050 ─────────────────────────────────────────

class MPU6050Driver(IMUDriver):
    """MPU6050 6-axis IMU over I2C.

    Works on MicroPython (machine.I2C) or CPython with adafruit-circuitpython-mpu6050.
    Includes simple complementary-filter attitude estimation.
    """

    _REG_PWR_MGMT_1 = 0x6B
    _REG_ACCEL_XOUT_H = 0x3B
    _REG_GYRO_CONFIG = 0x1B
    _REG_ACCEL_CONFIG = 0x1C

    def __init__(self):
        super().__init__("imu_mpu6050")
        self._i2c = None
        self._addr = config.IMU_I2C_ADDR
        self._gyro_scale = config.IMU_GYRO_SCALE
        self._accel_scale = config.IMU_ACCEL_SCALE

        # Attitude state
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0
        self._last_time = time.time()

    def init(self) -> bool:
        try:
            from machine import I2C, Pin
            self._i2c = I2C(
                0,
                scl=Pin(config.IMU_I2C_SCL_PIN),
                sda=Pin(config.IMU_I2C_SDA_PIN),
                freq=config.IMU_I2C_FREQ,
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

        # Wake up from sleep
        try:
            self._write_reg(self._REG_PWR_MGMT_1, 0x00)
            # Set gyro scale (±250 °/s)
            self._write_reg(self._REG_GYRO_CONFIG, 0x00)
            # Set accel scale (±2 g)
            self._write_reg(self._REG_ACCEL_CONFIG, 0x00)
        except Exception:
            return False

        self._last_time = time.time()
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
        raw = self._read_sensors()
        if raw is None:
            return (self._yaw, self._pitch, self._roll, 0.0, 0.0, 9.81)

        ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps = raw
        now = time.time()
        dt = max(now - self._last_time, 0.001)
        self._last_time = now

        # Complementary filter — 98% gyro integration, 2% accel correction
        alpha = 0.98

        # Accelerometer roll / pitch (gravity vector)
        accel_roll = math.atan2(ay_g, az_g) * 180.0 / math.pi
        accel_pitch = math.atan2(-ax_g, math.sqrt(ay_g * ay_g + az_g * az_g)) * 180.0 / math.pi

        # Gyro integration
        self._roll += gx_dps * dt
        self._pitch += gy_dps * dt
        self._yaw += gz_dps * dt

        # Fuse
        self._roll = alpha * self._roll + (1 - alpha) * accel_roll
        self._pitch = alpha * self._pitch + (1 - alpha) * accel_pitch

        return (self._yaw, self._pitch, self._roll, ax_g, ay_g, az_g)

    def _read_sensors(self) -> tuple | None:
        """Read raw 6-axis data from MPU6050. Returns (ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps)."""
        try:
            data = self._read_reg(self._REG_ACCEL_XOUT_H, 14)
        except Exception:
            return None

        def _s16(b: bytes, idx: int) -> int:
            val = int.from_bytes(b[idx:idx+2], 'big', True)
            if val >= 0x8000:
                val -= 0x10000
            return val

        raw_ax = _s16(data, 0)
        raw_ay = _s16(data, 2)
        raw_az = _s16(data, 4)
        raw_gx = _s16(data, 8)
        raw_gy = _s16(data, 10)
        raw_gz = _s16(data, 12)

        # Convert to physical units
        accel_sens = 16384.0  # LSB/g for ±2g
        gyro_sens = 131.0     # LSB/(°/s) for ±250°/s

        ax_g = raw_ax / accel_sens
        ay_g = raw_ay / accel_sens
        az_g = raw_az / accel_sens
        gx_dps = raw_gx / gyro_sens
        gy_dps = raw_gy / gyro_sens
        gz_dps = raw_gz / gyro_sens

        return (ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps)

    def _write_reg(self, reg: int, value: int):
        self._i2c.writeto_mem(self._addr, reg, bytes([value]))

    def _read_reg(self, reg: int, length: int = 1) -> bytes:
        self._i2c.writeto(self._addr, bytes([reg]))
        return self._i2c.readfrom(self._addr, length)


# ── Factory ──────────────────────────────────────────────

def create_imu_driver() -> IMUDriver:
    if config.MOCK_ENABLED:
        return MockIMUDriver()
    return MPU6050Driver()

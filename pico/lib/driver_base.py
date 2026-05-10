"""ABC base classes for all Pico hardware drivers.

Each driver type has an abstract interface so mock and real implementations
are interchangeable. All shared behaviour lives in BaseDriver.
"""


class BaseDriver:
    """Common init/deinit lifecycle for every driver."""

    def __init__(self, name: str = "driver"):
        self.name = name
        self._initialized = False

    def init(self) -> bool:
        """Power on / configure the peripheral.  Return True on success."""
        self._initialized = True
        return True

    def deinit(self):
        """Power down / release resources."""
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized


# ── Servo ────────────────────────────────────────────────

class ServoDriver(BaseDriver):
    """Abstract driver for multi-channel servo control (PCA9685 or mock)."""

    def __init__(self, name: str = "servo"):
        super().__init__(name)

    def set_angle(self, servo_id: int, angle_deg: float):
        """Set a single servo to *angle_deg* (0–180, clamped by implementation)."""
        raise NotImplementedError

    def get_angle(self, servo_id: int) -> float:
        """Return the last-set angle for *servo_id*."""
        raise NotImplementedError

    def get_all_positions(self) -> list:
        """Return a list of all servo angles."""
        raise NotImplementedError


# ── IMU ───────────────────────────────────────────────────

class IMUDriver(BaseDriver):
    """Abstract 6-axis IMU (MPU6050 or mock)."""

    def __init__(self, name: str = "imu"):
        super().__init__(name)

    def read(self) -> tuple:
        """Return (yaw_deg, pitch_deg, roll_deg, accel_x_g, accel_y_g, accel_z_g)."""
        raise NotImplementedError


# ── Pressure / Depth ─────────────────────────────────────

class PressureDriver(BaseDriver):
    """Abstract pressure/depth sensor (MS5837 or mock)."""

    def __init__(self, name: str = "pressure"):
        super().__init__(name)

    def read(self) -> tuple:
        """Return (depth_m, pressure_mbar, temperature_c)."""
        raise NotImplementedError


# ── Environment (BME280) ─────────────────────────────────

class EnvSensorDriver(BaseDriver):
    """Abstract environmental sensor (BME280 or mock)."""

    def __init__(self, name: str = "env"):
        super().__init__(name)

    def read(self) -> tuple:
        """Return (temperature_c, humidity_pct, pressure_hpa)."""
        raise NotImplementedError


# ── Leak sensor ──────────────────────────────────────────

class LeakSensorDriver(BaseDriver):
    """Abstract multi-channel leak detector (ADC pins or mock)."""

    def __init__(self, name: str = "leak"):
        super().__init__(name)

    def read_all(self) -> list[bool]:
        """Return a list of bools, one per channel (True = wet)."""
        raise NotImplementedError

    def is_wet(self, channel: int) -> bool:
        """Return True if *channel* is wet."""
        raise NotImplementedError


# ── Lighting ─────────────────────────────────────────────

class LightingDriver(BaseDriver):
    """Abstract multi-channel lighting PWM controller."""

    def __init__(self, name: str = "lighting"):
        super().__init__(name)

    def set_brightness(self, channel: int, brightness: float):
        """Set *channel* brightness (0.0 = off, 1.0 = full)."""
        raise NotImplementedError

    def get_brightness(self, channel: int) -> float:
        """Return current brightness for *channel*."""
        raise NotImplementedError

    def set_all(self, brightness: float):
        """Set every channel to *brightness*."""
        raise NotImplementedError

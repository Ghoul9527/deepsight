"""Pico configuration.

In MicroPython: edit the constants directly (no YAML parser available).
In CPython mock mode: values can be overridden by loading pico_config.yaml.
"""

import os as _os

# ── Control loop ──────────────────────────────────────────
CONTROL_LOOP_HZ = 50
CONTROL_LOOP_DT = 1.0 / CONTROL_LOOP_HZ

# ── Serial ────────────────────────────────────────────────
SERIAL_BAUD = 115200

# ── Mock mode ─────────────────────────────────────────────
MOCK_ENABLED = True

# ── Safety ────────────────────────────────────────────────
NO_COMMAND_TIMEOUT_S = 1.0
DEFAULT_SERVO_ANGLE = 90.0
MAX_SERVO_ANGLE = 180.0
MIN_SERVO_ANGLE = 0.0

# ── Servo (PCA9685, I2C) ─────────────────────────────────
SERVO_I2C_ADDR = 0x40
SERVO_I2C_SCL_PIN = 5
SERVO_I2C_SDA_PIN = 4
SERVO_I2C_FREQ = 100000
SERVO_COUNT = 16
SERVO_PWM_FREQ = 50
SERVO_PULSE_MIN_US = 500
SERVO_PULSE_MAX_US = 2500

# ── IMU (MPU6050, I2C) ───────────────────────────────────
IMU_I2C_ADDR = 0x68
IMU_I2C_SCL_PIN = 5
IMU_I2C_SDA_PIN = 4
IMU_I2C_FREQ = 400000
IMU_GYRO_SCALE = 250   # deg/s
IMU_ACCEL_SCALE = 2    # g

# ── Pressure / Depth (MS5837-30BA, I2C) ──────────────────
PRESSURE_I2C_ADDR = 0x76
PRESSURE_I2C_SCL_PIN = 5
PRESSURE_I2C_SDA_PIN = 4
PRESSURE_I2C_FREQ = 400000

# ── Environment (BME280, I2C) ────────────────────────────
BME280_I2C_ADDR = 0x77
BME280_I2C_SCL_PIN = 5
BME280_I2C_SDA_PIN = 4
BME280_I2C_FREQ = 400000

# ── Lighting (PWM) ───────────────────────────────────────
LIGHTING_CHANNELS = 4
LIGHTING_PWM_FREQ = 1000
LIGHTING_PWM_PINS = [0, 1, 2, 3]

# ── Leak sensor (ADC) ────────────────────────────────────
LEAK_CHANNELS = 4
LEAK_ADC_PINS = [26, 27, 28, 29]
LEAK_WET_THRESHOLD = 1.5  # volts, below = wet


def _load_yaml_overrides():
    """Try to load pico_config.yaml for CPython mock mode.

    MicroPython has no yaml module; this is a no-op there.
    """
    try:
        import yaml
    except ImportError:
        return

    yaml_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "..", "..", "configs", "pico_config.yaml",
    )
    try:
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f)
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return

    g = globals()
    if cfg:
        g["MOCK_ENABLED"] = _yaml_get(cfg, "mock", "enabled", True)
    g["SERIAL_BAUD"] = _yaml_get(cfg, "pico", "serial_baud", g["SERIAL_BAUD"])
    g["CONTROL_LOOP_HZ"] = _yaml_get(cfg, "control_loop", "frequency_hz", g["CONTROL_LOOP_HZ"])
    g["CONTROL_LOOP_DT"] = 1.0 / g["CONTROL_LOOP_HZ"]
    g["NO_COMMAND_TIMEOUT_S"] = _yaml_get(cfg, "safety", "no_command_timeout_s", g["NO_COMMAND_TIMEOUT_S"])
    g["DEFAULT_SERVO_ANGLE"] = _yaml_get(cfg, "safety", "default_servo_angle", g["DEFAULT_SERVO_ANGLE"])
    g["MAX_SERVO_ANGLE"] = _yaml_get(cfg, "safety", "max_servo_angle", g["MAX_SERVO_ANGLE"])
    g["MIN_SERVO_ANGLE"] = _yaml_get(cfg, "safety", "min_servo_angle", g["MIN_SERVO_ANGLE"])
    g["SERVO_I2C_ADDR"] = _yaml_get(cfg, "servo", "i2c_address", g["SERVO_I2C_ADDR"])
    g["IMU_I2C_ADDR"] = _yaml_get(cfg, "imu", "i2c_address", g["IMU_I2C_ADDR"])
    g["PRESSURE_I2C_ADDR"] = _yaml_get(cfg, "pressure", "i2c_address", g["PRESSURE_I2C_ADDR"])
    g["BME280_I2C_ADDR"] = _yaml_get(cfg, "bme280", "i2c_address", g["BME280_I2C_ADDR"])
    g["LIGHTING_PWM_FREQ"] = _yaml_get(cfg, "lighting", "pwm_freq_hz", g["LIGHTING_PWM_FREQ"])
    g["LEAK_CHANNELS"] = _yaml_get(cfg, "leak_sensor", "channels", g["LEAK_CHANNELS"])


def _yaml_get(cfg, section, key, default):
    try:
        return cfg.get(section, {}).get(key, default)
    except AttributeError:
        return default


# Attempt YAML override at import time (no-op on MicroPython)
_load_yaml_overrides()

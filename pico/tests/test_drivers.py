"""Test pico hardware drivers — mock implementations."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config


class TestMockServoDriver:
    def test_init(self):
        from lib.servo import MockServoDriver
        s = MockServoDriver()
        assert s.init() is True
        assert s.initialized is True
        assert len(s.get_all_positions()) == config.SERVO_COUNT

    def test_set_and_get_angle(self):
        from lib.servo import MockServoDriver
        s = MockServoDriver()
        s.set_angle(0, 90.0)
        assert s.get_angle(0) == 90.0
        assert s.get_angle(1) == config.DEFAULT_SERVO_ANGLE

    def test_angle_clamping(self):
        from lib.servo import MockServoDriver
        s = MockServoDriver()
        s.set_angle(0, 200.0)
        assert s.get_angle(0) == config.MAX_SERVO_ANGLE
        s.set_angle(0, -10.0)
        assert s.get_angle(0) == config.MIN_SERVO_ANGLE

    def test_get_all_positions(self):
        from lib.servo import MockServoDriver
        s = MockServoDriver()
        s.set_angle(0, 45.0)
        s.set_angle(1, 135.0)
        positions = s.get_all_positions()
        assert positions[0] == 45.0
        assert positions[1] == 135.0

    def test_deinit(self):
        from lib.servo import MockServoDriver
        s = MockServoDriver()
        s.init()
        s.deinit()
        assert s.initialized is False


class TestMockIMUDriver:
    def test_read_returns_six_values(self):
        from lib.imu import MockIMUDriver
        imu = MockIMUDriver()
        imu.init()
        yaw, pitch, roll, ax, ay, az = imu.read()
        assert isinstance(yaw, (int, float))
        assert isinstance(pitch, (int, float))
        assert isinstance(roll, (int, float))
        assert -180.0 <= yaw <= 180.0 or yaw == 0.0
        assert -90.0 <= pitch <= 90.0 or pitch == 0.0


class TestMockPressureDriver:
    def test_read_returns_three_values(self):
        from lib.pressure import MockPressureDriver
        p = MockPressureDriver()
        p.init()
        depth, pressure, temp = p.read()
        assert isinstance(depth, (int, float))
        assert depth >= 0.0
        assert pressure >= 0.0


class TestMockBME280Driver:
    def test_read_returns_three_values(self):
        from lib.bme280 import MockBME280Driver
        bme = MockBME280Driver()
        bme.init()
        temp, humidity, pressure = bme.read()
        assert isinstance(temp, (int, float))
        assert 0.0 <= humidity <= 100.0
        assert pressure > 0


class TestMockLeakSensor:
    def test_all_dry_by_default(self):
        from lib.leak_sensor import MockLeakSensor
        leak = MockLeakSensor()
        leak.init()
        for channel in range(config.LEAK_CHANNELS):
            assert leak.is_wet(channel) is False

    def test_read_all(self):
        from lib.leak_sensor import MockLeakSensor
        leak = MockLeakSensor()
        leak.init()
        results = leak.read_all()
        assert len(results) == config.LEAK_CHANNELS
        assert all(r is False for r in results)


class TestMockLightingDriver:
    def test_set_and_get_brightness(self):
        from lib.lighting import MockLightingDriver
        lt = MockLightingDriver()
        lt.init()
        lt.set_brightness(0, 0.75)
        assert lt.get_brightness(0) == 0.75

    def test_brightness_clamping(self):
        from lib.lighting import MockLightingDriver
        lt = MockLightingDriver()
        lt.set_brightness(0, 1.5)
        assert lt.get_brightness(0) == 1.0
        lt.set_brightness(0, -0.5)
        assert lt.get_brightness(0) == 0.0

    def test_set_all(self):
        from lib.lighting import MockLightingDriver
        lt = MockLightingDriver()
        lt.set_all(0.5)
        for ch in range(config.LIGHTING_CHANNELS):
            assert lt.get_brightness(ch) == 0.5

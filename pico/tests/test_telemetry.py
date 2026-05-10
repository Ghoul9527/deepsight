"""Test Pico telemetry message formatting."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json


class TestTelemetry:
    def test_make_telemetry_structure(self):
        import telemetry
        msg = telemetry.make_telemetry("tel.test", {"value": 42})
        parsed = json.loads(msg)
        assert parsed["node_id"] == "pico"
        assert parsed["type"] == "tel.test"
        assert parsed["version"] == "1.0"
        assert parsed["payload"]["value"] == 42
        assert "timestamp_ns" in parsed
        assert "msg_id" in parsed

    def test_tel_imu_format(self):
        import telemetry
        msg = telemetry.tel_imu(15.0, -3.0, 1.5, 0.1, 0.2, 1.0)
        parsed = json.loads(msg)
        assert parsed["type"] == "tel.imu"
        assert parsed["payload"]["yaw"] == 15.0
        assert parsed["payload"]["pitch"] == -3.0
        assert parsed["payload"]["roll"] == 1.5
        assert parsed["payload"]["accel_x"] == 0.1

    def test_tel_depth_format(self):
        import telemetry
        msg = telemetry.tel_depth(12.5, 2234.0, 24.3)
        parsed = json.loads(msg)
        assert parsed["type"] == "tel.depth"
        assert parsed["payload"]["depth_m"] == 12.5
        assert parsed["payload"]["pressure_mbar"] == 2234.0
        assert parsed["payload"]["temperature_c"] == 24.3

    def test_tel_env_format(self):
        import telemetry
        msg = telemetry.tel_env(31.2, 45.0, 1013.0)
        parsed = json.loads(msg)
        assert parsed["type"] == "tel.env"
        assert parsed["payload"]["temperature_c"] == 31.2

    def test_tel_leak_format(self):
        import telemetry
        msg = telemetry.tel_leak(0, True)
        parsed = json.loads(msg)
        assert parsed["type"] == "tel.leak"
        assert parsed["payload"]["channel"] == 0
        assert parsed["payload"]["wet"] is True

    def test_tel_heartbeat_format(self):
        import telemetry
        msg = telemetry.tel_heartbeat()
        parsed = json.loads(msg)
        assert parsed["type"] == "sys.heartbeat"

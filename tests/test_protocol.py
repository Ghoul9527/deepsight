"""Tests for the shared protocol library."""

import json

import pytest

from deepsight_shared.protocol import (
    Message,
    new_message,
    make_heartbeat,
    cmd_servo_set,
    cmd_winch_set,
    cmd_winch_stop,
    tel_imu,
    tel_depth,
    tel_winch_state,
    sys_ack,
    sys_error,
    sys_safety,
    validate_message,
    PROTOCOL_VERSION,
)
from deepsight_shared.constants import NodeId, SafetyState


class TestMessageSerialization:
    def test_message_to_json(self):
        msg = new_message("host", "sys.heartbeat", {})
        data = msg.to_json()
        parsed = json.loads(data)
        assert parsed["node_id"] == "host"
        assert parsed["type"] == "sys.heartbeat"
        assert parsed["version"] == PROTOCOL_VERSION
        assert "msg_id" in parsed
        assert "timestamp_ns" in parsed

    def test_message_from_json(self):
        raw = json.dumps({
            "msg_id": "abc123",
            "timestamp_ns": 1000000000,
            "node_id": "pi",
            "type": "sys.heartbeat",
            "version": "1.0",
            "payload": {},
        })
        msg = Message.from_json(raw)
        assert msg.msg_id == "abc123"
        assert msg.node_id == "pi"
        assert msg.type == "sys.heartbeat"

    def test_message_roundtrip(self):
        msg = cmd_servo_set("host", 1, 45.0)
        restored = Message.from_json(msg.to_json())
        assert restored.type == "cmd.servo.set"
        assert restored.payload["servo_id"] == 1
        assert restored.payload["angle"] == 45.0

    def test_message_bytes_roundtrip(self):
        msg = new_message("pico", "tel.imu", {"yaw": 1.5})
        data = msg.to_bytes()
        restored = Message.from_bytes(data)
        assert restored.type == "tel.imu"
        assert restored.payload["yaw"] == 1.5


class TestMessageFactories:
    def test_heartbeat(self):
        msg = make_heartbeat("pi")
        assert msg.type == "sys.heartbeat"
        assert msg.node_id == "pi"

    def test_servo_command(self):
        msg = cmd_servo_set("host", 3, 120.0, speed=30.0)
        assert msg.type == "cmd.servo.set"
        assert msg.payload["servo_id"] == 3
        assert msg.payload["angle"] == 120.0
        assert msg.payload["speed"] == 30.0

    def test_winch_set(self):
        msg = cmd_winch_set("host", 0.5, "up")
        assert msg.type == "cmd.winch.set"
        assert msg.payload["speed"] == 0.5
        assert msg.payload["direction"] == "up"

    def test_winch_stop(self):
        msg = cmd_winch_stop("host")
        assert msg.type == "cmd.winch.stop"

    def test_imu_telemetry(self):
        msg = tel_imu("pico", 1.2, 0.3, -0.2)
        assert msg.type == "tel.imu"
        assert msg.payload["yaw"] == 1.2
        assert msg.payload["pitch"] == 0.3

    def test_depth_telemetry(self):
        msg = tel_depth("pico", 12.3, pressure_mbar=2200.0, temperature_c=25.0)
        assert msg.type == "tel.depth"
        assert msg.payload["depth_m"] == 12.3
        assert msg.payload["temperature_c"] == 25.0

    def test_winch_telemetry(self):
        msg = tel_winch_state("stm32", 1000.0, 50.0, False, False, False)
        assert msg.type == "tel.winch_state"
        assert msg.payload["limit_top"] is False

    def test_ack(self):
        msg = sys_ack("pi", "ref-123")
        assert msg.type == "sys.ack"
        assert msg.payload["ref_msg_id"] == "ref-123"

    def test_error(self):
        msg = sys_error("stm32", "E_STOP", "Emergency stop active")
        assert msg.type == "sys.error"
        assert msg.payload["code"] == "E_STOP"

    def test_safety(self):
        msg = sys_safety("host", "emergency")
        assert msg.type == "sys.safety"
        assert msg.payload["state"] == "emergency"


class TestValidation:
    def test_valid_message(self):
        msg = make_heartbeat("host")
        errors = validate_message(msg)
        assert len(errors) == 0

    def test_invalid_node_id(self):
        msg = new_message("unknown_node", "sys.heartbeat")
        errors = validate_message(msg)
        assert any("node_id" in e for e in errors)

    def test_unknown_message_type(self):
        msg = new_message("host", "custom.unknown.type")
        errors = validate_message(msg)
        assert any("message type" in e for e in errors)

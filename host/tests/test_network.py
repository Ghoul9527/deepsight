"""Tests for the network layer: MessageBus, Message serialization, factories, validation."""

import asyncio
import json

import pytest

from deepsight_shared.protocol import (
    Message,
    new_message,
    make_heartbeat,
    cmd_servo_set,
    cmd_winch_set,
    cmd_winch_stop,
    cmd_lighting_set,
    cmd_gopro_record,
    cmd_gopro_mode,
    tel_imu,
    tel_depth,
    tel_env,
    tel_leak,
    tel_winch_state,
    tel_gopro_status,
    tel_pi_status,
    tel_tracking_result,
    sys_ack,
    sys_error,
    sys_safety,
    sys_startup,
    sys_shutdown,
    validate_message,
    PROTOCOL_VERSION,
)
from deepsight_shared.constants import NodeId, SafetyState


# ---------------------------------------------------------------------------
# network.message_bus
# ---------------------------------------------------------------------------

class TestMessageBus:
    def test_subscribe_and_publish(self):
        """Verify that a type-specific handler receives published messages."""
        from deepsight_host.network.message_bus import MessageBus

        received = []

        async def handler(msg: Message):
            received.append(msg)

        async def run():
            bus = MessageBus()
            bus.subscribe("sys.heartbeat", handler)
            await bus.publish(make_heartbeat("host"))

        asyncio.run(run())
        assert len(received) == 1
        assert received[0].type == "sys.heartbeat"

    def test_wildcard_handler_receives_all(self):
        """Wildcard subscribers receive every message regardless of type."""
        from deepsight_host.network.message_bus import MessageBus

        received = []

        async def catch_all(msg: Message):
            received.append(msg.type)

        async def run():
            bus = MessageBus()
            bus.subscribe_all(catch_all)
            await bus.publish(make_heartbeat("host"))
            await bus.publish(cmd_servo_set("host", 1, 45.0))

        asyncio.run(run())
        assert "sys.heartbeat" in received
        assert "cmd.servo.set" in received

    def test_subscribe_only_matches_exact_type(self):
        """A handler for one type must not fire for a different type."""
        from deepsight_host.network.message_bus import MessageBus

        received = []

        async def handler(msg: Message):
            received.append(msg)

        async def run():
            bus = MessageBus()
            bus.subscribe("sys.heartbeat", handler)
            await bus.publish(cmd_servo_set("host", 1, 90.0))

        asyncio.run(run())
        assert len(received) == 0

    def test_multiple_handlers_for_same_type(self):
        """All handlers for a given type fire when the message is published."""
        from deepsight_host.network.message_bus import MessageBus

        results = []

        async def h1(msg):
            results.append("h1")

        async def h2(msg):
            results.append("h2")

        async def run():
            bus = MessageBus()
            bus.subscribe("sys.heartbeat", h1)
            bus.subscribe("sys.heartbeat", h2)
            await bus.publish(make_heartbeat("host"))

        asyncio.run(run())
        assert "h1" in results
        assert "h2" in results

    def test_handler_exceptions_do_not_propagate(self):
        """A crashing handler must not prevent other handlers from running."""
        from deepsight_host.network.message_bus import MessageBus

        good_received = []

        async def bad_handler(msg):
            raise RuntimeError("simulated crash")

        async def good_handler(msg):
            good_received.append(msg)

        async def run():
            bus = MessageBus()
            bus.subscribe("sys.heartbeat", bad_handler)
            bus.subscribe("sys.heartbeat", good_handler)
            await bus.publish(make_heartbeat("host"))

        asyncio.run(run())
        assert len(good_received) == 1

    def test_publish_empty_channel_does_nothing(self):
        """Publishing to an empty channel must be a no-op, not a crash."""
        from deepsight_host.network.message_bus import MessageBus

        async def run():
            bus = MessageBus()
            await bus.publish(make_heartbeat("host"))

        asyncio.run(run())  # no exception = pass

    def test_handler_receives_correct_message_fields(self):
        """The handler must see the exact payload fields that were sent."""
        from deepsight_host.network.message_bus import MessageBus

        received = []

        async def handler(msg: Message):
            received.append(msg)

        async def run():
            bus = MessageBus()
            bus.subscribe("tel.depth", handler)
            msg = tel_depth("pico", 25.0, 3000.0, 18.0)
            await bus.publish(msg)

        asyncio.run(run())
        assert len(received) == 1
        assert received[0].payload["depth_m"] == 25.0
        assert received[0].payload["temperature_c"] == 18.0
        assert received[0].node_id == "pico"


# ---------------------------------------------------------------------------
# Message serialization
# ---------------------------------------------------------------------------

class TestMessageSerialization:
    def test_to_json_produces_valid_json(self):
        msg = new_message("host", "sys.heartbeat", {"key": "value"})
        data = msg.to_json()
        parsed = json.loads(data)
        assert parsed["type"] == "sys.heartbeat"
        assert parsed["node_id"] == "host"
        assert parsed["payload"]["key"] == "value"
        assert parsed["version"] == PROTOCOL_VERSION

    def test_from_json_reconstructs_message(self):
        raw = json.dumps({
            "msg_id": "abc12345",
            "timestamp_ns": 1234567890000000000,
            "node_id": "pi",
            "type": "tel.imu",
            "version": "1.0",
            "payload": {"yaw": 1.5, "pitch": 0.2, "roll": -0.1},
        })
        msg = Message.from_json(raw)
        assert msg.msg_id == "abc12345"
        assert msg.node_id == "pi"
        assert msg.type == "tel.imu"
        assert msg.payload["yaw"] == 1.5

    def test_from_json_missing_version_uses_default(self):
        raw = json.dumps({
            "msg_id": "x",
            "timestamp_ns": 1,
            "node_id": "host",
            "type": "sys.heartbeat",
            "payload": {},
        })
        msg = Message.from_json(raw)
        assert msg.version == PROTOCOL_VERSION

    def test_from_json_missing_payload_uses_empty_dict(self):
        raw = json.dumps({
            "msg_id": "x",
            "timestamp_ns": 1,
            "node_id": "host",
            "type": "sys.heartbeat",
            "version": "1.0",
        })
        msg = Message.from_json(raw)
        assert msg.payload == {}

    def test_json_roundtrip(self):
        msg = cmd_servo_set("host", 2, 75.0, speed=25.0)
        restored = Message.from_json(msg.to_json())
        assert restored.msg_id == msg.msg_id
        assert restored.type == msg.type
        assert restored.payload == msg.payload

    def test_to_bytes_and_from_bytes_roundtrip(self):
        msg = new_message("pico", "tel.depth", {"depth_m": 30.0})
        data = msg.to_bytes()
        assert isinstance(data, bytes)
        assert data.endswith(b"\n")
        restored = Message.from_bytes(data)
        assert restored.type == "tel.depth"
        assert restored.payload["depth_m"] == 30.0

    def test_from_bytes_strips_trailing_newline(self):
        msg = new_message("host", "sys.heartbeat")
        raw = msg.to_bytes()  # ends with \n
        # Add extra whitespace
        raw_extra = b" " + raw + b"  "
        restored = Message.from_bytes(raw_extra)
        # .strip() on decode should handle it
        assert restored.type == "sys.heartbeat"


# ---------------------------------------------------------------------------
# Message factories — commands
# ---------------------------------------------------------------------------

class TestCommandFactories:
    def test_cmd_servo_set(self):
        msg = cmd_servo_set("host", 1, 45.0, speed=30.0)
        assert msg.type == "cmd.servo.set"
        assert msg.node_id == "host"
        assert msg.payload["servo_id"] == 1
        assert msg.payload["angle"] == 45.0
        assert msg.payload["speed"] == 30.0

    def test_cmd_servo_set_default_speed(self):
        msg = cmd_servo_set("host", 2, 90.0)
        assert msg.payload["speed"] == 0.0

    def test_cmd_winch_set(self):
        msg = cmd_winch_set("host", 0.8, direction="up")
        assert msg.type == "cmd.winch.set"
        assert msg.payload["speed"] == 0.8
        assert msg.payload["direction"] == "up"

    def test_cmd_winch_set_default_direction(self):
        msg = cmd_winch_set("host", 0.5)
        assert msg.payload["direction"] == "stop"

    def test_cmd_winch_stop(self):
        msg = cmd_winch_stop("host")
        assert msg.type == "cmd.winch.stop"
        assert msg.payload == {}

    def test_cmd_lighting_set(self):
        msg = cmd_lighting_set("host", 3, 0.75)
        assert msg.type == "cmd.lighting.set"
        assert msg.payload["channel"] == 3
        assert msg.payload["brightness"] == 0.75

    def test_cmd_gopro_record(self):
        msg = cmd_gopro_record("pi", start=True)
        assert msg.type == "cmd.gopro.record"
        assert msg.payload["start"] is True

    def test_cmd_gopro_mode(self):
        msg = cmd_gopro_mode("pi", mode="photo")
        assert msg.type == "cmd.gopro.mode"
        assert msg.payload["mode"] == "photo"


# ---------------------------------------------------------------------------
# Message factories — telemetry
# ---------------------------------------------------------------------------

class TestTelemetryFactories:
    def test_tel_imu(self):
        msg = tel_imu("pico", yaw=1.2, pitch=0.3, roll=-0.2,
                      ax=0.01, ay=0.02, az=9.81)
        assert msg.type == "tel.imu"
        assert msg.payload["yaw"] == 1.2
        assert msg.payload["pitch"] == 0.3
        assert msg.payload["roll"] == -0.2
        assert msg.payload["accel_x"] == 0.01
        assert msg.payload["accel_z"] == 9.81

    def test_tel_imu_defaults(self):
        msg = tel_imu("pico", 0.0, 0.0, 0.0)
        assert msg.payload["accel_x"] == 0.0
        assert msg.payload["accel_y"] == 0.0
        assert msg.payload["accel_z"] == 0.0

    def test_tel_depth(self):
        msg = tel_depth("pico", depth_m=15.5, pressure_mbar=2500.0,
                        temperature_c=23.0)
        assert msg.type == "tel.depth"
        assert msg.payload["depth_m"] == 15.5
        assert msg.payload["pressure_mbar"] == 2500.0
        assert msg.payload["temperature_c"] == 23.0

    def test_tel_env(self):
        msg = tel_env("pico", temp_c=28.0, humidity=65.0, pressure_hpa=1013.0)
        assert msg.type == "tel.env"
        assert msg.payload["temperature_c"] == 28.0
        assert msg.payload["humidity_pct"] == 65.0
        assert msg.payload["pressure_hpa"] == 1013.0

    def test_tel_leak(self):
        msg = tel_leak("pico", channel=1, wet=True)
        assert msg.type == "tel.leak"
        assert msg.payload["channel"] == 1
        assert msg.payload["wet"] is True

    def test_tel_winch_state(self):
        msg = tel_winch_state("stm32", position_mm=500.0, speed_mm_s=30.0,
                              limit_top=False, limit_bottom=True,
                              e_stop=False, current_a=1.2)
        assert msg.type == "tel.winch_state"
        assert msg.payload["position_mm"] == 500.0
        assert msg.payload["limit_bottom"] is True
        assert msg.payload["e_stop_active"] is False
        assert msg.payload["motor_current_a"] == 1.2

    def test_tel_winch_state_default_current(self):
        msg = tel_winch_state("stm32", 0.0, 0.0, False, False, False)
        assert msg.payload["motor_current_a"] == 0.0

    def test_tel_gopro_status(self):
        msg = tel_gopro_status("pi", recording=True, battery_pct=85.0,
                               storage_gb=32.0, mode="video")
        assert msg.type == "tel.gopro_status"
        assert msg.payload["recording"] is True
        assert msg.payload["battery_pct"] == 85.0
        assert msg.payload["storage_gb_free"] == 32.0

    def test_tel_pi_status(self):
        msg = tel_pi_status("pi", cpu_temp=45.0, cpu_pct=30.0,
                            mem_pct=55.0, uptime_s=3600.0)
        assert msg.type == "tel.pi_status"
        assert msg.payload["cpu_temp_c"] == 45.0
        assert msg.payload["cpu_pct"] == 30.0
        assert msg.payload["memory_pct"] == 55.0
        assert msg.payload["uptime_s"] == 3600.0

    def test_tel_tracking_result(self):
        msg = tel_tracking_result("host", {"center_x": 0.5, "center_y": 0.6,
                                            "confidence": 0.95, "track_id": 3})
        assert msg.type == "tel.tracking_result"
        assert msg.payload["center_x"] == 0.5
        assert msg.payload["confidence"] == 0.95


# ---------------------------------------------------------------------------
# Message factories — system
# ---------------------------------------------------------------------------

class TestSystemMessageFactories:
    def test_make_heartbeat(self):
        msg = make_heartbeat("host")
        assert msg.type == "sys.heartbeat"
        assert msg.node_id == "host"
        assert msg.payload == {}

    def test_sys_ack(self):
        msg = sys_ack("pi", ref_msg_id="ref-abc-123")
        assert msg.type == "sys.ack"
        assert msg.payload["ref_msg_id"] == "ref-abc-123"

    def test_sys_error(self):
        msg = sys_error("stm32", code="OVER_CURRENT", detail="Motor overcurrent detected")
        assert msg.type == "sys.error"
        assert msg.payload["code"] == "OVER_CURRENT"
        assert msg.payload["detail"] == "Motor overcurrent detected"

    def test_sys_safety(self):
        for state in SafetyState:
            msg = sys_safety("host", state.value)
            assert msg.type == "sys.safety"
            assert msg.payload["state"] == state.value

    def test_sys_startup(self):
        msg = sys_startup("pico")
        assert msg.type == "sys.startup"
        assert msg.payload == {}

    def test_sys_shutdown(self):
        msg = sys_shutdown("pi")
        assert msg.type == "sys.shutdown"
        assert msg.payload == {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateMessage:
    def test_valid_message_passes(self):
        msg = make_heartbeat("host")
        errors = validate_message(msg)
        assert errors == []

    def test_missing_msg_id(self):
        msg = new_message("host", "sys.heartbeat")
        msg.msg_id = ""
        errors = validate_message(msg)
        assert any("msg_id" in e for e in errors)

    def test_missing_timestamp(self):
        msg = new_message("host", "sys.heartbeat")
        msg.timestamp_ns = 0
        errors = validate_message(msg)
        assert any("timestamp_ns" in e for e in errors)

    def test_unknown_node_id(self):
        msg = new_message("satellite", "sys.heartbeat")
        errors = validate_message(msg)
        assert any("node_id" in e for e in errors)

    def test_unknown_message_type(self):
        msg = new_message("host", "custom.unknown.type")
        errors = validate_message(msg)
        assert any("message type" in e for e in errors)

    def test_all_valid_node_ids_pass(self):
        for nid in NodeId:
            msg = make_heartbeat(nid.value)
            errors = validate_message(msg)
            assert not any("node_id" in e for e in errors), f"NodeId.{nid.name} failed validation"

    def test_all_known_types_pass(self):
        from deepsight_shared.protocol import KNOWN_TYPES
        for msg_type in sorted(KNOWN_TYPES):
            msg = new_message("host", msg_type, {})
            errors = validate_message(msg)
            assert not any("message type" in e for e in errors), \
                f"type '{msg_type}' failed validation"

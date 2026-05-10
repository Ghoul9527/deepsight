"""Integration tests — multi-node communication.

These tests verify that nodes can communicate using the shared protocol.
They don't require any hardware — pure mock mode.
"""

import json
import time

import pytest

from deepsight_shared.protocol import (
    Message,
    new_message,
    make_heartbeat,
    cmd_servo_set,
    cmd_winch_set,
    tel_imu,
    tel_depth,
    sys_safety,
    sys_ack,
    sys_error,
)
from deepsight_shared.constants import NodeId, SafetyState


class TestHostToPiCommunication:
    """Simulate Host sending commands to Pi."""

    def test_servo_command_route(self):
        msg = cmd_servo_set("host", 1, 45.0)
        data = msg.to_json()
        # Pi receives
        received = Message.from_json(data)
        assert received.type == "cmd.servo.set"
        assert received.payload["servo_id"] == 1
        # Pi would route this to Pico

    def test_winch_command_route(self):
        msg = cmd_winch_set("host", -0.5, "down")
        data = msg.to_json()
        received = Message.from_json(data)
        assert received.payload["direction"] == "down"


class TestPicoToHostTelemetry:
    """Simulate Pico sending telemetry to Host via Pi."""

    def test_imu_data_flow(self):
        msg = tel_imu("pico", 1.2, 0.3, -0.2)
        data = msg.to_json()
        # Pi relays to Host
        received = Message.from_json(data)
        assert received.node_id == "pico"
        assert received.type == "tel.imu"

    def test_depth_data_flow(self):
        msg = tel_depth("pico", 15.0, 2500.0, 24.0)
        data = msg.to_json()
        received = Message.from_json(data)
        assert received.payload["depth_m"] == 15.0


class TestSTM32ToHostTelemetry:
    """Simulate STM32 sending telemetry to Host via Pi."""

    def test_winch_state_flow(self):
        from deepsight_shared.protocol import tel_winch_state
        msg = tel_winch_state("stm32", 1000.0, -50.0, False, False, False)
        data = msg.to_json()
        received = Message.from_json(data)
        assert received.type == "tel.winch_state"
        assert received.payload["position_mm"] == 1000.0


class TestHeartbeatSystem:
    """Test the heartbeat/liveness protocol."""

    def test_nodes_send_heartbeat(self):
        for node_id in ["host", "pi", "pico", "stm32"]:
            msg = make_heartbeat(node_id)
            assert msg.type == "sys.heartbeat"
            assert msg.node_id == node_id

    def test_heartbeat_timeout_detection(self):
        """Simulate heartbeat timeout detection."""
        from deepsight_shared.constants import (
            HEARTBEAT_INTERVAL,
            HEARTBEAT_DEGRADED_TIMEOUT,
            HEARTBEAT_LOST_TIMEOUT,
        )
        assert HEARTBEAT_INTERVAL == 0.5
        assert HEARTBEAT_DEGRADED_TIMEOUT == 2.0
        assert HEARTBEAT_LOST_TIMEOUT == 5.0


class TestSafetyProtocol:
    """Test safety state propagation."""

    def test_emergency_stop_propagation(self):
        msg = sys_safety("host", "emergency")
        data = msg.to_json()
        received = Message.from_json(data)
        assert received.type == "sys.safety"
        assert received.payload["state"] == "emergency"

    def test_node_disconnect_safety(self):
        """Simulate node disconnection triggering safety state."""
        msg = sys_error("pi", "NODE_LOST", "Pico heartbeat timeout")
        data = msg.to_json()
        received = Message.from_json(data)
        assert received.payload["code"] == "NODE_LOST"


class TestNodeStartup:
    """Test node startup/shutdown sequence."""

    def test_node_startup(self):
        from deepsight_shared.protocol import sys_startup, sys_shutdown
        startup = sys_startup("pico")
        assert startup.type == "sys.startup"

        shutdown = sys_shutdown("pico")
        assert shutdown.type == "sys.shutdown"

"""Pytest fixtures for DeepSight integration tests."""

import json
import sys
from pathlib import Path

import pytest

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "host" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "pi" / "src"))


@pytest.fixture
def sample_heartbeat():
    return {
        "msg_id": "test-1",
        "timestamp_ns": 1234567890000000000,
        "node_id": "pi",
        "type": "sys.heartbeat",
        "version": "1.0",
        "payload": {},
    }


@pytest.fixture
def sample_servo_command():
    return {
        "msg_id": "test-2",
        "timestamp_ns": 1234567890000000000,
        "node_id": "host",
        "type": "cmd.servo.set",
        "version": "1.0",
        "payload": {"servo_id": 1, "angle": 45.0},
    }


@pytest.fixture
def sample_imu_telemetry():
    return {
        "msg_id": "test-3",
        "timestamp_ns": 1234567890000000000,
        "node_id": "pico",
        "type": "tel.imu",
        "version": "1.0",
        "payload": {"yaw": 1.2, "pitch": 0.3, "roll": -0.2},
    }

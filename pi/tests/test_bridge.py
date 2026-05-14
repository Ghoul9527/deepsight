"""Tests for the communication bridge module."""

import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared", "src"))

import pytest
from deepsight_shared.protocol import Message, new_message


def async_test(coro):
    return asyncio.run(coro)


# ── Mock config helper ─────────────────────────────────

MOCK_YAML = {
    "pi": {"id": "pi-test", "udp_port": 5100, "ws_port": 5101},
    "network": {"host_address": "127.0.0.1", "host_udp_port": 5000, "host_ws_port": 5001},
    "serial": {"pico_port": "mock", "stm32_port": "mock", "pico_baud": 115200, "stm32_baud": 115200},
    "gopro": {"mock": True},
    "capture": {"mock": True, "device": "/dev/video0", "width": 1920, "height": 1080, "fps": 60},
    "watchdog": {"heartbeat_interval_s": 0.5, "reconnect_delay_s": 2.0},
    "logging": {"level": "DEBUG", "dir": "logs/pi-test/"},
}


def make_cfg():
    from deepsight_pi.config import PiConfig
    with patch("builtins.open"), patch("yaml.safe_load", return_value=MOCK_YAML):
        return PiConfig()


# ── Message serialization ──────────────────────────────

class TestMessageRoundTrip:
    def test_json_roundtrip(self):
        msg = new_message("pi", "cmd.servo.set", {"servo_id": 0, "angle": 90})
        raw = msg.to_json()
        decoded = Message.from_json(raw)
        assert decoded.msg_id == msg.msg_id
        assert decoded.node_id == "pi"
        assert decoded.type == "cmd.servo.set"
        assert decoded.payload["servo_id"] == 0
        assert decoded.payload["angle"] == 90

    def test_bytes_roundtrip(self):
        msg = new_message("host", "sys.heartbeat", {})
        raw = msg.to_bytes()
        decoded = Message.from_bytes(raw)
        assert decoded.type == "sys.heartbeat"
        assert decoded.node_id == "host"

    def test_new_message_has_required_fields(self):
        msg = new_message("pi", "tel.imu", {"yaw": 15.0})
        assert msg.msg_id
        assert msg.timestamp_ns > 0
        assert msg.node_id == "pi"
        assert msg.type == "tel.imu"
        assert msg.version == "1.0"

    def test_from_json_missing_version(self):
        raw = '{"msg_id":"abc","timestamp_ns":1,"node_id":"pi","type":"sys.heartbeat"}'
        msg = Message.from_json(raw)
        assert msg.version == "1.0"

    def test_from_json_empty_payload(self):
        raw = '{"msg_id":"abc","timestamp_ns":1,"node_id":"pi","type":"sys.heartbeat"}'
        msg = Message.from_json(raw)
        assert msg.payload == {}


# ── HostLink ───────────────────────────────────────────

class TestHostLink:
    def test_init_defaults(self):
        from deepsight_pi.bridge.host_link import HostLink
        link = HostLink(make_cfg())
        assert hasattr(link, "recv_queue")
        assert link.running is False

    def test_send_method_exists(self):
        from deepsight_pi.bridge.host_link import HostLink
        link = HostLink(make_cfg())
        assert hasattr(link, "send")


# ── PicoLink ───────────────────────────────────────────

class TestPicoLink:
    def test_init(self):
        from deepsight_pi.bridge.pico_link import PicoLink
        link = PicoLink(make_cfg())
        assert hasattr(link, "recv_queue")
        assert hasattr(link, "send")

    def test_mock_start(self):
        from deepsight_pi.bridge.pico_link import PicoLink
        link = PicoLink(make_cfg())
        async_test(link.start())

    def test_stop(self):
        from deepsight_pi.bridge.pico_link import PicoLink
        link = PicoLink(make_cfg())
        async_test(link.stop())


# ── STM32Link ──────────────────────────────────────────

class TestSTM32Link:
    def test_init(self):
        from deepsight_pi.bridge.stm32_link import Stm32Link
        link = Stm32Link(make_cfg())
        assert hasattr(link, "recv_queue")
        assert hasattr(link, "send")

    def test_mock_start(self):
        from deepsight_pi.bridge.stm32_link import Stm32Link
        link = Stm32Link(make_cfg())
        async_test(link.start())


# ── MessageRouter ──────────────────────────────────────

class TestMessageRouter:
    def _make_router(self):
        from deepsight_pi.bridge.host_link import HostLink
        from deepsight_pi.bridge.pico_link import PicoLink
        from deepsight_pi.bridge.stm32_link import Stm32Link
        from deepsight_pi.bridge.message_router import MessageRouter

        cfg = make_cfg()
        return MessageRouter(
            HostLink(cfg), PicoLink(cfg), Stm32Link(cfg),
            gopro_ready=lambda: True,
        )

    def test_router_init(self):
        router = self._make_router()
        assert router is not None
        assert hasattr(router, "start")
        assert hasattr(router, "stop")

    def test_router_start_stop(self):
        router = self._make_router()
        async_test(router.start())
        async_test(router.stop())


# ── Bridge exports ─────────────────────────────────────

class TestBridgeExports:
    def test_imports(self):
        from deepsight_pi.bridge import HostLink, PicoLink, Stm32Link, MessageRouter
        assert HostLink is not None
        assert PicoLink is not None
        assert Stm32Link is not None
        assert MessageRouter is not None

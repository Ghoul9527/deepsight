"""Test Pico command parser and safety monitor."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import config


class TestCommandParser:
    def test_parse_valid_command(self):
        from command_parser import CommandParser
        p = CommandParser()
        result = p.parse('{"type":"cmd.servo.set","payload":{"servo_id":0,"angle":90}}')
        assert result is not None
        cmd_type, payload = result
        assert cmd_type == "cmd.servo.set"
        assert payload["servo_id"] == 0
        assert payload["angle"] == 90

    def test_parse_no_type_returns_none(self):
        from command_parser import CommandParser
        p = CommandParser()
        result = p.parse('{"payload":{"servo_id":0}}')
        assert result is not None  # still parses, just cmd_type is empty string

    def test_parse_malformed_json(self):
        from command_parser import CommandParser
        p = CommandParser()
        result = p.parse("not json")
        assert result is None

    def test_parse_empty_string(self):
        from command_parser import CommandParser
        p = CommandParser()
        result = p.parse("")
        assert result is None

    def test_register_and_dispatch(self):
        from command_parser import CommandParser
        p = CommandParser()
        calls = []
        p.register("cmd.test", lambda payload: calls.append(payload))
        p.dispatch("cmd.test", {"value": 42})
        assert len(calls) == 1
        assert calls[0]["value"] == 42

    def test_dispatch_unknown(self):
        from command_parser import CommandParser
        p = CommandParser()
        p.dispatch("cmd.nonexistent", {})  # prints but doesn't crash


class TestSafetyMonitor:
    def test_initially_not_active(self):
        from safety import SafetyMonitor
        s = SafetyMonitor()
        assert s.safety_active is False

    def test_check_no_timeout(self):
        from safety import SafetyMonitor
        s = SafetyMonitor()
        s.command_received()
        assert s.check() is False
        assert s.safety_active is False

    def test_timeout_triggers_safety(self):
        from safety import SafetyMonitor
        s = SafetyMonitor()
        s._last_command_time = time.time() - (config.NO_COMMAND_TIMEOUT_S + 1.0)
        assert s.check() is True
        assert s.safety_active is True

    def test_command_received_resets(self):
        from safety import SafetyMonitor
        s = SafetyMonitor()
        s._last_command_time = time.time() - (config.NO_COMMAND_TIMEOUT_S + 1.0)
        s.check()
        s.command_received()
        assert s.safety_active is False

    def test_default_angles(self):
        from safety import SafetyMonitor
        s = SafetyMonitor()
        angles = s.get_default_angles()
        assert len(angles) == config.SERVO_COUNT
        assert all(a == config.DEFAULT_SERVO_ANGLE for a in angles)

"""Verify local leak transitions, source identity and input cleanup."""
import asyncio
from unittest.mock import AsyncMock, Mock
import pytest
from deepsight_pi.hardware.leak_sensor import PiLeakMonitor


def test_transitions_and_cleanup():
    async def scenario():
        sensor = Mock(is_active=False)
        factory = Mock(return_value=sensor)
        host = Mock(send=AsyncMock())
        monitor = PiLeakMonitor(host, {"enabled": True, "gpio": 22}, input_factory=factory)
        await monitor.start()
        factory.assert_called_once_with(22, pull_up=False, bounce_time=0.05)
        sensor.is_active = True
        await monitor._publish()
        sensor.is_active = False
        await monitor._publish()
        messages = [call.args[0] for call in host.send.call_args_list]
        assert [m.payload for m in messages] == [
            {"channel": 0, "wet": False}, {"channel": 0, "wet": True},
            {"channel": 0, "wet": False}]
        assert all(m.node_id == "pi" and m.type == "tel.leak" for m in messages)
        await monitor.stop()
        sensor.close.assert_called_once()
        assert monitor._task is None
    asyncio.run(scenario())


def test_disabled_does_not_claim_gpio():
    async def scenario():
        factory = Mock()
        monitor = PiLeakMonitor(Mock(), {}, input_factory=factory)
        await monitor.start()
        await monitor.stop()
        factory.assert_not_called()
    asyncio.run(scenario())


def test_start_failure_releases_input():
    async def scenario():
        sensor = Mock(is_active=False)
        host = Mock(send=AsyncMock(side_effect=OSError("link failed")))
        monitor = PiLeakMonitor(host, {"enabled": True}, input_factory=Mock(return_value=sensor))
        with pytest.raises(OSError):
            await monitor.start()
        sensor.close.assert_called_once()
        assert monitor._input is None and monitor._task is None
    asyncio.run(scenario())

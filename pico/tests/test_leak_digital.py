"""Leak alarm module polarity and GPIO isolation tests."""
import sys
import types
import pytest
import config
from lib.leak_sensor import DigitalLeakSensor, create_leak_sensor


@pytest.fixture
def pins(monkeypatch):
    class Pin:
        IN, PULL_DOWN, PULL_UP = 0, 1, 2
        levels = {2: 0}
        configured = []
        def __init__(self, number, mode, pull):
            self.number = number
            self.configured.append((number, mode, pull))
        def value(self):
            return self.levels[self.number]
    monkeypatch.setitem(sys.modules, 'machine', types.SimpleNamespace(Pin=Pin))
    monkeypatch.setattr(config, 'LEAK_CHANNELS', 1)
    monkeypatch.setattr(config, 'LEAK_DIGITAL_PINS', [2])
    monkeypatch.setattr(config, 'LEAK_ACTIVE_HIGH', True)
    return Pin


def test_dry_wet_dry_transitions(pins):
    sensor = DigitalLeakSensor()
    assert sensor.init()
    assert pins.configured == [(2, pins.IN, pins.PULL_DOWN)]
    assert sensor.read_all() == [False]
    pins.levels[2] = 1
    assert sensor.is_wet(0)
    pins.levels[2] = 0
    assert sensor.read_all() == [False]


def test_rejects_missing_input_pin(pins, monkeypatch):
    monkeypatch.setattr(config, 'LEAK_CHANNELS', 2)
    sensor = DigitalLeakSensor()
    assert not sensor.init()
    with pytest.raises(OSError):
        sensor.read_all()


def test_factory_uses_real_digital_module(pins, monkeypatch):
    monkeypatch.setattr(config, 'MOCK_ENABLED', False)
    assert isinstance(create_leak_sensor(), DigitalLeakSensor)

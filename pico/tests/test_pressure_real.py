"""Protocol and calibration regressions for the real MS5837-30BA driver."""
import sys
import types

import pytest
import config
from lib.pressure import MS5837Driver

# Datasheet conversion example, with CRC-4=2 in the factory word.
PROM = [0x2000, 34982, 36352, 20328, 22354, 26646, 26146]


class SensorBus:
    def __init__(self):
        self.prom = PROM[:]
        self.commands = []
        self.pending = None
        self.conversion = None
        self.fail_read = False

    def writeto(self, address, data, stop=True):
        assert address == 0x76
        command = data[0]
        self.commands.append(command)
        if command == 0x1E:
            assert stop
        elif command in (0x4A, 0x5A):
            self.conversion = command
        else:
            assert not stop, 'register reads must use repeated START'
            assert command == 0 or command in range(0xA0, 0xAD, 2)
            self.pending = command
        return 1

    def readfrom(self, address, size):
        if self.fail_read:
            raise OSError('injected bus fault')
        if self.pending >= 0xA0:
            return self.prom[(self.pending - 0xA0) // 2].to_bytes(2, 'big')
        value = 4958179 if self.conversion == 0x4A else 6815414
        return value.to_bytes(3, 'big')


@pytest.fixture
def device(monkeypatch):
    bus = SensorBus()
    events = []
    class Pin:
        PULL_UP = 1
        def __init__(self, number):
            self.number = number
        def init(self, **kwargs):
            assert kwargs == {'pull': self.PULL_UP}
            events.append(('pull', self.number))
    def make_i2c(index, **kwargs):
        assert index == 1
        assert kwargs['sda'].number == 18
        assert kwargs['scl'].number == 19
        assert kwargs['freq'] == 10000
        events.append(('bus', index))
        bus.setup_events = events
        return bus
    monkeypatch.setitem(sys.modules, 'machine', types.SimpleNamespace(I2C=make_i2c, Pin=Pin))
    monkeypatch.setattr(config, 'PRESSURE_I2C_BUS', 1)
    monkeypatch.setattr(config, 'PRESSURE_I2C_SDA_PIN', 18)
    monkeypatch.setattr(config, 'PRESSURE_I2C_SCL_PIN', 19)
    monkeypatch.setattr(config, 'PRESSURE_I2C_FREQ', 10000)
    monkeypatch.setattr(config, 'PRESSURE_I2C_INTERNAL_PULLUP', True)
    monkeypatch.setattr('lib.pressure.time.sleep', lambda _: None)
    return MS5837Driver(), bus


def test_reads_factory_word_and_all_six_coefficients(device):
    sensor, bus = device
    assert sensor.init()
    assert bus.commands == [0x1E, 0xA0, 0xA2, 0xA4, 0xA6, 0xA8, 0xAA, 0xAC]
    assert sensor._cal == PROM + [0]
    assert MS5837Driver._crc4(PROM) == 2
    assert PROM[0] == 0x2000


def test_crc_rejects_corrupt_coefficients(device):
    sensor, bus = device
    bus.prom[3] ^= 1
    assert not sensor.init()
    assert not sensor.initialized
    assert 'CRC mismatch' in sensor.last_error


def test_empty_prom_is_not_valid_calibration(device):
    sensor, bus = device
    bus.prom = [0] * 7
    assert not sensor.init()
    assert 'invalid calibration' in sensor.last_error


def test_read_failure_does_not_return_fake_atmospheric_pressure(device):
    sensor, bus = device
    assert sensor.init()
    bus.fail_read = True
    with pytest.raises(OSError, match='injected bus fault'):
        sensor.read()


def test_reinitialization_clears_previous_success(device):
    sensor, bus = device
    assert sensor.init()
    bus.fail_read = True
    assert not sensor.init()
    assert not sensor.initialized
    assert 'PROM W0' in sensor.last_error


def test_datasheet_pressure_temperature_example(device):
    sensor, _ = device
    assert sensor.init()
    depth, pressure, temperature = sensor.read()
    assert pressure == pytest.approx(3999.8, abs=1)
    assert temperature == pytest.approx(19.81, abs=0.02)
    assert depth > 0


def test_internal_pullups_enabled_after_hardware_bus_init(device):
    sensor, bus = device
    assert sensor.init()
    assert bus.setup_events == [('bus', 1), ('pull', 19), ('pull', 18)]


def test_separate_buses_and_disabled_environment_do_not_remap_imu(monkeypatch):
    from lib.imu import MPU6050Driver
    from lib.bme280 import BME280Driver
    calls = []
    class Pin:
        def __init__(self, number):
            self.number = number
    class Bus:
        def writeto_mem(self, *args):
            pass
    def make_i2c(index, **kwargs):
        calls.append((index, kwargs['sda'].number, kwargs['scl'].number))
        return Bus()
    monkeypatch.setitem(sys.modules, 'machine', types.SimpleNamespace(I2C=make_i2c, Pin=Pin))
    monkeypatch.setattr('lib.imu.time.ticks_us', lambda: 0, raising=False)
    assert config.IMU_I2C_BUS != config.PRESSURE_I2C_BUS
    assert MPU6050Driver().init()
    assert not BME280Driver().init()
    assert calls == [(0, 20, 21)]

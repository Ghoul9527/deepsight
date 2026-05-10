"""Leak sensor driver — ADC-based multi-channel + mock implementation."""

import random

import config
from lib.driver_base import LeakSensorDriver


# ── Mock ─────────────────────────────────────────────────

class MockLeakSensor(LeakSensorDriver):
    def __init__(self):
        super().__init__("leak_mock")
        self._wet = [False] * config.LEAK_CHANNELS

    def read_all(self) -> list:
        return list(self._wet)

    def is_wet(self, channel: int) -> bool:
        return self._wet[channel]


# ── Real ADC leak sensor ─────────────────────────────────

class ADCLeakSensor(LeakSensorDriver):
    """Multi-channel leak detector using ADC voltage thresholds.

    Each channel has a pair of exposed contacts. When water bridges
    the contacts, the voltage drops below the threshold → wet = True.

    Works on MicroPython (machine.ADC) and CPython (try adafruit).
    """

    def __init__(self):
        super().__init__("leak_adc")
        self._pins = []
        self._adc = []
        self._threshold = config.LEAK_WET_THRESHOLD
        self._channels = config.LEAK_CHANNELS
        self._states = [False] * self._channels

    def init(self) -> bool:
        try:
            from machine import ADC, Pin
            self._adc = []
            for pin_num in config.LEAK_ADC_PINS[:self._channels]:
                adc = ADC(Pin(pin_num))
                self._adc.append(adc)
        except ImportError:
            # CPython — no real ADC, return False
            try:
                import board
                import analogio
                for pin_name in config.LEAK_ADC_PINS[:self._channels]:
                    p = getattr(board, f'A{pin_name}', None)
                    if p is None:
                        return False
                    self._adc.append(analogio.AnalogIn(p))
            except (ImportError, NotImplementedError):
                return False
        except Exception:
            return False

        if not self._adc:
            return False
        super().init()
        return True

    def read_all(self) -> list:
        for i, adc in enumerate(self._adc):
            self._states[i] = self._read_channel(i)
        return list(self._states)

    def is_wet(self, channel: int) -> bool:
        if 0 <= channel < len(self._adc):
            self._states[channel] = self._read_channel(channel)
        return self._states[channel]

    def _read_channel(self, channel: int) -> bool:
        try:
            raw = self._adc[channel].read_u16()
            voltage = (raw / 65535.0) * 3.3
            return voltage < self._threshold
        except Exception:
            return self._states[channel]


# ── Factory ──────────────────────────────────────────────

def create_leak_sensor() -> LeakSensorDriver:
    if config.MOCK_ENABLED:
        return MockLeakSensor()
    return ADCLeakSensor()

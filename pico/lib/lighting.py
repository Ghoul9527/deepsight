"""Lighting PWM driver + mock implementation."""

import config
from lib.driver_base import LightingDriver


# ── Mock ─────────────────────────────────────────────────

class MockLightingDriver(LightingDriver):
    def __init__(self):
        super().__init__("lighting_mock")
        self._brightness = [0.0] * config.LIGHTING_CHANNELS

    def set_brightness(self, channel: int, brightness: float):
        brightness = max(0.0, min(1.0, brightness))
        self._brightness[channel] = brightness

    def get_brightness(self, channel: int) -> float:
        return self._brightness[channel]

    def set_all(self, brightness: float):
        brightness = max(0.0, min(1.0, brightness))
        for i in range(config.LIGHTING_CHANNELS):
            self._brightness[i] = brightness


# ── Real PWM lighting ────────────────────────────────────

class PWMLightingDriver(LightingDriver):
    """Multi-channel PWM LED lighting controller.

    Uses hardware PWM pins on the Pico. Each channel controls
    a MOSFET gate or LED driver enable pin.

    Works on MicroPython (machine.PWM) and CPython (try adafruit).
    """

    def __init__(self):
        super().__init__("lighting_pwm")
        self._channels = config.LIGHTING_CHANNELS
        self._pwm_pins = config.LIGHTING_PWM_PINS[:self._channels]
        self._pwms = []
        self._brightness = [0.0] * self._channels

    def init(self) -> bool:
        try:
            from machine import PWM, Pin
            self._pwms = []
            for pin_num in self._pwm_pins:
                pwm = PWM(Pin(pin_num))
                pwm.freq(config.LIGHTING_PWM_FREQ)
                pwm.duty_u16(0)
                self._pwms.append(pwm)
        except ImportError:
            try:
                import board
                import pwmio
                for pin_name in self._pwm_pins:
                    p = getattr(board, f'GP{pin_name}', None)
                    if p is None:
                        return False
                    pwm = pwmio.PWMOut(p, frequency=config.LIGHTING_PWM_FREQ)
                    pwm.duty_cycle = 0
                    self._pwms.append(pwm)
            except (ImportError, NotImplementedError):
                return False
        except Exception:
            return False

        if not self._pwms:
            return False
        super().init()
        return True

    def deinit(self):
        for pwm in self._pwms:
            try:
                pwm.deinit()
            except (AttributeError, Exception):
                pass
        super().deinit()

    def set_brightness(self, channel: int, brightness: float):
        brightness = max(0.0, min(1.0, brightness))
        self._brightness[channel] = brightness
        if channel < len(self._pwms):
            duty = int(brightness * 65535)
            try:
                self._pwms[channel].duty_u16(duty)
            except AttributeError:
                self._pwms[channel].duty_cycle = duty

    def get_brightness(self, channel: int) -> float:
        return self._brightness[channel]

    def set_all(self, brightness: float):
        brightness = max(0.0, min(1.0, brightness))
        for i in range(self._channels):
            self.set_brightness(i, brightness)


# ── Factory ──────────────────────────────────────────────

def create_lighting_driver() -> LightingDriver:
    if config.MOCK_ENABLED:
        return MockLightingDriver()
    return PWMLightingDriver()

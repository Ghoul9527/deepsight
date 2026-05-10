"""EMA (Exponential Moving Average) smoothing for tracking positions."""

from __future__ import annotations


class EMASmoother:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._value: tuple[float, float] | None = None

    def update(self, value: tuple[float, float]) -> tuple[float, float]:
        if self._value is None:
            self._value = value
            return value

        x = self.alpha * value[0] + (1 - self.alpha) * self._value[0]
        y = self.alpha * value[1] + (1 - self.alpha) * self._value[1]
        self._value = (x, y)
        return self._value

    @property
    def current(self) -> tuple[float, float] | None:
        return self._value

    def reset(self):
        self._value = None

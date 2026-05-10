"""Kalman filter for position prediction and smoothing."""

from __future__ import annotations

import numpy as np


class KalmanPredictor:
    def __init__(self, dt: float = 1.0 / 30.0, process_noise: float = 0.01,
                 measurement_noise: float = 0.1):
        self.dt = dt
        self._kf = self._init_filter(dt, process_noise, measurement_noise)
        self._initialized = False
        self._predicted: tuple[float, float] = (0.5, 0.5)
        self._uncertainty: float = 1.0
        self._steps_since_update: int = 0

    @staticmethod
    def _init_filter(dt: float, q: float, r: float):
        return {"dt": dt, "q": q, "r": r, "x": np.zeros(4), "P": np.eye(4) * 1000}

    def predict(self) -> tuple[float, float]:
        dt = self.dt
        x = self._kf["x"]
        P = self._kf["P"]
        q = self._kf["q"]

        # State transition: x_new = x + vx*dt, y_new = y + vy*dt
        F = np.array([[1, 0, dt, 0],
                       [0, 1, 0, dt],
                       [0, 0, 1, 0],
                       [0, 0, 0, 1]])
        Q = np.eye(4) * q

        x = F @ x
        P = F @ P @ F.T + Q

        self._kf["x"] = x
        self._kf["P"] = P
        self._steps_since_update += 1
        self._uncertainty = np.trace(P)
        self._predicted = (float(x[0]), float(x[1]))
        return self._predicted

    def update(self, measurement: tuple[float, float]):
        x = self._kf["x"]
        P = self._kf["P"]
        r = self._kf["r"]

        H = np.array([[1, 0, 0, 0],
                       [0, 1, 0, 0]])
        R = np.eye(2) * r
        z = np.array(measurement)

        y = z - H @ x[:4]
        S = H @ P[:4, :4] @ H.T + R
        K = P[:4, :4] @ H.T @ np.linalg.inv(S)

        x = x + K @ y
        P = P - K @ H @ P[:4, :4]

        self._kf["x"] = x
        self._kf["P"] = P
        self._initialized = True
        self._steps_since_update = 0
        self._uncertainty = np.trace(P)
        self._predicted = (float(x[0]), float(x[1]))

    def reset(self):
        self._kf["x"] = np.zeros(4)
        self._kf["P"] = np.eye(4) * 1000
        self._initialized = False
        self._uncertainty = 1.0
        self._steps_since_update = 0

    @property
    def predicted_position(self) -> tuple[float, float]:
        return self._predicted

    @property
    def uncertainty(self) -> float:
        return self._uncertainty

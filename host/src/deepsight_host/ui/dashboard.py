"""Compact telemetry status widget — key readouts in a dense grid."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel

from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.dashboard")


class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: dict[str, float] = {}
        self._labels: dict[str, QLabel] = {}
        self._key_labels: dict[str, QLabel] = {}
        self._i18n = I18n.instance()
        self._setup_ui()
        self._i18n.language_changed.connect(self._retranslate)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(2)

        grid = QGridLayout()
        grid.setSpacing(2)

        # Row 0: IMU data
        self._add_cell(grid, 0, 0, "dashboard.imu")
        self._add_metric(grid, 0, 1, "yaw", "°")
        self._add_metric(grid, 0, 2, "pitch", "°")
        self._add_metric(grid, 0, 3, "roll", "°")

        # Row 1: Depth + Pressure + Temp
        self._add_cell(grid, 1, 0, "dashboard.depth")
        self._add_metric(grid, 1, 1, "depth", "m")
        self._add_metric(grid, 1, 2, "pressure", "mbar")
        self._add_metric(grid, 1, 3, "water_temp", "°C")

        # Row 2: Tracking
        self._add_cell(grid, 2, 0, "dashboard.tracking_title")
        self._add_metric(grid, 2, 1, "confidence", "%")
        self._add_metric(grid, 2, 2, "target_x", "")
        self._add_metric(grid, 2, 3, "target_y", "")

        root.addLayout(grid)

    def _add_cell(self, grid: QGridLayout, row: int, col: int, i18n_key: str):
        label = QLabel(tr(i18n_key))
        label.setObjectName("heading")
        label.setStyleSheet("font-size: 10px;")
        grid.addWidget(label, row, col)
        self._key_labels[i18n_key] = label

    def _add_metric(self, grid: QGridLayout, row: int, col: int,
                    key: str, unit: str):
        label = QLabel("---")
        label.setObjectName("value")
        label.setStyleSheet("font-size: 12px;")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(label, row, col)
        self._labels[key] = label

    def _retranslate(self, _lang: str = ""):
        for i18n_key, label in self._key_labels.items():
            label.setText(tr(i18n_key))

    def update_value(self, key: str, value):
        self._values[key] = value
        if key in self._labels:
            if isinstance(value, float):
                if key in ("target_x", "target_y"):
                    text = f"{value:.4f}"
                elif key == "confidence":
                    text = f"{value * 100:.0f}"
                elif key in ("yaw", "pitch", "roll", "water_temp"):
                    text = f"{value:.1f}"
                elif key == "depth":
                    text = f"{value:.1f}"
                elif key == "pressure":
                    text = f"{value:.0f}"
                else:
                    text = f"{value:.2f}"
            else:
                text = str(value)
            self._labels[key].setText(text)

    def update_imu(self, yaw: float, pitch: float, roll: float):
        self.update_value("yaw", yaw)
        self.update_value("pitch", pitch)
        self.update_value("roll", roll)

    def update_depth(self, depth_m: float, pressure_mbar: float = 0.0,
                     temp_c: float = 0.0):
        self.update_value("depth", depth_m)
        self.update_value("pressure", pressure_mbar)
        self.update_value("water_temp", temp_c)

    def update_tracking(self, center_x: float, center_y: float,
                        confidence: float, track_id: int):
        self.update_value("target_x", center_x)
        self.update_value("target_y", center_y)
        self.update_value("confidence", confidence)

    def update_winch(self, position_mm: float, speed_mm_s: float,
                     limit_top: bool, limit_bottom: bool):
        self.update_value("winch_pos", position_mm)
        self.update_value("winch_speed", speed_mm_s)

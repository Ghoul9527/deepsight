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

        # Row 0: Gyro
        self._add_cell(grid, 0, 0, "dashboard.gyro")
        self._add_metric(grid, 0, 1, "yaw", "°")
        self._add_metric(grid, 0, 2, "pitch", "°")
        self._add_metric(grid, 0, 3, "roll", "°")

        # Row 1: Depth + Pressure + Temp
        self._add_cell(grid, 1, 0, "dashboard.depth")
        self._add_metric(grid, 1, 1, "depth", "m")
        self._add_metric(grid, 1, 2, "pressure", "mbar")
        self._add_metric(grid, 1, 3, "water_temp", "°C")

        # Row 2: Light
        self._add_cell(grid, 2, 0, "dashboard.light")
        self._add_metric(grid, 2, 1, "lux", "lx")

        # Row 3: E-Bay (electronics bay)
        self._add_cell(grid, 3, 0, "dashboard.ebay")
        self._add_metric(grid, 3, 1, "ebay_pressure", "mbar")
        self._add_metric(grid, 3, 2, "ebay_temp", "°C")
        self._add_metric(grid, 3, 3, "ebay_humidity", "%")

        # Row 4: Cam Bay
        self._add_cell(grid, 4, 0, "dashboard.cambay")
        self._add_metric(grid, 4, 1, "cambay_pressure", "mbar")
        self._add_metric(grid, 4, 2, "cambay_temp", "°C")
        self._add_metric(grid, 4, 3, "cambay_humidity", "%")

        # Row 5: Environment
        self._add_cell(grid, 5, 0, "dashboard.env")
        self._add_metric(grid, 5, 1, "env_temp", "°C")
        self._add_metric(grid, 5, 2, "humidity", "%")
        self._add_metric(grid, 5, 3, "env_pressure", "hPa")

        # Row 6: Tracking
        self._add_cell(grid, 6, 0, "dashboard.tracking_title")
        self._add_metric(grid, 6, 1, "confidence", "%")
        self._add_metric(grid, 6, 2, "target_x", "")
        self._add_metric(grid, 6, 3, "target_y", "")

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
                elif key in ("yaw", "pitch", "roll", "water_temp",
                             "ebay_temp", "cambay_temp", "env_temp"):
                    text = f"{value:.1f}"
                elif key in ("depth", "lux"):
                    text = f"{value:.1f}"
                elif key in ("pressure", "ebay_pressure", "cambay_pressure",
                             "env_pressure"):
                    text = f"{value:.0f}"
                elif key in ("humidity", "ebay_humidity", "cambay_humidity"):
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

    def update_light(self, lux: float):
        self.update_value("lux", lux)

    def update_ebay(self, pressure_mbar: float = 0.0, temp_c: float = 0.0,
                    humidity_pct: float = 0.0):
        self.update_value("ebay_pressure", pressure_mbar)
        self.update_value("ebay_temp", temp_c)
        self.update_value("ebay_humidity", humidity_pct)

    def update_cambay(self, pressure_mbar: float = 0.0, temp_c: float = 0.0,
                      humidity_pct: float = 0.0):
        self.update_value("cambay_pressure", pressure_mbar)
        self.update_value("cambay_temp", temp_c)
        self.update_value("cambay_humidity", humidity_pct)

    def update_tracking(self, center_x: float, center_y: float,
                        confidence: float, track_id: int):
        self.update_value("target_x", center_x)
        self.update_value("target_y", center_y)
        self.update_value("confidence", confidence)

    def update_winch(self, position_mm: float, speed_mm_s: float,
                     limit_top: bool, limit_bottom: bool):
        self.update_value("winch_pos", position_mm)
        self.update_value("winch_speed", speed_mm_s)

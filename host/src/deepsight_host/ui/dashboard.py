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
        self._units: dict[str, str] = {}
        self._metric_keys: dict[str, str] = {}  # key → i18n key for short label
        self._key_labels: dict[str, QLabel] = {}
        self._i18n = I18n.instance()
        self._setup_ui()
        self._i18n.language_changed.connect(self._retranslate)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(2)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        # Row 0: IMU (roll only)
        self._add_cell(grid, 0, 0, "dashboard.gyro")
        self._add_metric(grid, 0, 1, "roll", "°")

        # Row 1: Depth + Pressure + Temp
        self._add_cell(grid, 1, 0, "dashboard.depth")
        self._add_metric(grid, 1, 1, "depth", "m")
        self._add_metric(grid, 1, 2, "pressure", "mbar")
        self._add_metric(grid, 1, 3, "water_temp", "°C")

        # Brightness is computed from the preview image, not a lux sensor.
        self._add_cell(grid, 2, 0, "dashboard.preview_brightness")
        self._add_metric(grid, 2, 1, "frame_brightness", "%")

        self._add_cell(grid, 2, 2, "dashboard.light_pwm")
        self._add_metric(grid, 2, 3, "light_pwm", "%")

        self._add_cell(grid, 3, 0, "dashboard.leak")
        self._add_metric(grid, 3, 1, "leak_ch0", "")
        self._add_metric(grid, 3, 2, "leak_pi", "")

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
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(label, row, col)
        self._labels[key] = label
        self._units[key] = unit
        self._metric_keys[key] = f"metric.{key}"

    def _retranslate(self, _lang: str = ""):
        for i18n_key, label in self._key_labels.items():
            label.setText(tr(i18n_key))
        # Re-render all values with new language labels
        for key, value in self._values.items():
            self._render_value(key, value)

    def update_value(self, key: str, value):
        self._values[key] = value
        self._render_value(key, value)

    def _render_value(self, key: str, value):
        if key not in self._labels:
            return
        if value is None:
            self._labels[key].setText("---")
            return
        if key in ("leak_ch0", "leak_pi"):
            wet = value == "WET"
            source = "Pi" if key == "leak_pi" else "Pico"
            status = tr("leak.wet") if wet else tr("leak.dry")
            self._labels[key].setText(f"{source}: {status}")
            color = "#ff5555" if wet else "#55bb77"
            self._labels[key].setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
            return
        if isinstance(value, float):
            if key in ("target_x", "target_y"):
                num = f"{value:.4f}"
            elif key == "confidence":
                num = f"{value * 100:.0f}"
            elif key in ("yaw", "pitch", "roll", "water_temp",
                         "ebay_temp", "cambay_temp", "env_temp"):
                num = f"{value:.1f}"
            elif key in ("depth", "lux", "frame_brightness"):
                num = f"{value:.1f}"
            elif key in ("pressure", "ebay_pressure", "cambay_pressure",
                         "env_pressure"):
                num = f"{value:.0f}"
            elif key in ("humidity", "ebay_humidity", "cambay_humidity", "light_pwm"):
                num = f"{value:.0f}"
            else:
                num = f"{value:.2f}"
        else:
            num = str(value)

        label_key = self._metric_keys.get(key, "")
        metric_name = tr(label_key) if label_key else key
        unit = self._units.get(key, "")
        text = f"{num}{unit}" if key in ("frame_brightness", "light_pwm") else f"{metric_name}: {num}{unit}"
        self._labels[key].setText(text)

    def update_leak(self, node_id: str, channel: int, wet: bool):
        if channel != 0 or node_id not in ("pi", "pico"):
            return
        key = "leak_pi" if node_id == "pi" else "leak_ch0"
        self.update_value(key, "WET" if wet else "DRY")

    def update_imu(self, yaw: float, pitch: float, roll: float):
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

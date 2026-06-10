"""Mock motion control panel for dry testing."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)


class MockControlPanel(QGroupBox):
    state_changed = Signal(str, float, float)  # (state, speed_ms, depth_m)

    def __init__(self):
        super().__init__("Mock Motion")
        self._direction = 0  # -1=ascend, 0=stop, 1=descend
        self._speed = 1.0
        self._depth = 0.0

        self._setup_ui()

        self._timer = QTimer()
        self._timer.setInterval(50)  # 20 Hz
        self._timer.timeout.connect(self._tick)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Direction buttons
        btn_row = QHBoxLayout()
        self._btn_up = QPushButton("↑ Ascend")
        self._btn_stop = QPushButton("■ Stop")
        self._btn_down = QPushButton("↓ Descend")

        for btn in (self._btn_up, self._btn_stop, self._btn_down):
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { padding: 4px 8px; font-size: 11px; }"
                "QPushButton:checked { background-color: #3388cc; color: white; }"
            )
            btn_row.addWidget(btn)

        self._btn_stop.setChecked(True)
        self._btn_up.clicked.connect(lambda: self._set_direction(-1))
        self._btn_stop.clicked.connect(lambda: self._set_direction(0))
        self._btn_down.clicked.connect(lambda: self._set_direction(1))
        layout.addLayout(btn_row)

        # Speed slider
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(10, 200)  # 0.1 - 2.0 m/s * 100
        self._slider.setValue(100)
        self._slider.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self._slider)
        self._speed_label = QLabel("1.0 m/s")
        self._speed_label.setMinimumWidth(50)
        speed_row.addWidget(self._speed_label)
        layout.addLayout(speed_row)

        # Depth display
        self._depth_label = QLabel("Depth: 0.0 m")
        self._depth_label.setStyleSheet("font-size: 11px; color: #88ccff;")
        layout.addWidget(self._depth_label)

    def _set_direction(self, d: int):
        self._direction = d
        self._btn_up.setChecked(d == -1)
        self._btn_stop.setChecked(d == 0)
        self._btn_down.setChecked(d == 1)

    def _on_speed_changed(self, val: int):
        self._speed = val / 100.0
        self._speed_label.setText(f"{self._speed:.1f} m/s")

    def start(self):
        self._depth = 0.0
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        dt = 0.05  # 20 Hz
        if self._direction != 0:
            self._depth += self._direction * self._speed * dt
            self._depth = max(0.0, self._depth)

        if self._direction == 1:
            state = "descending"
        elif self._direction == -1:
            state = "ascending"
        else:
            state = "hovering"

        speed = self._direction * self._speed  # +descend, -ascend, 0=hover
        self._depth_label.setText(f"Depth: {self._depth:.1f} m")
        self.state_changed.emit(state, speed, self._depth)

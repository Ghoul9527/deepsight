"""Motion state display — shows robot direction, speed, depth with mock state machine."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QSizePolicy, QHBoxLayout

from deepsight_host.ui.i18n import I18n, tr

_STATE_COLORS = {
    "descending": "#44cc88",
    "hovering": "#ccaa44",
    "ascending": "#4488cc",
}
_STATE_ARROWS = {
    "descending": "↓",
    "hovering": "●",
    "ascending": "↑",
}


class MotionStateWidget(QWidget):
    """Displays robot motion direction, speed, and depth.

    Mock mode cycles: 60s descending -> 2s hovering -> 60s ascending -> 2s hovering.
    """

    state_changed = Signal(str)
    speed_changed = Signal(float)
    depth_changed = Signal(float)

    _T_DESCEND = 60.0
    _T_HOVER = 2.0
    _T_ASCEND = 60.0
    _MAX_DEPTH = 50.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "descending"
        self._speed_ms = 0.0
        self._depth_m = 0.0
        self._mock_enabled = True
        self._phase_elapsed = 0.0

        self._i18n = I18n.instance()
        self._i18n.language_changed.connect(self._on_lang_changed)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(50)  # 20 Hz

        self._setup_ui()
        self._retranslate()

    def _setup_ui(self):
        self.setMinimumSize(140, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._group = QGroupBox(tr("motion.title"))
        self._group.setStyleSheet(
            "QGroupBox { color: #8888cc; font-weight: bold; font-size: 10px; "
            "border: 1px solid #2a2a4a; border-radius: 4px; margin-top: 8px; padding-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(8, 6, 8, 6)
        group_layout.setSpacing(4)

        # State row: arrow + text
        state_row = QHBoxLayout()
        state_row.setSpacing(8)

        self._arrow_label = QLabel(_STATE_ARROWS["descending"])
        self._arrow_label.setStyleSheet(
            f"color: {_STATE_COLORS['descending']}; font-size: 24px; font-weight: bold;"
        )
        state_row.addWidget(self._arrow_label)

        self._state_label = QLabel()
        self._state_label.setStyleSheet(
            f"color: {_STATE_COLORS['descending']}; font-size: 16px; font-weight: bold;"
        )
        state_row.addWidget(self._state_label)
        state_row.addStretch()

        group_layout.addLayout(state_row)

        # Speed
        self._speed_label = QLabel()
        self._speed_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        group_layout.addWidget(self._speed_label)

        # Depth
        self._depth_label = QLabel()
        self._depth_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        group_layout.addWidget(self._depth_label)

        # Mock hint
        self._mock_label = QLabel(tr("motion.mock_hint"))
        self._mock_label.setStyleSheet("color: #666688; font-size: 9px; font-style: italic;")
        group_layout.addWidget(self._mock_label)

        root.addWidget(self._group)

    def _retranslate(self):
        self._update_display()

    def _on_lang_changed(self, _lang: str):
        self._group.setTitle(tr("motion.title"))
        self._retranslate()

    def _tick(self):
        if not self._mock_enabled:
            return

        dt = 0.05
        self._phase_elapsed += dt

        if self._state == "descending":
            if self._phase_elapsed >= self._T_DESCEND:
                self._phase_elapsed = 0.0
                self._state = "hovering"
                self._speed_ms = 0.0
            else:
                self._speed_ms = self._MAX_DEPTH / self._T_DESCEND
                self._depth_m = self._phase_elapsed * self._speed_ms
        elif self._state == "hovering":
            if self._phase_elapsed >= self._T_HOVER:
                self._phase_elapsed = 0.0
                # After bottom hover -> ascend; after top hover -> descend
                if self._depth_m > 1.0:
                    self._state = "ascending"
                else:
                    self._state = "descending"
            self._speed_ms = 0.0
        elif self._state == "ascending":
            if self._phase_elapsed >= self._T_ASCEND:
                self._phase_elapsed = 0.0
                self._depth_m = 0.0
                self._state = "hovering"
                self._speed_ms = 0.0
            else:
                self._speed_ms = -(self._MAX_DEPTH / self._T_ASCEND)
                self._depth_m = self._MAX_DEPTH * (1.0 - self._phase_elapsed / self._T_ASCEND)

        self._update_display()

    def _update_display(self):
        color = _STATE_COLORS.get(self._state, "#aaaaaa")
        arrow = _STATE_ARROWS.get(self._state, "?")

        self._arrow_label.setText(arrow)
        self._arrow_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")

        state_text = tr(f"motion.{self._state}")
        self._state_label.setText(state_text)
        self._state_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")

        speed_text = tr("motion.speed")
        self._speed_label.setText(f"{speed_text}: {abs(self._speed_ms):.2f} m/s")

        depth_text = tr("motion.depth")
        self._depth_label.setText(f"{depth_text}: {self._depth_m:.1f} m")

        self._mock_label.setVisible(self._mock_enabled)
        self._mock_label.setText(tr("motion.mock_hint"))

    def start_mock(self):
        self._mock_enabled = True
        self._phase_elapsed = 0.0
        self._state = "descending"
        self._depth_m = 0.0
        self._speed_ms = self._MAX_DEPTH / self._T_DESCEND
        self._timer.start()

    def stop_mock(self):
        self._timer.stop()
        self._mock_enabled = False

    def set_real_data(self, state: str, speed_ms: float, depth_m: float):
        self._mock_enabled = False
        self._timer.stop()
        self._state = state
        self._speed_ms = speed_ms
        self._depth_m = depth_m
        self._update_display()

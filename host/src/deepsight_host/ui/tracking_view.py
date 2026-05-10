"""Tracking view widget — mode switcher and live metrics."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
)

from deepsight_shared.constants import TrackingMode
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.tracking")


class TrackingViewWidget(QWidget):
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._i18n = I18n.instance()
        self._setup_ui()
        self._i18n.language_changed.connect(self._retranslate)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # Mode selector
        mode_group = QGroupBox(tr("tracking.mode"))
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(4)

        selector_layout = QHBoxLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItem(tr("tracking.fast"), TrackingMode.FAST.value)
        self._mode_combo.addItem(tr("tracking.precise"), TrackingMode.PRECISE.value)
        selector_layout.addWidget(self._mode_combo)
        mode_layout.addLayout(selector_layout)

        root.addWidget(mode_group)
        self._mode_group = mode_group

        # Status
        self._status_label = QLabel("---")
        self._status_label.setObjectName("heading")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        # Live metrics
        self._metrics_label = QLabel(
            "FPS: ---  Lat: --- ms\n"
            "ID: ---  Conf: ---\n"
            "Pan: ---°  Tilt: ---°"
        )
        self._metrics_label.setObjectName("value")
        self._metrics_label.setWordWrap(True)
        root.addWidget(self._metrics_label)

        # Reset button
        self._reset_btn = QPushButton(tr("tracking.reset"))
        root.addWidget(self._reset_btn)

        root.addStretch()

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

    def _retranslate(self, _lang: str = ""):
        self._mode_group.setTitle(tr("tracking.mode"))
        self._reset_btn.setText(tr("tracking.reset"))
        # Rebuild combo items
        self._mode_combo.blockSignals(True)
        current = self._mode_combo.currentData()
        self._mode_combo.clear()
        self._mode_combo.addItem(tr("tracking.fast"), TrackingMode.FAST.value)
        self._mode_combo.addItem(tr("tracking.precise"), TrackingMode.PRECISE.value)
        idx = self._mode_combo.findData(current)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.blockSignals(False)

    def _on_mode_changed(self, index: int):
        mode = self._mode_combo.itemData(index)
        if mode:
            self.mode_changed.emit(mode)

    def set_metrics(self, fps: float = 0.0, latency_ms: float = 0.0,
                    target_id: int = 0, confidence: float = 0.0,
                    pan: float = 0.0, tilt: float = 0.0):
        target_str = f"{target_id}" if target_id >= 0 else "LOST"
        self._metrics_label.setText(
            f"FPS: {fps:.1f}  Lat: {latency_ms:.1f} ms\n"
            f"ID: {target_str}  Conf: {confidence:.2f}\n"
            f"Pan: {pan:.1f}°  Tilt: {tilt:.1f}°"
        )

    def set_status(self, text: str):
        self._status_label.setText(text)

    @property
    def reset_button(self) -> QPushButton:
        return self._reset_btn

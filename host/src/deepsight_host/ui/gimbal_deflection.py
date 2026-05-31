"""Gimbal deflection display — target-style concentric circles with red dot."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QSizePolicy

from deepsight_host.ui.i18n import I18n, tr

_CIRCLE_COLOR = QColor("#2a2a5a")
_CROSSHAIR_COLOR = QColor("#445566")
_DOT_COLOR = QColor("#ff3344")
_BG_COLOR = QColor("#0d0d1a")
_TEXT_COLOR = QColor("#aaaaaa")


class GimbalDeflectionWidget(QWidget):
    """Target-style gimbal deflection display.

    Angles are deflection from center: 0° = centered, ±max_deflection = edge.
    Positive pan = gimbal yaws right, positive tilt = gimbal pitches down.
    """

    def __init__(self, max_deflection: float = 15.0, parent=None):
        super().__init__(parent)
        self._pan_deg = 0.0
        self._tilt_deg = 0.0
        self._max_deflection = max_deflection
        self._last_label_update = 0.0
        self._i18n = I18n.instance()
        self._i18n.language_changed.connect(self._on_lang_changed)
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumSize(160, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._group = QGroupBox(tr("gimbal.title"))
        self._group.setStyleSheet(
            "QGroupBox { color: #8888cc; font-weight: bold; font-size: 10px; "
            "border: 1px solid #2a2a4a; border-radius: 4px; margin-top: 8px; padding-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(6, 8, 6, 6)

        self._canvas = _GimbalCanvas(self)
        self._canvas.setMinimumSize(120, 120)
        group_layout.addWidget(self._canvas, 1)

        readout_row = QHBoxLayout()
        readout_row.setSpacing(12)

        self._pan_label = QLabel()
        self._pan_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        readout_row.addWidget(self._pan_label)

        self._tilt_label = QLabel()
        self._tilt_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        readout_row.addWidget(self._tilt_label)

        readout_row.addStretch()
        group_layout.addLayout(readout_row)
        root.addWidget(self._group)
        self._retranslate_readouts()

    def _retranslate_readouts(self):
        pan_txt = tr("gimbal.pan")
        tilt_txt = tr("gimbal.tilt")
        self._pan_label.setText(f"{pan_txt}: {self._pan_deg:+.1f}°")
        self._tilt_label.setText(f"{tilt_txt}: {self._tilt_deg:+.1f}°")

    def _on_lang_changed(self, _lang: str):
        self._group.setTitle(tr("gimbal.title"))
        self._retranslate_readouts()

    def set_angles(self, pan_deg: float, tilt_deg: float):
        """Set gimbal angles. Accepts servo angles (90=center) or deflection angles."""
        if abs(pan_deg - 90.0) < self._max_deflection * 3:
            pan_deg = pan_deg - 90.0
        if abs(tilt_deg - 90.0) < self._max_deflection * 3:
            tilt_deg = tilt_deg - 90.0
        self._pan_deg = pan_deg
        self._tilt_deg = tilt_deg
        self._maybe_update_labels()
        self._canvas.update()

    def set_pan(self, pan_deg: float):
        if abs(pan_deg - 90.0) < self._max_deflection * 3:
            pan_deg = pan_deg - 90.0
        self._pan_deg = pan_deg
        self._maybe_update_labels()
        self._canvas.update()

    def set_tilt(self, tilt_deg: float):
        if abs(tilt_deg - 90.0) < self._max_deflection * 3:
            tilt_deg = tilt_deg - 90.0
        self._tilt_deg = tilt_deg
        self._maybe_update_labels()
        self._canvas.update()

    def set_max_deflection(self, deg: float):
        self._max_deflection = deg
        self._canvas.update()

    def _maybe_update_labels(self):
        now = time.monotonic()
        if now - self._last_label_update > 0.1:
            self._last_label_update = now
            self._retranslate_readouts()


class _GimbalCanvas(QWidget):
    """Inner canvas that paints concentric circles and deflection dot."""

    def __init__(self, gimbal_widget: GimbalDeflectionWidget, parent=None):
        super().__init__(parent)
        self._gimbal = gimbal_widget
        self.setMinimumSize(120, 120)

    def paintEvent(self, event):
        g = self._gimbal
        dx = g._pan_deg    # positive = yaw right
        dy = g._tilt_deg   # positive = pitch down
        max_d = g._max_deflection

        w = self.width()
        h = self.height()
        side = min(w, h) - 16
        if side < 20:
            return
        cx, cy = w / 2.0, h / 2.0

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.fillRect(0, 0, w, h, _BG_COLOR)

        # Concentric circles
        rings = 4
        for i in range(1, rings + 1):
            r = (side / 2.0) * (i / rings)
            pen = QPen(_CIRCLE_COLOR)
            pen.setWidthF(1.0 if i < rings else 1.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

            if i == rings:
                p.setPen(_TEXT_COLOR)
                font = QFont()
                font.setPixelSize(max(9, int(side * 0.06)))
                p.setFont(font)
                label = f"{max_d:.0f}°"
                p.drawText(QPointF(cx + 4, cy - r + 12), label)

        # Crosshair
        pen = QPen(_CROSSHAIR_COLOR)
        pen.setWidthF(0.5)
        p.setPen(pen)
        p.drawLine(QPointF(cx - side / 2, cy), QPointF(cx + side / 2, cy))
        p.drawLine(QPointF(cx, cy - side / 2), QPointF(cx, cy + side / 2))

        # Red deflection dot
        #   dx > 0 (yaw right) → dot moves right on screen → cx + dx
        #   dy > 0 (pitch down) → dot moves down on screen → cy + dy
        scale = (side / 2.0) / max_d if max_d > 0 else 0
        dot_x = cx - dx * scale
        dot_y = cy + dy * scale

        # Clamp to circle
        dist = ((dot_x - cx) ** 2 + (dot_y - cy) ** 2) ** 0.5
        if dist > side / 2:
            dot_x = cx + (dot_x - cx) * (side / 2) / dist
            dot_y = cy + (dot_y - cy) * (side / 2) / dist

        # Glow
        dot_r = max(4, side * 0.04)
        glow = QColor(_DOT_COLOR)
        glow.setAlpha(60)
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(dot_x, dot_y), dot_r * 2.5, dot_r * 2.5)

        # Dot
        p.setBrush(QBrush(_DOT_COLOR))
        p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

        # Center dot
        p.setPen(QPen(_CROSSHAIR_COLOR))
        p.setBrush(QBrush(_CROSSHAIR_COLOR.darker(150)))
        p.drawEllipse(QPointF(cx, cy), 2, 2)

        p.end()

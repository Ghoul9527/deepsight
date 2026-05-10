"""Depth/Time V‑profile chart for freediving sessions.

Draws a coordinate system: Y‑axis = depth (0 m top, 150 m bottom),
X‑axis = time (0 s left, 300 s right). Plots V‑shaped dive profiles.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QPainterPath
from PySide6.QtWidgets import QWidget, QSizePolicy, QVBoxLayout, QLabel

logger = logging.getLogger("host.ui.depth_chart")

MAX_DEPTH_M = 150
MAX_TIME_S = 300
GRID_DEPTH_STEP = 25
GRID_TIME_STEP = 60


@dataclass
class DiveProfile:
    """One complete freedive V‑profile."""
    start_time: float
    max_depth_m: float
    end_time: float
    points: list[tuple[float, float]] = field(default_factory=list)
    # points: [(time_s, depth_m), ...]


class DepthChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 210)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self._dives: list[DiveProfile] = []
        self._current_points: list[tuple[float, float]] = []
        self._session_start: float | None = None
        self._margin_left = 44
        self._margin_right = 16
        self._margin_top = 10
        self._margin_bottom = 24

    def sizeHint(self):
        return self.minimumSize()

    def start_session(self):
        self._session_start = time.monotonic()
        self._dives.clear()
        self._current_points.clear()
        self.update()

    def record_depth(self, depth_m: float):
        """Push a depth sample during a dive."""
        if self._session_start is None:
            self.start_session()
        t = time.monotonic() - self._session_start
        if t > MAX_TIME_S:
            return
        self._current_points.append((t, depth_m))

    def start_dive(self):
        self._current_points.clear()

    def end_dive(self, max_depth_m: float):
        if not self._current_points or self._session_start is None:
            return
        start_t = self._current_points[0][0]
        end_t = self._current_points[-1][0]
        self._dives.append(DiveProfile(
            start_time=start_t,
            max_depth_m=max_depth_m,
            end_time=end_t,
            points=list(self._current_points),
        ))
        self._current_points.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        plot_rect = QRectF(
            self._margin_left,
            self._margin_top,
            w - self._margin_left - self._margin_right,
            h - self._margin_top - self._margin_bottom,
        )

        # Background
        painter.fillRect(self.rect(), QColor("#15152a"))
        painter.fillRect(plot_rect, QColor("#0d0d1a"))

        self._draw_grid(painter, plot_rect)
        self._draw_axes_labels(painter, plot_rect)
        self._draw_dives(painter, plot_rect)

        # Title
        painter.setPen(QColor("#8888cc"))
        font = QFont("Monaco", 10)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 0, w, self._margin_top),
            Qt.AlignCenter,
            "Depth / Time (V‑Profile)",
        )

    def _draw_grid(self, painter: QPainter, rect: QRectF):
        grid_pen = QPen(QColor("#1a1a3a"), 1)
        painter.setPen(grid_pen)

        # Horizontal grid lines (depth)
        for d in range(0, MAX_DEPTH_M + 1, GRID_DEPTH_STEP):
            y = rect.top() + (d / MAX_DEPTH_M) * rect.height()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        # Vertical grid lines (time)
        for t in range(0, MAX_TIME_S + 1, GRID_TIME_STEP):
            x = rect.left() + (t / MAX_TIME_S) * rect.width()
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

    def _draw_axes_labels(self, painter: QPainter, rect: QRectF):
        label_font = QFont("Monaco", 8)
        painter.setFont(label_font)

        # Depth labels (Y)
        painter.setPen(QColor("#6688aa"))
        fm = QFontMetrics(label_font)
        for d in range(0, MAX_DEPTH_M + 1, GRID_DEPTH_STEP):
            y = rect.top() + (d / MAX_DEPTH_M) * rect.height()
            label = f"{d}"
            painter.drawText(
                QRectF(0, y - fm.height() / 2, self._margin_left - 4, fm.height()),
                Qt.AlignRight | Qt.AlignVCenter,
                label,
            )

        # Time labels (X)
        for t in range(0, MAX_TIME_S + 1, GRID_TIME_STEP):
            x = rect.left() + (t / MAX_TIME_S) * rect.width()
            mins, secs = divmod(t, 60)
            label = f"{mins}:{secs:02d}"
            pw = fm.horizontalAdvance(label)
            painter.drawText(
                QRectF(x - pw / 2, rect.bottom() + 2, pw, self._margin_bottom - 2),
                Qt.AlignCenter,
                label,
            )

        # Axis labels
        axis_font = QFont("Monaco", 9, QFont.Bold)
        painter.setFont(axis_font)
        painter.setPen(QColor("#aaaacc"))
        painter.drawText(
            QRectF(0, rect.top() - 2, self._margin_left, 14),
            Qt.AlignCenter,
            "m",
        )
        painter.drawText(
            QRectF(rect.right() + 4, rect.bottom() - 4, 40, 14),
            Qt.AlignLeft,
            "t(s)",
        )

    def _draw_dives(self, painter: QPainter, rect: QRectF):
        if not self._dives and not self._current_points:
            return

        dive_colors = [
            QColor(0, 220, 140),   # teal
            QColor(80, 180, 255),  # light blue
            QColor(255, 180, 60),  # orange
            QColor(220, 80, 220),  # magenta
            QColor(255, 255, 80),  # yellow
        ]

        def to_plot(t_s: float, d_m: float) -> QPointF:
            x = rect.left() + (t_s / MAX_TIME_S) * rect.width()
            y = rect.top() + (d_m / MAX_DEPTH_M) * rect.height()
            return QPointF(x, y)

        # Draw completed dives
        for i, dive in enumerate(self._dives):
            color = dive_colors[i % len(dive_colors)]
            pen = QPen(color, 2)
            painter.setPen(pen)

            if dive.points and len(dive.points) >= 2:
                path = QPainterPath()
                pt = to_plot(*dive.points[0])
                path.moveTo(pt)
                for p in dive.points[1:]:
                    path.lineTo(to_plot(*p))
                painter.drawPath(path)
            else:
                # Fallback: simple V from 3 key points
                mid_t = (dive.start_time + dive.end_time) / 2
                path = QPainterPath()
                path.moveTo(to_plot(dive.start_time, 0))
                path.lineTo(to_plot(mid_t, dive.max_depth_m))
                path.lineTo(to_plot(dive.end_time, 0))
                painter.drawPath(path)

        # Current in-progress dive
        if self._current_points and len(self._current_points) >= 2:
            pen = QPen(QColor(255, 80, 80), 2)
            painter.setPen(pen)
            path = QPainterPath()
            pt = to_plot(*self._current_points[0])
            path.moveTo(pt)
            for p in self._current_points[1:]:
                path.lineTo(to_plot(*p))
            painter.drawPath(path)

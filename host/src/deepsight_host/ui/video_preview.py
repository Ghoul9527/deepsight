"""Video preview widget with OpenCV frame display."""

from __future__ import annotations

import logging

import time

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QWidget, QLabel

from deepsight_host.video.display import VideoDisplay
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.video")


class VideoPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_pixmap: QPixmap | None = None
        self._last_frame: np.ndarray | None = None
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._target_aspect: tuple[int, int] | None = None
        self._recording = False
        self._rec_start_time: float = 0.0
        self._battery_pct: float = 0.0
        self._setup_ui()

    def _setup_ui(self):
        # NO layout on this widget — all children are free-floating.
        # Layout-managed QLabels render CJK text as blocks on macOS/Qt.

        # Video pixmap label — fills widget via setGeometry in resizeEvent
        self._video_label = QLabel(self)
        self._video_label.setAlignment(Qt.AlignCenter)
        self._video_label.setStyleSheet(
            "background-color: #0a0a1a; border: 1px solid #333355;"
        )
        self._video_label.setScaledContents(False)

        # CJK text label — free-floating, fitted to content.
        # Uses setFont() instead of stylesheet font-size to avoid DARK_THEME
        # cascade interference on macOS/Qt.
        self._text_label = QLabel(self)
        self._text_label.setAlignment(Qt.AlignCenter)
        text_font = QFont()
        text_font.setFamilies(["Heiti SC", "STHeiti", "PingFang SC",
                               "Hiragino Sans GB", ".AppleSystemUIFont"])
        text_font.setPointSize(18)
        text_font.setBold(True)
        self._text_label.setFont(text_font)
        self._text_label.setStyleSheet(
            "background: transparent; color: #556677; font-size: 18px; font-weight: bold;"
        )
        self._text_label.setText(tr("video.no_video"))
        self._text_label.adjustSize()

        # Overlays
        self._overlay_label = QLabel(self)
        self._overlay_label.setStyleSheet(
            "background: rgba(0, 0, 0, 160); color: #00ff88; font-size: 14px; "
            "font-weight: bold; padding: 4px 8px; border-radius: 3px;"
        )
        self._overlay_label.setAlignment(Qt.AlignCenter)
        self._overlay_label.setMinimumWidth(160)

        self._rec_label = QLabel(self)
        self._rec_label.setStyleSheet(
            "background: rgba(0, 0, 0, 180); color: #ff3344; font-size: 15px; "
            "font-weight: bold; padding: 4px 10px; border-radius: 3px;"
        )
        self._rec_label.setAlignment(Qt.AlignCenter)
        self._rec_label.hide()

        self._battery_label = QLabel(self)
        self._battery_label.setStyleSheet(
            "background: rgba(0, 0, 0, 160); color: #00cc66; font-size: 13px; "
            "font-weight: bold; padding: 3px 8px; border-radius: 3px;"
        )
        self._battery_label.setAlignment(Qt.AlignCenter)
        self._battery_label.hide()

        self._lock_overlay = QLabel(self)
        self._lock_overlay.setAlignment(Qt.AlignCenter)
        self._lock_overlay.setStyleSheet(
            "background: rgba(180, 0, 0, 200); color: #ffffff; font-size: 22px; "
            "font-weight: bold; padding: 10px 30px; border-radius: 6px;"
        )
        self._lock_overlay.hide()

        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._update_rec_time)

        I18n.instance().language_changed.connect(self._retranslate)

    def _retranslate(self, _lang: str = ""):
        if self._raw_pixmap is None:
            self._text_label.setText(tr("video.no_video"))
            self._text_label.adjustSize()
            self._center_text_label()
        if self._lock_overlay.isVisible():
            self._lock_overlay.setText(tr("video.locked_overlay"))
            self._lock_overlay.adjustSize()
            self._position_overlay()
        if self._battery_label.isVisible() and self._battery_pct > 0:
            self._battery_label.setText(f" {tr('video.battery')} {self._battery_pct:.0f}% ")

    def set_target_aspect(self, ratio: tuple[int, int] | None):
        self._target_aspect = ratio

    def update_frame(self, frame: np.ndarray, fps: float = 0.0, latency_ms: float = 0.0):
        if frame is None:
            return
        self._frame_h, self._frame_w = frame.shape[:2]

        if self._target_aspect is not None:
            frame = self._crop_to_aspect(frame, self._target_aspect)

        self._last_frame = frame.copy()
        self._raw_pixmap = VideoDisplay.frame_to_pixmap(frame)
        self._text_label.hide()
        self._scale_and_display()

        fps_str = f"{fps:.1f}" if fps > 0 else "--"
        lat_str = f"  {latency_ms:.0f}ms" if latency_ms > 0 else ""
        h, w = frame.shape[:2]
        self._overlay_label.setText(
            f"  {w}x{h}  |  {fps_str} FPS{lat_str}  "
        )
        self._overlay_label.adjustSize()
        self._position_overlay()

    @staticmethod
    def _crop_to_aspect(frame: np.ndarray, target: tuple[int, int]) -> np.ndarray:
        h, w = frame.shape[:2]
        tw, th = target
        target_ratio = tw / th
        current_ratio = w / h

        if abs(current_ratio - target_ratio) < 0.02:
            return frame

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            offset = (w - new_w) // 2
            return frame[:, offset:offset + new_w]
        else:
            new_h = int(w / target_ratio)
            offset = (h - new_h) // 2
            return frame[offset:offset + new_h, :]

    def _scale_and_display(self):
        if self._raw_pixmap is None or self._raw_pixmap.isNull():
            return
        label_size = self._video_label.size()
        if label_size.width() <= 2 or label_size.height() <= 2:
            return
        scaled = self._raw_pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self._video_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._video_label.setGeometry(0, 0, self.width(), self.height())
        self._scale_and_display()
        self._position_overlay()
        self._center_text_label()

    def _center_text_label(self):
        label = self._video_label
        tw = self._text_label.width()
        th = self._text_label.height()
        self._text_label.move(
            label.x() + (label.width() - tw) // 2,
            label.y() + (label.height() - th) // 2,
        )

    def _position_overlay(self):
        label = self._video_label
        overlay = self._overlay_label
        oh = overlay.height()
        overlay.move(label.x() + 8, label.y() + label.height() - oh - 8)

        right_x = label.x() + label.width() - 8
        top_y = label.y() + 8

        if self._rec_label.isVisible():
            rw = self._rec_label.width()
            self._rec_label.move(right_x - rw, top_y)
            top_y += self._rec_label.height() + 4

        if self._battery_label.isVisible():
            bw = self._battery_label.width()
            self._battery_label.move(right_x - bw, top_y)

        if self._lock_overlay.isVisible():
            lw = self._lock_overlay.width()
            lh = self._lock_overlay.height()
            self._lock_overlay.move(
                label.x() + (label.width() - lw) // 2,
                label.y() + (label.height() - lh) // 2,
            )

    def _update_rec_time(self):
        elapsed = int(time.time() - self._rec_start_time)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        if h:
            self._rec_label.setText(f"● REC {h}:{m:02d}:{s:02d}")
        else:
            self._rec_label.setText(f"● REC {m:02d}:{s:02d}")
        self._rec_label.adjustSize()
        self._position_overlay()

    def set_recording(self, recording: bool):
        if recording and not self._recording:
            self._recording = True
            self._rec_start_time = time.time()
            self._rec_label.show()
            self._rec_timer.start(500)
            self._update_rec_time()
        elif not recording and self._recording:
            self._recording = False
            self._rec_timer.stop()
            self._rec_label.hide()

    def set_battery(self, pct: float):
        self._battery_pct = pct
        if pct <= 0:
            self._battery_label.hide()
            return
        self._battery_label.setText(f" {tr('video.battery')} {pct:.0f}% ")
        self._battery_label.show()
        self._position_overlay()

    def set_lock_overlay(self, locked: bool):
        if locked:
            self._lock_overlay.setText(tr("video.locked_overlay"))
            self._lock_overlay.adjustSize()
            self._lock_overlay.show()
        else:
            self._lock_overlay.hide()
        self._position_overlay()

    def set_overlay(self, text: str):
        self._overlay_label.setText(text)

    def force_repaint(self):
        if self._last_frame is not None:
            self._raw_pixmap = VideoDisplay.frame_to_pixmap(self._last_frame)
        self._scale_and_display()
        self._video_label.update()
        self._video_label.repaint()
        self.update()
        self.repaint()

    def clear(self):
        self._video_label.setPixmap(QPixmap())
        self._raw_pixmap = None
        self._last_frame = None
        self._text_label.setText(tr("video.no_video"))
        self._text_label.adjustSize()
        self._text_label.show()
        self._center_text_label()

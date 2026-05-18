"""Video preview widget with OpenCV frame display."""

from __future__ import annotations

import logging

import time

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

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
        self._target_aspect: tuple[int, int] | None = None  # (w, h) for cropping
        self._recording = False
        self._rec_start_time: float = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(tr("video.no_video"))
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(640, 360)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setStyleSheet(
            "background-color: #0a0a1a; border: 1px solid #333355; color: #444466;"
        )
        self._label.setScaledContents(False)
        layout.addWidget(self._label)

        self._overlay_label = QLabel(self._label)
        self._overlay_label.setStyleSheet(
            "background: rgba(0, 0, 0, 160); color: #00ff88; font-size: 14px; "
            "font-weight: bold; padding: 4px 8px; border-radius: 3px;"
        )
        self._overlay_label.setAlignment(Qt.AlignCenter)
        self._overlay_label.setMinimumWidth(160)

        # Recording indicator (top-right)
        self._rec_label = QLabel(self._label)
        self._rec_label.setStyleSheet(
            "background: rgba(0, 0, 0, 180); color: #ff3344; font-size: 15px; "
            "font-weight: bold; padding: 4px 10px; border-radius: 3px;"
        )
        self._rec_label.setAlignment(Qt.AlignCenter)
        self._rec_label.hide()

        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._update_rec_time)

        I18n.instance().language_changed.connect(self._retranslate)

    def _retranslate(self, _lang: str = ""):
        if self._raw_pixmap is None:
            self._label.setText(tr("video.no_video"))

    def set_target_aspect(self, ratio: tuple[int, int] | None):
        """Set target aspect ratio for cropping (e.g., (16, 9) or None for native)."""
        self._target_aspect = ratio

    def update_frame(self, frame: np.ndarray, fps: float = 0.0, latency_ms: float = 0.0):
        if frame is None:
            return
        self._frame_h, self._frame_w = frame.shape[:2]

        # Crop to target aspect ratio if set
        if self._target_aspect is not None:
            frame = self._crop_to_aspect(frame, self._target_aspect)

        self._last_frame = frame.copy()
        self._raw_pixmap = VideoDisplay.frame_to_pixmap(frame)
        self._scale_and_display()

        # Update overlay with resolution + FPS + end-to-end latency
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
        """Center-crop frame to the target aspect ratio."""
        h, w = frame.shape[:2]
        tw, th = target
        target_ratio = tw / th
        current_ratio = w / h

        if abs(current_ratio - target_ratio) < 0.02:
            return frame  # Already close enough

        if current_ratio > target_ratio:
            # Frame too wide — crop width
            new_w = int(h * target_ratio)
            offset = (w - new_w) // 2
            return frame[:, offset:offset + new_w]
        else:
            # Frame too tall — crop height
            new_h = int(w / target_ratio)
            offset = (h - new_h) // 2
            return frame[offset:offset + new_h, :]

    def _scale_and_display(self):
        if self._raw_pixmap is None or self._raw_pixmap.isNull():
            return
        label_size = self._label.size()
        if label_size.width() <= 2 or label_size.height() <= 2:
            return
        scaled = self._raw_pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self._label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_and_display()
        self._position_overlay()

    def _position_overlay(self):
        """Pin overlay to bottom-left, rec indicator to top-right."""
        label = self._label
        overlay = self._overlay_label
        ow = overlay.width()
        oh = overlay.height()
        x = 8
        y = label.height() - oh - 8
        overlay.move(x, max(y, 0))

        if self._rec_label.isVisible():
            rw = self._rec_label.width()
            self._rec_label.move(label.width() - rw - 8, 8)

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

    def set_overlay(self, text: str):
        self._overlay_label.setText(text)

    def force_repaint(self):
        """Recreate pixmap and repaint — for macOS fullscreen transitions.
        The backing store may change during space transitions, so the old
        QPixmap needs to be rebuilt from the raw frame data."""
        if self._last_frame is not None:
            self._raw_pixmap = VideoDisplay.frame_to_pixmap(self._last_frame)
        self._scale_and_display()
        self._label.update()
        self._label.repaint()
        self.update()
        self.repaint()

    def clear(self):
        self._label.setText(tr("video.no_video"))
        self._label.setPixmap(QPixmap())
        self._raw_pixmap = None
        self._last_frame = None

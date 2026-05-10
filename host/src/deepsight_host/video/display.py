"""OpenCV ↔ Qt pixmap bridge for video display in PySide6."""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt

logger = logging.getLogger("host.video.display")


class VideoDisplay:
    @staticmethod
    def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
        h, w, ch = frame.shape
        bytes_per_line = ch * w

        if ch == 3:
            # BGR → RGB, deep-copy so QImage owns its data independently of numpy
            rgb = frame[..., ::-1].copy()
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        elif ch == 1:
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_Grayscale8).copy()
        elif ch == 4:
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGBA8888).copy()
        else:
            logger.error("Unsupported frame channels: %d", ch)
            return QPixmap()

        return QPixmap.fromImage(qimg)

    @staticmethod
    def frame_to_qimage(frame: np.ndarray) -> QImage:
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        if ch == 3:
            rgb = frame[..., ::-1].copy()
            return QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        elif ch == 4:
            return QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGBA8888)
        return QImage(frame.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

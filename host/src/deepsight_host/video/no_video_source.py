"""NoVideoSource — black frame with "No Video Signal" placeholder.

Used when no real video source (Pi stream, camera, or file) is configured.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

NO_SIGNAL_TEXT_EN = "No Video Signal"
NO_SIGNAL_TEXT_ZH = "无视频信号"


class NoVideoSource:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._frame = None
        self._build_frame()

    def _build_frame(self):
        h, w = self.height, self.width
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Grid lines for visual reference
        if cv2:
            for i in range(0, w, 120):
                cv2.line(frame, (i, 0), (i, h), (10, 10, 20), 1)
            for i in range(0, h, 90):
                cv2.line(frame, (0, i), (w, i), (10, 10, 20), 1)

        text = NO_SIGNAL_TEXT_ZH
        if Image:
            self._draw_text_pil(frame, text)
        elif cv2:
            self._draw_text_cv2(frame, NO_SIGNAL_TEXT_EN)

        self._frame = frame

    def _draw_text_pil(self, frame: np.ndarray, text: str):
        h, w = frame.shape[:2]
        pil_img = Image.fromarray(frame)
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 48)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
            except (OSError, IOError):
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (w - tw) // 2
        ty = (h - th) // 2
        draw.text((tx, ty), text, font=font, fill=(80, 80, 80))
        frame[:] = np.array(pil_img)

    def _draw_text_cv2(self, frame: np.ndarray, text: str):
        h, w = frame.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), baseline = cv2.getTextSize(text, font, 1.5, 3)
        tx = (w - tw) // 2
        ty = (h + th) // 2
        cv2.putText(frame, text, (tx, ty), font, 1.5, (80, 80, 80), 3)

    def read(self) -> np.ndarray | None:
        return self._frame.copy()

    def close(self):
        pass

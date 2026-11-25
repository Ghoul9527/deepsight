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

from deepsight_host.ui.i18n import tr


class NoVideoSource:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._placeholder: np.ndarray | None = None
        self._placeholder_text = ""

    def _build_frame(self, text: str) -> np.ndarray:
        h, w = self.height, self.width
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        if cv2:
            for i in range(0, w, 120):
                cv2.line(frame, (i, 0), (i, h), (10, 10, 20), 1)
            for i in range(0, h, 90):
                cv2.line(frame, (0, i), (w, i), (10, 10, 20), 1)

        if Image:
            self._draw_text_pil(frame, text)
        elif cv2:
            self._draw_text_cv2(frame, text)

        return frame

    def _draw_text_pil(self, frame: np.ndarray, text: str):
        h, w = frame.shape[:2]
        pil_img = Image.fromarray(frame)
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 48)
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

    def placeholder(self) -> np.ndarray:
        """Return the shared, read-only frame for an inactive preview."""
        text = tr("video.no_video")
        if self._placeholder is None or text != self._placeholder_text:
            frame = self._build_frame(text)
            frame.flags.writeable = False
            self._placeholder = frame
            self._placeholder_text = text
        return self._placeholder

    def read(self) -> np.ndarray:
        return self.placeholder().copy()

    def frame_age_ms(self) -> float:
        return 0.0

    def stale(self, threshold: float = 3.0) -> bool:
        return False

    def close(self):
        pass

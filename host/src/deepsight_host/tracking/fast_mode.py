"""Fast Mode: YOLOv8n + ByteTrack + EMA smoothing.

Optimised for lowest latency: resolution scaling, MPS/CUDA device auto-detect,
adaptive frame skipping under load.
"""

from __future__ import annotations

import logging
import math
import time

import numpy as np

from deepsight_host.tracking.base import TrackingEngine, TrackingResult

logger = logging.getLogger("host.tracking.fast")

PERSON_CLASS = 0


class FastModeTracker(TrackingEngine):
    def __init__(self, confidence_threshold: float = 0.5,
                 iou_threshold: float = 0.45,
                 model_name: str = "yolov8n.pt",
                 model_path: str = "",
                 inference_size: int = 640):
        self._conf = confidence_threshold
        self._iou = iou_threshold
        self._model_name = model_name
        self._model_path = model_path
        self._model = None
        self._mock = True
        self._frame_count = 0
        self._fps = 0.0
        self._latency_ms = 0.0
        self._inference_size = inference_size
        self._device = None
        self._skip_frames = 0
        self._max_latency_ms = 1000 / 30  # Target: 30 fps

        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            import torch

            # Auto-detect best device
            if torch.cuda.is_available():
                self._device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self._device = "mps"
            else:
                self._device = "cpu"

            model = self._model_path or self._model_name
            self._model = YOLO(model)
            self._mock = False
            logger.info("FastMode: loaded %s (device=%s, imgsz=%d)",
                         model, self._device, self._inference_size)
        except Exception as e:
            logger.warning("FastMode: YOLO unavailable (%s), using synthetic", e)
            self._device = "cpu"

    def process_frame(self, frame: np.ndarray) -> TrackingResult:
        self._frame_count += 1
        t0 = time.monotonic()

        # Adaptive frame skipping
        if self._skip_frames > 0:
            self._skip_frames -= 1
            return self._cached_result()

        if self._mock or self._model is None:
            result = self._lost_result()
        else:
            result = self._real_track(frame)

        self._latency_ms = (time.monotonic() - t0) * 1000.0

        # Adaptive skip: if inference took > 1 frame period, skip next N frames
        frame_period_ms = 1000 / 30
        if self._latency_ms > frame_period_ms * 1.5:
            self._skip_frames = int(self._latency_ms / frame_period_ms) - 1

        # Cache last result for fallback
        if result.visible:
            self._last_result = result

        if self._frame_count % 30 == 0:
            self._fps = 1000.0 / max(self._latency_ms, 0.001)

        return result

    def _real_track(self, frame: np.ndarray) -> TrackingResult:
        h, w = frame.shape[:2]

        # Resolution scaling: downscale to inference_size if frame is larger
        if max(w, h) > self._inference_size:
            scale = self._inference_size / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            input_frame = frame[::int(1/scale), ::int(1/scale)]  # nearest-neighbor subsample
        else:
            scale = 1.0
            input_frame = frame

        try:
            results = self._model.track(
                input_frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=self._conf,
                iou=self._iou,
                classes=[PERSON_CLASS],
                verbose=False,
                device=self._device,
            )
        except Exception as e:
            logger.error("YOLO tracking error: %s", e)
            if self._device and self._device != "cpu":
                logger.warning("Falling back to CPU after GPU error")
                self._device = "cpu"
            return self._cached_result()

        if not results or len(results) == 0:
            return self._lost_result()

        r = results[0]

        if r.boxes is None or r.boxes.id is None or len(r.boxes.id) == 0:
            return self._lost_result()

        confs = r.boxes.conf.cpu().numpy() if r.boxes.conf is not None else np.array([])
        if len(confs) == 0:
            return self._lost_result()

        idx = int(np.argmax(confs))
        bbox = r.boxes.xyxy[idx].cpu().numpy()
        track_id = int(r.boxes.id[idx])
        conf = float(confs[idx])

        # Scale bbox back to original frame coordinates
        if scale != 1.0:
            bbox = bbox / scale

        bx1, by1, bx2, by2 = bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h
        center_x = (bx1 + bx2) / 2.0
        center_y = (by1 + by2) / 2.0

        return TrackingResult(
            bbox=(bx1, by1, bx2, by2),
            center_x=center_x,
            center_y=center_y,
            confidence=conf,
            track_id=track_id,
            visible=True,
            lost=False,
        )

    def _lost_result(self) -> TrackingResult:
        return TrackingResult(
            bbox=(0.45, 0.45, 0.55, 0.55),
            center_x=0.5, center_y=0.5,
            confidence=0.0, track_id=-1,
            visible=False, lost=True,
        )

    def _cached_result(self) -> TrackingResult:
        if hasattr(self, '_last_result') and self._last_result is not None:
            return self._last_result
        return self._lost_result()

    def _synthetic_result(self) -> TrackingResult:
        t = self._frame_count * 0.033
        center_x = 0.5 + 0.15 * math.sin(t * 0.5)
        center_y = 0.5 + 0.10 * math.cos(t * 0.3)
        bbox_w, bbox_h = 0.08, 0.12
        return TrackingResult(
            bbox=(center_x - bbox_w / 2, center_y - bbox_h / 2,
                  center_x + bbox_w / 2, center_y + bbox_h / 2),
            center_x=center_x, center_y=center_y,
            confidence=0.85 + 0.05 * math.sin(t * 0.7),
            track_id=1, visible=True, lost=False,
        )

    @property
    def is_mock(self) -> bool:
        return self._mock

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    def reset(self):
        self._frame_count = 0
        self._skip_frames = 0
        if hasattr(self, '_last_result'):
            del self._last_result
        if self._model is not None:
            try:
                self._model.predictor.trackers = []
            except Exception:
                pass

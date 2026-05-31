"""Fast Mode: YOLOv8 + BoTSORT + adaptive EMA + motion prediction.

Stable synchronous pipeline tuned for underwater tracking at 30 fps.
Resolution scaling, MPS/CUDA auto-detect, adaptive frame skipping under load.
"""

from __future__ import annotations

import logging
import math
import time

import numpy as np

import cv2

from deepsight_host.tracking.base import TrackingEngine, TrackingResult

logger = logging.getLogger("host.tracking.fast")

PERSON_CLASS = 0


class FastModeTracker(TrackingEngine):
    def __init__(self, confidence_threshold: float = 0.5,
                 iou_threshold: float = 0.45,
                 model_name: str = "yolov8n.pt",
                 model_path: str = "",
                 inference_size: int = 640,
                 motion_predict_ms: float = 10000):
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

        # Adaptive EMA
        self._ema_alpha_min = 0.12
        self._ema_alpha_max = 0.65
        self._smooth_cx: float | None = None
        self._smooth_cy: float | None = None
        self._smooth_w: float | None = None
        self._smooth_h: float | None = None

        # Motion prediction
        self._motion_predict_ms = motion_predict_ms
        self._last_track_time: float | None = None
        self._last_cx: float = 0.5
        self._last_cy: float = 0.5
        self._last_w: float = 0.1
        self._last_h: float = 0.1
        self._vel_x: float = 0.0
        self._vel_y: float = 0.0
        self._lost_at: float | None = None
        self._persistent_id: int = 1  # single-target: always same ID

        self._init_model()

    # ── model init ──────────────────────────────────────────────

    def _init_model(self):
        try:
            from ultralytics import YOLO
            import torch

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

    # ── main entry ──────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> TrackingResult:
        self._frame_count += 1
        t0 = time.monotonic()

        # Adaptive frame skip
        if self._skip_frames > 0:
            self._skip_frames -= 1
            return self._cached_result()

        if self._mock or self._model is None:
            result = self._synthetic_result()
        else:
            result = self._real_track(frame)

        self._latency_ms = (time.monotonic() - t0) * 1000.0

        # Periodic MPS cache flush to prevent memory fragmentation
        if self._frame_count % 300 == 0 and self._device == "mps":
            try:
                import torch
                torch.mps.empty_cache()
            except Exception:
                pass

        # Adaptive frame skip when latency exceeds 1.5x frame budget
        frame_budget_ms = 1000 / 30
        if self._latency_ms > frame_budget_ms * 1.5:
            self._skip_frames = min(4, int(self._latency_ms / frame_budget_ms) - 1)

        if result.visible:
            self._last_result = result
            self._last_track_time = time.monotonic()

        if self._frame_count % 30 == 0:
            self._fps = 1000.0 / max(self._latency_ms, 0.001)

        return result

    # ── real tracking (sync, all on resized frame) ──────────────

    def _real_track(self, frame: np.ndarray) -> TrackingResult:
        h, w = frame.shape[:2]

        # Resolution scaling
        if max(w, h) > self._inference_size:
            scale = self._inference_size / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            input_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            scale = 1.0
            input_frame = frame

        rh, rw = input_frame.shape[:2]

        # YOLO + BoTSORT
        try:
            results = self._model.track(
                input_frame,
                persist=True,
                tracker="botsort.yaml",
                conf=self._conf,
                iou=self._iou,
                classes=[PERSON_CLASS],
                verbose=False,
                device=self._device,
            )
        except Exception:
            return self._motion_predict()

        # Extract best detection
        if not results or len(results) == 0:
            return self._motion_predict()

        r = results[0]
        if r.boxes is None or r.boxes.id is None or len(r.boxes.id) == 0:
            return self._motion_predict()

        confs = r.boxes.conf.cpu().numpy() if r.boxes.conf is not None else np.array([])
        if len(confs) == 0:
            return self._motion_predict()

        idx = int(np.argmax(confs))
        bbox = r.boxes.xyxy[idx].cpu().numpy()
        conf = float(confs[idx])

        # Normalize to resized frame
        bx1 = bbox[0] / rw
        by1 = bbox[1] / rh
        bx2 = bbox[2] / rw
        by2 = bbox[3] / rh
        cx_norm = (bx1 + bx2) / 2.0
        cy_norm = (by1 + by2) / 2.0
        bw_norm = bx2 - bx1
        bh_norm = by2 - by1

        # Adaptive EMA
        adaptive_alpha = self._ema_alpha_min + (self._ema_alpha_max - self._ema_alpha_min) * conf

        if self._smooth_cx is not None:
            self._smooth_cx = adaptive_alpha * cx_norm + (1 - adaptive_alpha) * self._smooth_cx
            self._smooth_cy = adaptive_alpha * cy_norm + (1 - adaptive_alpha) * self._smooth_cy
            self._smooth_w = adaptive_alpha * bw_norm + (1 - adaptive_alpha) * self._smooth_w
            self._smooth_h = adaptive_alpha * bh_norm + (1 - adaptive_alpha) * self._smooth_h
        else:
            self._smooth_cx = cx_norm
            self._smooth_cy = cy_norm
            self._smooth_w = bw_norm
            self._smooth_h = bh_norm

        # Velocity update
        now = time.monotonic()
        dt = now - self._last_track_time if self._last_track_time else 0.033
        dt = max(dt, 0.001)
        self._vel_x = (self._smooth_cx - self._last_cx) / dt
        self._vel_y = (self._smooth_cy - self._last_cy) / dt
        self._last_cx = self._smooth_cx
        self._last_cy = self._smooth_cy
        self._last_w = self._smooth_w
        self._last_h = self._smooth_h
        self._lost_at = None

        return TrackingResult(
            bbox=(self._smooth_cx - self._smooth_w / 2, self._smooth_cy - self._smooth_h / 2,
                  self._smooth_cx + self._smooth_w / 2, self._smooth_cy + self._smooth_h / 2),
            center_x=self._smooth_cx,
            center_y=self._smooth_cy,
            confidence=conf,
            track_id=self._persistent_id,
            visible=True,
            lost=False,
        )

    # ── motion prediction ───────────────────────────────────────

    def _motion_predict(self) -> TrackingResult:
        if self._lost_at is None:
            self._lost_at = time.monotonic()

        elapsed_ms = (time.monotonic() - self._lost_at) * 1000
        if elapsed_ms > self._motion_predict_ms:
            return self._lost_result()

        elapsed_s = elapsed_ms / 1000.0
        pred_cx = self._last_cx + self._vel_x * elapsed_s
        pred_cy = self._last_cy + self._vel_y * elapsed_s
        pred_w = self._last_w
        pred_h = self._last_h

        decay = max(0.0, 1.0 - elapsed_ms / self._motion_predict_ms)
        pred_conf = 0.5 * decay

        return TrackingResult(
            bbox=(pred_cx - pred_w / 2, pred_cy - pred_h / 2,
                  pred_cx + pred_w / 2, pred_cy + pred_h / 2),
            center_x=pred_cx,
            center_y=pred_cy,
            confidence=pred_conf,
            track_id=self._persistent_id,
            visible=False,
            lost=False,
        )

    # ── fallbacks ───────────────────────────────────────────────

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
            track_id=self._persistent_id, visible=True, lost=False,
        )

    # ── properties ──────────────────────────────────────────────

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
        self._smooth_cx = None
        self._smooth_cy = None
        self._smooth_w = None
        self._smooth_h = None
        self._vel_x = 0.0
        self._vel_y = 0.0
        self._lost_at = None
        self._last_track_time = None
        if hasattr(self, '_last_result'):
            del self._last_result
        if self._model is not None:
            try:
                self._model.predictor.trackers = []
            except Exception:
                pass

    def close(self):
        pass

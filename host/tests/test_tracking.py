"""Tests for the tracking pipeline: base, Kalman, EMA, fast/precise modes, registry.

Note: When ultralytics YOLO is installed `is_mock` will be `False`; when it is
not, `is_mock` will be `True`.  Tests accommodate both environments.
"""

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# tracking.base
# ---------------------------------------------------------------------------

class TestTrackingResult:
    def test_create_default_tracking_result(self):
        from deepsight_host.tracking.base import TrackingResult
        r = TrackingResult(
            bbox=(0.1, 0.2, 0.3, 0.4),
            center_x=0.2,
            center_y=0.3,
            confidence=0.88,
            track_id=5,
            visible=True,
            lost=False,
        )
        assert r.center_x == 0.2
        assert r.center_y == 0.3
        assert r.confidence == 0.88
        assert r.track_id == 5
        assert r.visible is True
        assert r.lost is False
        assert r.bbox == (0.1, 0.2, 0.3, 0.4)

    def test_tracking_result_optional_fields_default(self):
        from deepsight_host.tracking.base import TrackingResult
        r = TrackingResult(
            bbox=(0.0, 0.0, 1.0, 1.0),
            center_x=0.5,
            center_y=0.5,
            confidence=0.0,
            track_id=-1,
            visible=False,
            lost=True,
        )
        assert r.mask is None
        assert r.pose_landmarks is None

    def test_tracking_result_with_mask(self):
        from deepsight_host.tracking.base import TrackingResult
        r = TrackingResult(
            bbox=(0.1, 0.1, 0.2, 0.2),
            center_x=0.15,
            center_y=0.15,
            confidence=0.75,
            track_id=2,
            visible=True,
            lost=False,
            mask="fake_mask_array",
        )
        assert r.mask == "fake_mask_array"

    def test_tracking_result_equality(self):
        from deepsight_host.tracking.base import TrackingResult
        r1 = TrackingResult(
            bbox=(0.1, 0.2, 0.3, 0.4), center_x=0.2, center_y=0.3,
            confidence=0.9, track_id=1, visible=True, lost=False,
        )
        r2 = TrackingResult(
            bbox=(0.1, 0.2, 0.3, 0.4), center_x=0.2, center_y=0.3,
            confidence=0.9, track_id=1, visible=True, lost=False,
        )
        assert r1 == r2

    def test_tracking_result_inequality(self):
        from deepsight_host.tracking.base import TrackingResult
        r1 = TrackingResult(
            bbox=(0.1, 0.2, 0.3, 0.4), center_x=0.2, center_y=0.3,
            confidence=0.9, track_id=1, visible=True, lost=False,
        )
        r2 = TrackingResult(
            bbox=(0.1, 0.2, 0.3, 0.4), center_x=0.2, center_y=0.3,
            confidence=0.9, track_id=2, visible=True, lost=False,
        )
        assert r1 != r2


class TestTrackingEngineABC:
    def test_cannot_instantiate_abc(self):
        from deepsight_host.tracking.base import TrackingEngine
        with pytest.raises(TypeError):
            TrackingEngine()  # abstract

    def test_concrete_subclass_must_implement_all(self):
        from deepsight_host.tracking.base import TrackingEngine
        # Missing reset -> still abstract
        class IncompleteTracker(TrackingEngine):
            def process_frame(self, frame):
                pass
        with pytest.raises(TypeError):
            IncompleteTracker()


# ---------------------------------------------------------------------------
# tracking.kalman
# ---------------------------------------------------------------------------

class TestKalmanPredictor:
    def test_initial_state(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        assert kf.predicted_position == (0.5, 0.5)
        assert kf.uncertainty > 0.0

    def test_predict_updates_position(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        new = kf.predict()
        assert isinstance(new, tuple)
        assert len(new) == 2

    def test_uncertainty_grows_with_predicts_without_update(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        # Do a single update first so the filter is initialized
        kf.update((0.5, 0.5))
        u1 = kf.uncertainty
        for _ in range(5):
            kf.predict()
        u2 = kf.uncertainty
        # Uncertainty should grow after multiple predicts without measurement
        assert u2 > u1

    def test_update_reduces_uncertainty(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        # Initial predict to set up
        kf.predict()
        u_before = kf.uncertainty
        kf.update((0.5, 0.5))
        u_after = kf.uncertainty
        # After an update, uncertainty should drop
        assert u_after < u_before

    def test_update_moves_prediction_toward_measurement(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        kf.update((0.5, 0.5))  # Initialize near 0.5
        kf.update((0.7, 0.7))  # Shift right/down
        px, py = kf.predicted_position
        # Position should have moved toward (0.7, 0.7)
        assert px > 0.5
        assert py > 0.5

    def test_reset_clears_kalman_state(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor()
        kf.update((0.3, 0.3))
        kf.predict()
        kf.reset()
        assert kf._initialized is False
        assert kf._steps_since_update == 0
        # The internal filter state x is zeroed
        assert kf._kf["x"][0] == 0.0
        assert kf._kf["x"][1] == 0.0

    def test_custom_parameters_accepted(self):
        from deepsight_host.tracking.kalman import KalmanPredictor
        kf = KalmanPredictor(dt=1.0 / 60.0, process_noise=0.02, measurement_noise=0.05)
        assert kf._kf["dt"] == pytest.approx(1.0 / 60.0)
        assert kf._kf["q"] == 0.02
        assert kf._kf["r"] == 0.05


# ---------------------------------------------------------------------------
# tracking.smoother
# ---------------------------------------------------------------------------

class TestEMASmoother:
    def test_initial_current_is_none(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother()
        assert s.current is None

    def test_first_update_sets_value(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother(alpha=0.3)
        result = s.update((0.6, 0.7))
        assert result == (0.6, 0.7)
        assert s.current == (0.6, 0.7)

    def test_ema_converges_toward_target(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother(alpha=0.5)
        s.update((0.0, 0.0))
        result = s.update((1.0, 1.0))
        # With alpha=0.5: 0.5*1.0 + 0.5*0.0 = 0.5
        assert result[0] == 0.5
        assert result[1] == 0.5

    def test_ema_steady_state_converges(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother(alpha=0.1)
        s.update((1.0, 1.0))
        for _ in range(100):
            s.update((1.0, 1.0))
        cx, cy = s.current
        assert math.isclose(cx, 1.0, rel_tol=1e-4)
        assert math.isclose(cy, 1.0, rel_tol=1e-4)

    def test_reset_clears_value(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother()
        s.update((0.3, 0.4))
        assert s.current is not None
        s.reset()
        assert s.current is None

    def test_custom_alpha(self):
        from deepsight_host.tracking.smoother import EMASmoother
        s = EMASmoother(alpha=0.8)
        s.update((0.0, 0.0))
        result = s.update((1.0, 0.0))
        # 0.8 * 1.0 + 0.2 * 0.0 = 0.8
        assert result[0] == 0.8
        assert result[1] == 0.0


# ---------------------------------------------------------------------------
# tracking.fast_mode
# ---------------------------------------------------------------------------

class TestFastModeTracker:
    def test_constructor_creates_valid_tracker(self):
        """The tracker must construct without error regardless of YOLO availability."""
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        # is_mock depends on whether ultralytics is installed
        assert isinstance(tracker.is_mock, bool)
        # Must have a device string
        assert isinstance(tracker._device, str)

    def test_synthetic_result_produces_valid_coords(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        r = tracker._synthetic_result()
        assert 0.0 < r.center_x < 1.0
        assert 0.0 < r.center_y < 1.0
        assert 0.0 < r.confidence <= 1.0
        assert r.visible is True
        assert r.lost is False
        assert r.track_id == 1
        # bbox contains 4 elements all in [0,1]
        assert len(r.bbox) == 4
        for v in r.bbox:
            assert 0.0 <= v <= 1.0
        # center is midpoint of bbox
        bx1, by1, bx2, by2 = r.bbox
        assert math.isclose(r.center_x, (bx1 + bx2) / 2.0, rel_tol=1e-9)
        assert math.isclose(r.center_y, (by1 + by2) / 2.0, rel_tol=1e-9)

    def test_synthetic_result_changes_over_time(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        r1 = tracker._synthetic_result()
        # Advance frame counter to get a different position
        tracker._frame_count = 10
        r2 = tracker._synthetic_result()
        # Coordinates should differ (the sine/cosine moves it)
        assert (r1.center_x != r2.center_x) or (r1.center_y != r2.center_y)

    def test_lost_result_has_visible_false(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        r = tracker._lost_result()
        assert r.visible is False
        assert r.lost is True
        assert r.confidence == 0.0
        assert r.track_id == -1
        # center should be at nominal center
        assert r.center_x == 0.5
        assert r.center_y == 0.5

    def test_cached_result_returns_last_when_available(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        # No cached result yet -> should return lost
        r = tracker._cached_result()
        assert r.lost is True
        # Set a cached result
        tracker._last_result = tracker._synthetic_result()
        r2 = tracker._cached_result()
        assert r2.lost is False
        assert r2.visible is True

    def test_reset_clears_state(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        tracker._frame_count = 42
        tracker._skip_frames = 3
        tracker._last_result = tracker._synthetic_result()
        tracker.reset()
        assert tracker._frame_count == 0
        assert tracker._skip_frames == 0
        assert not hasattr(tracker, '_last_result')

    def test_process_frame_returns_tracking_result(self):
        """process_frame must return a TrackingResult in any mode."""
        from deepsight_host.tracking.fast_mode import FastModeTracker
        from deepsight_host.tracking.base import TrackingResult
        tracker = FastModeTracker()
        dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = tracker.process_frame(dummy_frame)
        assert isinstance(result, TrackingResult)
        # When model unavailable, returns lost result (not synthetic data)
        if tracker.is_mock:
            assert result.visible is False
            assert result.lost is True

    def test_fps_and_latency_properties(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        # Initially zero
        assert tracker.fps == 0.0
        assert tracker.latency_ms == 0.0

    def test_default_confidence_threshold(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        assert tracker._conf == 0.5

    def test_custom_parameters(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker(
            confidence_threshold=0.7,
            iou_threshold=0.5,
            inference_size=320,
        )
        assert tracker._conf == 0.7
        assert tracker._iou == 0.5
        assert tracker._inference_size == 320

    def test_frame_skipping_uses_cached_result(self):
        from deepsight_host.tracking.fast_mode import FastModeTracker
        tracker = FastModeTracker()
        # Manually set skip_frames to simulate heavy-load skip
        tracker._skip_frames = 2
        tracker._last_result = tracker._synthetic_result()
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = tracker.process_frame(dummy_frame)
        assert tracker._skip_frames == 1  # decremented
        assert not result.lost  # got cached


# ---------------------------------------------------------------------------
# tracking.precise_mode
# ---------------------------------------------------------------------------

class TestPreciseModeTracker:
    def test_constructor_creates_valid_tracker(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        tracker = PreciseModeTracker()
        assert isinstance(tracker.is_mock, bool)
        assert isinstance(tracker._device, str)

    def test_synthetic_result_produces_valid_coords(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        tracker = PreciseModeTracker()
        r = tracker._synthetic_result()
        assert 0.0 < r.center_x < 1.0
        assert 0.0 < r.center_y < 1.0
        assert 0.0 < r.confidence <= 1.0
        assert r.visible is True
        assert r.lost is False
        assert r.track_id == 1
        assert len(r.bbox) == 4
        for v in r.bbox:
            assert 0.0 <= v <= 1.0

    def test_lost_result_has_visible_false(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        tracker = PreciseModeTracker()
        r = tracker._lost_result()
        assert r.visible is False
        assert r.lost is True
        assert r.confidence == 0.0
        assert r.track_id == -1

    def test_reset_clears_state(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        tracker = PreciseModeTracker()
        tracker._frame_count = 99
        tracker._skip_frames = 5
        tracker._last_result = tracker._synthetic_result()
        tracker.reset()
        assert tracker._frame_count == 0
        assert tracker._skip_frames == 0
        assert not hasattr(tracker, '_last_result')

    def test_process_frame_returns_tracking_result(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        from deepsight_host.tracking.base import TrackingResult
        tracker = PreciseModeTracker()
        dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = tracker.process_frame(dummy_frame)
        assert isinstance(result, TrackingResult)
        # When model unavailable, returns lost result (not synthetic data)
        if tracker.is_mock:
            assert result.visible is False
            assert result.lost is True

    def test_fps_and_latency_properties(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        tracker = PreciseModeTracker()
        assert tracker.fps == 0.0
        assert tracker.latency_ms == 0.0

    def test_defaults_differ_from_fast_mode(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        from deepsight_host.tracking.fast_mode import FastModeTracker
        precise = PreciseModeTracker()
        fast = FastModeTracker()
        # Precise has higher confidence threshold and larger inference size
        assert precise._conf > fast._conf
        assert precise._inference_size > fast._inference_size

    def test_synthetic_trajectory_differs_from_fast(self):
        from deepsight_host.tracking.precise_mode import PreciseModeTracker
        from deepsight_host.tracking.fast_mode import FastModeTracker
        precise = PreciseModeTracker()
        fast = FastModeTracker()
        # Use frame_count=1 so t is non-zero and trajectories actually differ
        precise._frame_count = 1
        fast._frame_count = 1
        rp = precise._synthetic_result()
        rf = fast._synthetic_result()
        # Trajectories are different (different math expressions)
        assert (rp.center_x != rf.center_x) or (rp.center_y != rf.center_y)


# ---------------------------------------------------------------------------
# tracking.registry
# ---------------------------------------------------------------------------

class TestTrackerRegistry:
    def test_list_trackers_returns_known(self):
        from deepsight_host.tracking.registry import list_trackers
        trackers = list_trackers()
        assert "fast" in trackers
        assert "precise" in trackers

    def test_get_tracker_fast_returns_engine(self):
        from deepsight_host.tracking.registry import get_tracker
        from deepsight_host.tracking.base import TrackingEngine
        tracker = get_tracker("fast")
        assert isinstance(tracker, TrackingEngine)

    def test_get_tracker_precise_returns_engine(self):
        from deepsight_host.tracking.registry import get_tracker
        from deepsight_host.tracking.base import TrackingEngine
        tracker = get_tracker("precise")
        assert isinstance(tracker, TrackingEngine)

    def test_get_tracker_unknown_raises(self):
        from deepsight_host.tracking.registry import get_tracker
        with pytest.raises(ValueError, match="Unknown tracker"):
            get_tracker("nonexistent")

    def test_register_new_tracker(self):
        from deepsight_host.tracking.registry import (
            register_tracker,
            get_tracker,
            list_trackers,
        )
        from deepsight_host.tracking.fast_mode import FastModeTracker
        register_tracker("custom_test_fast", FastModeTracker)
        trackers = list_trackers()
        assert "custom_test_fast" in trackers
        t = get_tracker("custom_test_fast")
        from deepsight_host.tracking.base import TrackingEngine
        assert isinstance(t, TrackingEngine)

    def test_get_tracker_passes_kwargs(self):
        from deepsight_host.tracking.registry import get_tracker
        tracker = get_tracker("fast", confidence_threshold=0.99, inference_size=128)
        assert tracker._conf == 0.99
        assert tracker._inference_size == 128

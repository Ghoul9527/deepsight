import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
from PySide6.QtWidgets import QApplication
from deepsight_host.app import HostApp, GimbalMode
from deepsight_host.ui.tracking_view import TrackingViewWidget
from deepsight_shared.constants import SafetyState


def fake_host():
    app=HostApp.__new__(HostApp)
    app.config=SimpleNamespace(tracking_mode='fast')
    app._gimbal_mode=GimbalMode.MANUAL
    app._tracker=None
    app._window=Mock()
    app._framer=Mock()
    app._framer.safety_state=SafetyState.NOMINAL
    app._framer.current_angles=SimpleNamespace(pan=90,tilt=90)
    app._framer.process.return_value=app._framer.current_angles
    app._fps_ema=25.
    app._udp=Mock()
    app._schedule_async=Mock()
    app._pan_manual=app._tilt_manual=False
    return app


def test_manual_frame_never_calls_detector_or_framer_even_if_cached():
    app=fake_host()
    app._tracker=Mock()
    app._video_source=Mock()
    app._video_source.read.return_value=np.zeros((4,4,3),np.uint8)
    app._video_source.frame_age_ms.return_value=0
    app._last_brightness_update=time.monotonic()
    app._first_frame_seen=True
    app._frame_count=0
    app._last_fps_update=time.monotonic()
    app._pi_stream_latency_ms=0
    app._draw_overlay=Mock()
    app._recorder=Mock()
    app._send_servo=Mock()
    for _ in range(10):app._process_frame()
    app._tracker.process_frame.assert_not_called()
    app._framer.process.assert_not_called()
    app._recorder.record_tracking.assert_not_called()
    app._send_servo.assert_not_called()
    assert app._window.video_preview.update_frame.call_count==10


def test_rb_loads_on_enable_and_releases_on_disable():
    app=fake_host()
    tracker=Mock()
    app._load_tracker=Mock(return_value=tracker)
    app._on_tracking_toggle()
    assert app._gimbal_mode==GimbalMode.AUTO and app._tracker is tracker
    app._load_tracker.assert_called_once()
    app._window.tracking_view.set_tracking_active.assert_called_with(True)
    app._on_tracking_toggle()
    assert app._gimbal_mode==GimbalMode.MANUAL and app._tracker is None
    app._window.tracking_view.set_tracking_active.assert_called_with(False)


def test_model_failure_leaves_manual_controls_disabled():
    app=fake_host()
    app._load_tracker=Mock(side_effect=RuntimeError('failed'))
    app._on_tracking_toggle()
    assert app._tracker is None and app._gimbal_mode==GimbalMode.MANUAL
    app._udp.send.assert_not_called()


def test_manual_mode_change_does_not_load_model():
    app=fake_host()
    app._load_tracker=Mock()
    app._switch_tracking_mode('precise')
    assert app.config.tracking_mode=='precise'
    app._load_tracker.assert_not_called()


def test_stick_takeover_stops_tracking():
    for method in ['_on_gimbal_pitch','_on_gimbal_yaw']:
        app=fake_host();app._gimbal_mode=GimbalMode.AUTO;app._tracker=Mock()
        app._send_servo=Mock()
        getattr(app,method)(95)
        assert app._tracker is None and app._gimbal_mode==GimbalMode.MANUAL
        app._window.tracking_view.set_tracking_active.assert_called_with(False)


def test_tracking_controls_disabled_until_enabled():
    app=QApplication.instance() or QApplication([])
    widget=TrackingViewWidget()
    assert not widget._mode_combo.isEnabled() and not widget.reset_button.isEnabled()
    widget.set_tracking_active(True)
    assert widget._mode_combo.isEnabled() and widget.reset_button.isEnabled()
    widget.set_tracking_active(False)
    assert not widget._mode_combo.isEnabled()


def test_roll_trim_respects_default_physical_limit():
    app=SimpleNamespace(config=SimpleNamespace(gimbal_roll_max_angle=15),
                        _controller=Mock(),_send_servo=Mock())
    HostApp._on_roll_trim(app,180)
    app._send_servo.assert_called_with(2,105)
    assert app._controller._roll_angle==105
    HostApp._on_roll_trim(app,0)
    app._send_servo.assert_called_with(2,75)

"""Tests for the control layer: PID, servo mapper, framer, safety, controller."""

import math
import time

import pytest


# ---------------------------------------------------------------------------
# control.pid
# ---------------------------------------------------------------------------

class TestPIDGains:
    def test_default_gains(self):
        from deepsight_host.control.pid import PIDGains
        g = PIDGains()
        assert g.p == 0.8
        assert g.i == 0.05
        assert g.d == 0.2

    def test_custom_gains(self):
        from deepsight_host.control.pid import PIDGains
        g = PIDGains(p=1.5, i=0.1, d=0.5)
        assert g.p == 1.5
        assert g.i == 0.1
        assert g.d == 0.5


class TestPIDController:
    # --- Proportional term ---

    def test_proportional_response(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController()
        # With P=0.8, error=1.0, dt=0.1 -> output > 0 (P dominates)
        out = pid.update(1.0, 0.1)
        assert out > 0.0

    def test_output_is_zero_for_zero_error(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController()
        out = pid.update(0.0, 0.1)
        assert out == 0.0

    def test_output_sign_matches_error_sign(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController()
        assert pid.update(0.5, 0.1) > 0
        pid.reset()
        assert pid.update(-0.5, 0.1) < 0

    # --- Integral term ---

    def test_integral_accumulates_over_time(self):
        from deepsight_host.control.pid import PIDController
        from deepsight_host.control.pid import PIDGains
        # Use a pure-I controller to isolate integral behaviour
        pid = PIDController(gains=PIDGains(p=0.0, i=1.0, d=0.0))
        # error=1.0, dt=0.1 -> integral += 0.1, output = integral
        o1 = pid.update(1.0, 0.1)
        o2 = pid.update(1.0, 0.1)
        assert o2 > o1  # integral grows

    # --- Derivative term ---

    def test_derivative_damps_rapid_change(self):
        from deepsight_host.control.pid import PIDController
        from deepsight_host.control.pid import PIDGains
        pid = PIDController(gains=PIDGains(p=0.0, i=0.0, d=1.0))
        # First call: error jump from 0 to 1, derivative ≈ 1/0.1 = 10
        # but output is clamped so we just check sign / non-zero
        o1 = pid.update(1.0, 0.1)
        # Second call: same error -> derivative = 0
        o2 = pid.update(1.0, 0.1)
        # Output from derivative should drop significantly
        assert abs(o2) < abs(o1)

    # --- Output clamping ---

    def test_output_clamps_to_limit(self):
        from deepsight_host.control.pid import PIDController
        from deepsight_host.control.pid import PIDGains
        pid = PIDController(
            gains=PIDGains(p=100.0, i=100.0, d=100.0),
            output_limit=1.0,
        )
        out = pid.update(10.0, 0.1)
        assert abs(out) <= 1.0

    def test_custom_output_limit(self):
        from deepsight_host.control.pid import PIDController
        from deepsight_host.control.pid import PIDGains
        pid = PIDController(
            gains=PIDGains(p=100.0, i=0.0, d=0.0),
            output_limit=0.5,
        )
        out = pid.update(10.0, 0.1)
        assert abs(out) <= 0.5

    # --- Anti-windup ---

    def test_anti_windup_prevents_integral_runaway(self):
        from deepsight_host.control.pid import PIDController
        from deepsight_host.control.pid import PIDGains
        pid = PIDController(
            gains=PIDGains(p=5.0, i=10.0, d=0.0),
            output_limit=1.0,
        )
        # Run many updates at large error -> integral should be backed off
        for _ in range(100):
            pid.update(2.0, 0.1)
        # Integral should not have exploded (reasonable bound)
        assert abs(pid._integral) < 20.0

    # --- Dead zone ---

    def test_dead_zone_suppresses_small_errors(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController(dead_zone=0.1)
        out = pid.update(0.05, 0.1)
        assert out == 0.0

    def test_no_dead_zone_does_not_suppress(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController(dead_zone=0.0)
        out = pid.update(0.01, 0.1)
        assert out != 0.0

    # --- Reset ---

    def test_reset_clears_integral_and_prev_error(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController()
        pid.update(0.5, 0.1)
        pid.update(0.5, 0.1)
        assert pid._integral != 0.0
        pid.reset()
        assert pid._integral == 0.0
        assert pid._prev_error == 0.0
        assert pid._initialized is False

    # --- dt = 0 ---

    def test_zero_dt_handled_gracefully(self):
        from deepsight_host.control.pid import PIDController
        pid = PIDController()
        out = pid.update(0.3, 0.0)
        # Should not crash, output should be based on P and I only
        assert isinstance(out, float)


# ---------------------------------------------------------------------------
# control.servo_mapper
# ---------------------------------------------------------------------------

class TestServoAngles:
    def test_creation(self):
        from deepsight_host.control.servo_mapper import ServoAngles
        a = ServoAngles(pan=45.0, tilt=30.0)
        assert a.pan == 45.0
        assert a.tilt == 30.0


class TestServoMapper:
    def test_center_mapping_when_target_at_center(self, sample_tracking_result):
        from deepsight_host.control.servo_mapper import ServoMapper
        mapper = ServoMapper()
        # Modify result to be exactly centered
        from deepsight_host.tracking.base import TrackingResult
        centered = TrackingResult(
            bbox=(0.45, 0.45, 0.55, 0.55),
            center_x=0.5,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(centered)
        assert angles.pan == pytest.approx(90.0)
        assert angles.tilt == pytest.approx(90.0)

    def test_target_right_of_center_moves_pan_right(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper()
        right_target = TrackingResult(
            bbox=(0.55, 0.45, 0.65, 0.55),
            center_x=0.6,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(right_target)
        assert angles.pan > 90.0

    def test_target_left_of_center_moves_pan_left(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper()
        left_target = TrackingResult(
            bbox=(0.25, 0.45, 0.35, 0.55),
            center_x=0.3,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(left_target)
        assert angles.pan < 90.0

    def test_target_above_center_moves_tilt(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper()
        above_target = TrackingResult(
            bbox=(0.45, 0.25, 0.55, 0.35),
            center_x=0.5,
            center_y=0.3,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(above_target)
        # center_y < 0.5 -> error_y negative -> tilt < 90.0
        assert angles.tilt < 90.0

    def test_pan_angle_clamped_to_range(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper(pan_center=90.0, pan_range=30.0)
        far_right = TrackingResult(
            bbox=(0.95, 0.45, 0.99, 0.55),
            center_x=0.97,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(far_right)
        assert angles.pan <= 120.0  # 90 + 30
        assert angles.pan >= 60.0   # 90 - 30

    def test_tilt_angle_clamped_to_range(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper(tilt_center=90.0, tilt_range=20.0)
        far_top = TrackingResult(
            bbox=(0.45, 0.01, 0.55, 0.05),
            center_x=0.5,
            center_y=0.03,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(far_top)
        assert angles.tilt >= 70.0   # 90 - 20
        assert angles.tilt <= 110.0  # 90 + 20

    def test_lost_target_returns_center(self, lost_tracking_result):
        from deepsight_host.control.servo_mapper import ServoMapper
        mapper = ServoMapper(pan_center=90.0, tilt_center=90.0)
        angles = mapper.tracking_to_servo(lost_tracking_result)
        assert angles.pan == 90.0
        assert angles.tilt == 90.0

    def test_invert_pan(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper_no_inv = ServoMapper(invert_pan=False)
        mapper_inv = ServoMapper(invert_pan=True)
        right_target = TrackingResult(
            bbox=(0.55, 0.45, 0.65, 0.55),
            center_x=0.6,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        normal = mapper_no_inv.tracking_to_servo(right_target)
        inverted = mapper_inv.tracking_to_servo(right_target)
        # Normal: pan > 90; Inverted: pan < 90
        assert (normal.pan - 90.0) * (inverted.pan - 90.0) < 0

    def test_invert_tilt(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper_no_inv = ServoMapper(invert_tilt=False)
        mapper_inv = ServoMapper(invert_tilt=True)
        below_target = TrackingResult(
            bbox=(0.45, 0.55, 0.55, 0.65),
            center_x=0.5,
            center_y=0.6,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        normal = mapper_no_inv.tracking_to_servo(below_target)
        inverted = mapper_inv.tracking_to_servo(below_target)
        assert (normal.tilt - 90.0) * (inverted.tilt - 90.0) < 0

    def test_custom_center_and_range(self):
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper(pan_center=100.0, tilt_center=80.0,
                             pan_range=30.0, tilt_range=20.0)
        centered = TrackingResult(
            bbox=(0.45, 0.45, 0.55, 0.55),
            center_x=0.5,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = mapper.tracking_to_servo(centered)
        assert angles.pan == pytest.approx(100.0)
        assert angles.tilt == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# control.framer
# ---------------------------------------------------------------------------

class TestFramer:
    def test_initial_angles_are_center(self):
        from deepsight_host.control.framer import Framer
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.control.pid import PIDController
        mapper = ServoMapper()
        framer = Framer(mapper, PIDController(), PIDController())
        assert framer.current_angles.pan == 90.0
        assert framer.current_angles.tilt == 90.0

    def test_process_visible_target_updates_angles(self):
        from deepsight_host.control.framer import Framer
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.control.pid import PIDController
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper()
        framer = Framer(mapper, PIDController(), PIDController())
        visible = TrackingResult(
            bbox=(0.55, 0.45, 0.65, 0.55),
            center_x=0.6,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        angles = framer.process(visible)
        assert isinstance(angles.pan, float)
        assert isinstance(angles.tilt, float)

    def test_process_lost_target_maintains_safety(self, lost_tracking_result):
        from deepsight_host.control.framer import Framer
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.control.pid import PIDController
        mapper = ServoMapper()
        framer = Framer(mapper, PIDController(), PIDController())
        angles = framer.process(lost_tracking_result)
        # Should still produce valid angles
        assert 0.0 <= angles.pan <= 180.0
        assert 0.0 <= angles.tilt <= 180.0

    def test_reset_returns_to_center(self):
        from deepsight_host.control.framer import Framer
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.control.pid import PIDController
        from deepsight_host.tracking.base import TrackingResult
        mapper = ServoMapper()
        framer = Framer(mapper, PIDController(), PIDController())
        target = TrackingResult(
            bbox=(0.55, 0.45, 0.65, 0.55),
            center_x=0.6,
            center_y=0.5,
            confidence=0.9,
            track_id=1,
            visible=True,
            lost=False,
        )
        framer.process(target)
        framer.reset()
        assert framer.current_angles.pan == 90.0
        assert framer.current_angles.tilt == 90.0

    def test_can_accept_external_kalman_and_smoother(self):
        from deepsight_host.control.framer import Framer
        from deepsight_host.control.servo_mapper import ServoMapper
        from deepsight_host.control.pid import PIDController
        from deepsight_host.tracking.kalman import KalmanPredictor
        from deepsight_host.tracking.smoother import EMASmoother
        kf = KalmanPredictor(dt=1.0 / 25.0)
        ema = EMASmoother(alpha=0.5)
        framer = Framer(
            ServoMapper(), PIDController(), PIDController(),
            kalman=kf, smoother=ema,
        )
        assert framer._kalman is kf
        assert framer._smoother is ema


# ---------------------------------------------------------------------------
# control.safety
# ---------------------------------------------------------------------------

class TestSafetyMonitor:
    def test_initial_state_is_nominal(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor()
        assert sm.state == SafetyState.NOMINAL

    def test_report_found_resets_lost_duration(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor()
        sm.report_lost(1.0)
        sm.report_found()
        assert sm._lost_duration == 0.0
        assert sm.state == SafetyState.NOMINAL

    def test_no_override_when_nominal(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        sm = SafetyMonitor()
        target = ServoAngles(pan=95.0, tilt=90.0)
        current = ServoAngles(pan=90.0, tilt=90.0)
        override = sm.check(target, current, 0.033)
        assert override is None

    def test_degraded_after_hold_timeout(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor(lost_hold_time=0.1, lost_neutral_time=1.0)
        # Simulate time passing while lost
        sm.report_lost(0.15)
        target = ServoAngles(pan=100.0, tilt=100.0)
        current = ServoAngles(pan=90.0, tilt=90.0)
        override = sm.check(target, current, 0.033)
        assert override is not None
        assert sm.state == SafetyState.DEGRADED
        # In DEGRADED, should hold position (return current)
        assert override.pan == current.pan
        assert override.tilt == current.tilt

    def test_caution_after_neutral_timeout(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor(lost_hold_time=0.1, lost_neutral_time=0.3)
        sm.report_lost(0.5)
        target = ServoAngles(pan=100.0, tilt=100.0)
        current = ServoAngles(pan=95.0, tilt=95.0)
        override = sm.check(target, current, 0.033)
        assert override is not None
        assert sm.state == SafetyState.CAUTION
        # CAUTION: moving toward neutral (90, 90)
        assert abs(override.pan - 90.0) < abs(current.pan - 90.0)

    def test_recover_to_nominal_when_visible(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor(lost_hold_time=0.1, lost_neutral_time=1.0)
        # Push into DEGRADED via check()
        sm.report_lost(0.2)
        sm.check(ServoAngles(pan=100.0, tilt=100.0),
                 ServoAngles(pan=90.0, tilt=90.0), 0.033)
        assert sm.state == SafetyState.DEGRADED
        # report_found resets to NOMINAL
        sm.report_found()
        assert sm.state == SafetyState.NOMINAL

    def test_sudden_angle_jump_clamped(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        sm = SafetyMonitor(max_angle_step=5.0)
        target = ServoAngles(pan=150.0, tilt=90.0)  # huge jump
        current = ServoAngles(pan=90.0, tilt=90.0)
        override = sm.check(target, current, 0.033)
        assert override is not None
        # Should be clamped to max_angle_step
        assert abs(override.pan - current.pan) <= sm.max_angle_step + 1e-6

    def test_reset_clears_state(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        from deepsight_shared.constants import SafetyState
        sm = SafetyMonitor(lost_hold_time=0.1, lost_neutral_time=0.3)
        # Push into CAUTION via check()
        sm.report_lost(1.0)
        sm.check(ServoAngles(pan=100.0, tilt=100.0),
                 ServoAngles(pan=90.0, tilt=90.0), 0.033)
        assert sm.state != SafetyState.NOMINAL
        sm.reset()
        assert sm.state == SafetyState.NOMINAL

    def test_custom_neutral_angles(self):
        from deepsight_host.control.safety import SafetyMonitor
        from deepsight_host.control.servo_mapper import ServoAngles
        sm = SafetyMonitor(
            lost_hold_time=0.1,
            lost_neutral_time=0.3,
            neutral_pan=80.0,
            neutral_tilt=70.0,
        )
        sm.report_lost(0.5)
        current = ServoAngles(pan=90.0, tilt=90.0)
        target = ServoAngles(pan=100.0, tilt=100.0)
        override = sm.check(target, current, 0.033)
        # Moving toward custom neutral
        assert abs(override.pan - 80.0) < abs(current.pan - 80.0)
        assert abs(override.tilt - 70.0) < abs(current.tilt - 70.0)


# ---------------------------------------------------------------------------
# control.controller
# ---------------------------------------------------------------------------

class TestGameControllerSignals:
    """Verify that the signal definitions exist without requiring pygame."""

    def test_signal_definitions_exist(self):
        from deepsight_host.control.controller import GameController
        assert hasattr(GameController, 'pan_changed')
        assert hasattr(GameController, 'tilt_changed')
        assert hasattr(GameController, 'winch_speed_changed')
        assert hasattr(GameController, 'e_stop')
        assert hasattr(GameController, 'tracking_toggle')

    def test_controller_connects_to_signals(self):
        from deepsight_host.control.controller import GameController
        from PySide6.QtCore import QObject, Signal
        # Create a dummy parent -- no QApplication needed for signal/slot meta-object
        parent = QObject()
        gc = GameController(parent=parent)
        assert gc.connected is False
        assert isinstance(gc.pan_changed, Signal)
        assert isinstance(gc.tilt_changed, Signal)
        assert isinstance(gc.winch_speed_changed, Signal)
        assert isinstance(gc.e_stop, Signal)
        assert isinstance(gc.tracking_toggle, Signal)

    def test_discover_controller_returns_none_without_pygame(self):
        from deepsight_host.control.controller import discover_controller
        result = discover_controller()
        assert result is None

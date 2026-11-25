from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication
from deepsight_host.servo_tester import ServoTester,pulse_for_angle


@pytest.mark.parametrize('angle,pulse',[(0,1000),(90,1500),(180,2000),(-5,1000),(200,2000)])
def test_angle_conversion(angle,pulse):
    assert pulse_for_angle(angle)==pulse


def test_invalid_pulse_range():
    with pytest.raises(ValueError):pulse_for_angle(90,2000,1000)
    with pytest.raises(ValueError):pulse_for_angle(90,400,2500)


def widget():
    app=QApplication.instance() or QApplication([])
    w=ServoTester();w._app_ref=app;w.send=Mock()
    return w


def test_startup_has_no_output_and_requires_explicit_enable():
    w=widget()
    assert not w.ready and not w.enabled.isChecked()
    w.angle.setValue(100);w.flush()
    w.send.assert_not_called()
    w.ready=True;w.controls.setEnabled(True);w.enabled.setChecked(True)
    w.send.assert_called_once_with('set',channel=0,pulse_us=1556)
    w.timer.stop();w.keepalive.stop()


def test_switching_channel_stops_output_and_requires_reenable():
    w=widget();w.ready=True;w.controls.setEnabled(True)
    w.enabled.setChecked(True);w.send.reset_mock()
    w.selector.setCurrentIndex(3)
    assert not w.enabled.isChecked() and w.pulse.value()==1500
    assert w.send.call_args.args==('off',)
    assert all(call.args[0]=='off' for call in w.send.call_args_list)
    w.timer.stop();w.keepalive.stop()


def test_stop_clears_pending_changes():
    w=widget();w.ready=True;w.controls.setEnabled(True)
    w.enabled.setChecked(True);w.pulse.setValue(1600)
    w.stop_outputs();w.send.reset_mock();w.flush();w.repeat_output();w.flush()
    w.send.assert_not_called()
    assert w.pending is None
    w.timer.stop();w.keepalive.stop()


def test_all_option_requires_enable_then_sends_all():
    w=widget();w.ready=True;w.controls.setEnabled(True)
    w.selector.setCurrentIndex(5)
    assert w.selector.currentData()=='all' and not w.enabled.isChecked()
    w.send.reset_mock();w.enabled.setChecked(True)
    w.send.assert_called_once_with('set',channel='all',pulse_us=1500)
    w.timer.stop();w.keepalive.stop()

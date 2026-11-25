from unittest.mock import Mock,patch
import pytest
from deepsight_pi.servo_calibration import calibrated_pulse,DEFAULT_CALIBRATION
from deepsight_pi.servo_controller import ServoController

@pytest.mark.parametrize('angle,limit,expected',[(90,15,1500),(105,15,1585.7142857),(75,15,1414.2857143),(135,45,1757.142857),(45,45,1242.857143),(180,15,1585.7142857),(0,45,1242.857143)])
def test_physical_degrees_and_clamping(angle,limit,expected):
    assert calibrated_pulse(angle,DEFAULT_CALIBRATION,limit)==pytest.approx(expected)


def test_full_calibration_endpoints():
    assert calibrated_pulse(-85,DEFAULT_CALIBRATION,175)==500
    assert calibrated_pulse(265,DEFAULT_CALIBRATION,175)==2500


def test_driver_applies_defaults_for_all_five_channels():
    with patch('deepsight_pi.servo_controller.PCA9685') as factory:
        s=ServoController({'servos':[{'id':sid,'channel':sid} for sid in range(5)]})
        for sid in range(5):
            s.set_angle(sid,180)
            expected=1585.7142857 if sid<3 else 1757.142857
            assert factory.return_value.set_pwm.call_args.args[1]==pytest.approx(expected)


def test_invalid_command_is_rejected_before_write():
    with pytest.raises(ValueError):calibrated_pulse(float('nan'),{},15)
    with pytest.raises(ValueError):calibrated_pulse(90,{},180)

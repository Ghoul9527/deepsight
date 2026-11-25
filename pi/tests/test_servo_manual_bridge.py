import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest
spec=importlib.util.spec_from_file_location('servo_bridge',Path(__file__).resolve().parents[2]/'scripts/servo_manual_bridge.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def fake_pca():
    p=Mock();p._period_us=20000.;p._addr=64
    states={}
    def write(ch,pulse):
        count=int(4096/20000*pulse);states[6+4*ch]=[0,0,count&255,count>>8]
    p.set_pwm.side_effect=write
    p._bus.read_i2c_block_data.side_effect=lambda addr,reg,n:states[reg]
    return p


def test_all_drives_only_five_servo_channels_and_reads_each():
    p=fake_pca()
    result=module.apply_servo_command(p,set(range(5)),'all',1500)
    assert set(result)=={'0','1','2','3','4'}
    assert [c.args[0] for c in p.set_pwm.call_args_list]==[0,1,2,3,4]
    p.set_duty_cycle.assert_not_called()
    assert all(value==pytest.approx(1499.0,abs=1) for value in result.values())


def test_single_channel_turns_other_servos_off():
    p=fake_pca()
    result=module.apply_servo_command(p,set(range(5)),2,1000)
    assert set(result)=={'2'}
    assert [c.args[0] for c in p.set_duty_cycle.call_args_list]==[0,1,3,4]


def test_rejects_invalid_channel_before_writing():
    p=fake_pca()
    with pytest.raises(ValueError):module.apply_servo_command(p,set(range(5)),5,1500)
    p.set_pwm.assert_not_called();p.set_duty_cycle.assert_not_called()

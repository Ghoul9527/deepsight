from unittest.mock import Mock
import pytest
from deepsight_pi.hardware.pca9685 import PCA9685


@pytest.mark.parametrize('fraction,registers,percent',[(0,[0,0,0,16],0),(1,[0,16,0,0],100),(.5,[0,0,0,8],50)])
def test_lighting_endpoints_and_duty(fraction,registers,percent):
    p=PCA9685.__new__(PCA9685)
    p._bus=Mock();p._addr=0x40
    assert p.set_duty_cycle(5,fraction)==percent
    p._bus.write_i2c_block_data.assert_called_once_with(0x40,26,registers)

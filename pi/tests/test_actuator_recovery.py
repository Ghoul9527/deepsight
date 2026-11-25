import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from deepsight_pi.bridge.message_router import MessageRouter
from deepsight_pi.servo_controller import ServoController
from deepsight_shared.protocol import new_message


def make_router():
    with patch('deepsight_pi.servo_controller.ServoController', side_effect=OSError('disconnected')):
        r=MessageRouter(Mock(send=AsyncMock()),Mock(),Mock(),
            servo_config={'pca9685':{'i2c_bus':1}})
    r._actuator_retry_s=.005
    r._running=True
    return r


def test_two_good_probes_clear_fault_and_drop_commands(caplog):
    async def scenario():
        r=make_router()
        r._probe_actuator=Mock()
        def restore():
            assert r._probe_actuator.call_count==2
            r._running=False
        r._restore_actuator=Mock(side_effect=restore)
        r._servo_buf[0]=new_message('host','cmd.servo.set',{'angle':150})
        r._lighting_buf=Mock()
        await asyncio.wait_for(r._recover_actuator(),.5)
        assert r._actuator_fault is None and not r._servo_buf and r._lighting_buf is None
        assert 'PCA9685 recovered' in caplog.text
    caplog.set_level(logging.INFO)
    asyncio.run(scenario())


def test_intermittent_probe_does_not_clear_fault():
    async def scenario():
        r=make_router()
        calls=0
        def probe():
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('loose contact')
            if calls==4:r._running=False
        r._probe_actuator=Mock(side_effect=probe)
        r._restore_actuator=Mock()
        await asyncio.wait_for(r._recover_actuator(),.5)
        # success, failure, success, success -> recovery only on fourth probe
        r._restore_actuator.assert_called_once()
        assert calls==4 and r._actuator_fault is None
    asyncio.run(scenario())


def test_initialization_failure_keeps_fault_until_success():
    async def scenario():
        r=make_router()
        r._probe_actuator=Mock()
        calls=0
        def restore():
            nonlocal calls
            calls+=1
            if calls==1:raise OSError('write still failing')
            assert r._actuator_fault is not None
            r._running=False
        r._restore_actuator=Mock(side_effect=restore)
        await asyncio.wait_for(r._recover_actuator(),.5)
        assert calls==2 and r._probe_actuator.call_count==4 and r._actuator_fault is None
    asyncio.run(scenario())


def test_recovery_reinitializes_neutral_and_light_off():
    servo=ServoController.__new__(ServoController)
    servo._pca=Mock();servo._pca._freq=50
    servo._servo_channels={0:{},1:{}}
    servo._light_channels={0:{}}
    servo._default_angle=90
    servo.set_angle=Mock();servo.set_brightness=Mock()
    servo.recover()
    servo._pca.set_pwm_freq.assert_called_once_with(50)
    assert servo.set_angle.call_args_list[0].args==(0,90)
    assert servo.set_angle.call_args_list[1].args==(1,90)
    servo.set_brightness.assert_called_once_with(0,0.0)


def test_faulted_commands_are_not_queued_for_replay():
    async def scenario():
        r=make_router()
        await r._handle_message(new_message('host','cmd.servo.set',{'servo_id':0,'angle':150}))
        await r._handle_message(new_message('host','cmd.light',{'brightness':1}))
        assert not r._servo_buf and r._lighting_buf is None
        r._running=False
    asyncio.run(scenario())

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from deepsight_pi.bridge.message_router import MessageRouter
from deepsight_shared.protocol import new_message


def make_router():
    host=Mock(send=AsyncMock(),recv_queue=asyncio.Queue())
    pico=Mock(send=AsyncMock(),recv_queue=asyncio.Queue())
    stm=Mock(send=AsyncMock(),recv_queue=asyncio.Queue())
    return MessageRouter(host,pico,stm),host,pico


def test_servo_error_does_not_stop_sensor_translation():
    async def scenario():
        router,host,pico=make_router()
        router._stabilizer=Mock()
        router._stabilizer.step.side_effect=OSError(121,'I2C failed')
        message=new_message('pico','t',{'r':12,'d':.3,'pr':1020,'le':[True]})
        await router._translate_compact(message)
        assert router._actuator_fault is not None
        types=[c.args[0].type for c in host.send.call_args_list]
        assert 'tel.imu' in types and 'tel.depth' in types and types.count('tel.leak')==4
        await router._translate_compact(message)
        router._stabilizer.step.assert_called_once()  # fault latched, no repeated actuator writes
        await router._handle_message(new_message('host','cmd.servo.set',{'servo_id':0,'angle':120}))
        assert not router._servo_buf
        pico.send.assert_not_called()  # no unintended fallback to Pico
    asyncio.run(scenario())


def test_failed_initialization_keeps_gateway_available():
    with patch('deepsight_pi.servo_controller.ServoController',side_effect=OSError(121,'absent')):
        router=MessageRouter(Mock(),Mock(),Mock(),servo_config={'pca9685':{}},
                             stabilizer_config={'roll':{'enabled':True}})
        # Empty PCA config is deliberately disabled by existing configuration semantics.
        router=MessageRouter(Mock(),Mock(),Mock(),servo_config={'pca9685':{'i2c_bus':1}},
                             stabilizer_config={'roll':{'enabled':True}})
    assert router._actuator_fault and router._stabilizer is None


def test_telemetry_heartbeat_continues_after_write_fault():
    async def scenario():
        router,host,pico=make_router()
        router._stabilizer=Mock(step=Mock(side_effect=OSError(121,'absent')))
        await pico.recv_queue.put(new_message('pico','t',{'r':2,'le':[False]}))
        async def send(message):
            if message.type=='sys.heartbeat' and message.node_id=='pi':router._running=False
        host.send.side_effect=send
        router._running=True
        await asyncio.wait_for(router._generate_telemetry(),1)
        msgs=[c.args[0] for c in host.send.call_args_list]
        assert any(m.type=='sys.heartbeat' and m.node_id=='pico' for m in msgs)
        status=next(m for m in msgs if m.type=='tel.pi_status')
        assert status.payload['actuator_ok'] is False
    asyncio.run(scenario())

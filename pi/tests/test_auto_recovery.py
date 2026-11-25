import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.hardware.gopro_recovery import Recovery
from deepsight_shared.protocol import tel_leak


def test_pico_absent_then_connect_and_eof_reconnect():
    async def scenario():
        cfg=SimpleNamespace(pico_port='usb',pico_telemetry_port='usb',pico_baud=115200,reconnect_delay_s=.1)
        writer1=Mock(wait_closed=AsyncMock(),drain=AsyncMock())
        writer2=Mock(wait_closed=AsyncMock(),drain=AsyncMock())
        first=Mock(readline=AsyncMock(side_effect=[tel_leak('pico',0,True).to_bytes()+b'\n',b'']))
        next_reader=asyncio.StreamReader()
        opener=AsyncMock(side_effect=[OSError('absent'),(first,writer1),(next_reader,writer2)])
        link=PicoLink(cfg)
        with patch('deepsight_pi.bridge.pico_link.open_serial_connection',opener):
            await link.start()
            msg=await asyncio.wait_for(link.recv_queue.get(),1)
            assert msg.payload['wet'] is True
            for _ in range(30):
                if opener.await_count>=3:break
                await asyncio.sleep(.02)
            assert opener.await_count==3
            writer1.close.assert_called()
            await link.stop()
            writer2.close.assert_called()
            assert link._recv_task is None and link._cmd_writer is None
    asyncio.run(scenario())


def test_pico_send_failure_drops_stale_handle():
    async def scenario():
        link=PicoLink(SimpleNamespace(pico_port='usb',pico_telemetry_port='usb',pico_baud=115200,reconnect_delay_s=.1))
        writer=Mock(drain=AsyncMock(side_effect=OSError('unplug')))
        link._cmd_writer=writer
        await link.send(tel_leak('host',0,False))
        writer.close.assert_called_once()
        assert link._cmd_writer is None
    asyncio.run(scenario())


def test_recovery_threshold_cooldown_identity_and_budget(tmp_path):
    async def scenario():
        device=tmp_path/'camera';(device/'interface/net/eth1').mkdir(parents=True)
        (device/'busnum').write_text('2');(device/'devnum').write_text('7')
        worker=Recovery('172.22.121.51',tmp_path/'state.json',cooldown_s=120,max_resets=3)
        worker.command=AsyncMock(return_value=True)
        with patch('deepsight_pi.hardware.gopro_recovery.camera_device',return_value=device):
            await worker.step(False,now=0,wall=10000)
            await worker.step(False,now=5,wall=10005)
            worker.command.assert_not_called()
            await worker.step(False,now=10,wall=10010)
            assert worker.command.call_args.args==('/usr/bin/nmcli','device','reapply','eth1')
            await worker.step(False,now=20,wall=10020)
            assert worker.command.await_count==1
            await worker.step(False,now=130,wall=10130)
            assert worker.command.call_args.args[-1]=='/dev/bus/usb/002/007'
            await worker.step(False,now=250,wall=10250)
            await worker.step(False,now=370,wall=10370)
            assert len(worker.resets)==3
            await worker.step(False,now=490,wall=10490)
            assert worker.command.await_count==4  # network plus three device-only resets
            assert len(Recovery(worker.ip,tmp_path/'state.json').resets)==3
            await worker.step(True,now=500,wall=10500)
            assert worker.failures==0 and not worker.network_tried
    asyncio.run(scenario())


def test_absent_camera_never_resets_hub(tmp_path):
    async def scenario():
        worker=Recovery('camera',tmp_path/'state.json');worker.command=AsyncMock()
        with patch('deepsight_pi.hardware.gopro_recovery.camera_device',return_value=None):
            for i in range(5):await worker.step(False,now=i*130,wall=10000+i*130)
        worker.command.assert_not_called()
    asyncio.run(scenario())


def test_small_error_threshold_baseline_and_cooldown(tmp_path):
    async def scenario():
        device=tmp_path/'camera';interface=device/'iface/net/eth1'
        (interface/'statistics').mkdir(parents=True)
        (interface/'ifindex').write_text('5')
        (device/'busnum').write_text('4');(device/'devnum').write_text('16')
        def counters(rx,tx):
            (interface/'statistics/rx_errors').write_text(str(rx))
            (interface/'statistics/tx_errors').write_text(str(tx))
        worker=Recovery('camera',tmp_path/'state.json',cooldown_s=30)
        worker.command=AsyncMock(return_value=True)
        with patch('deepsight_pi.hardware.gopro_recovery.camera_device',return_value=device):
            counters(1000,100)
            await worker.check_errors()  # historical errors alone must not reset
            counters(1007,100)
            await worker.check_errors()
            worker.command.assert_not_called()
            counters(1007,101)
            await worker.check_errors()
            assert worker.command.await_count==1
            assert worker.command.call_args.args[-1]=='/dev/bus/usb/004/016'
            assert 'nmcli' not in worker.command.call_args.args[0]
            counters(0,0)
            await worker.check_errors()
            counters(50,0)
            await worker.check_errors()
            assert worker.command.await_count==1  # still inside cooldown
            worker.last_action-=31
            await worker.check_errors()
            assert worker.command.await_count==2
    asyncio.run(scenario())


def test_counter_reset_and_device_identity_do_not_trigger(tmp_path):
    async def scenario():
        device=tmp_path/'camera';interface=device/'iface/net/eth1'
        (interface/'statistics').mkdir(parents=True)
        (interface/'ifindex').write_text('7')
        (interface/'statistics/rx_errors').write_text('100')
        (interface/'statistics/tx_errors').write_text('0')
        worker=Recovery('camera',tmp_path/'state.json');worker.command=AsyncMock()
        with patch('deepsight_pi.hardware.gopro_recovery.camera_device',return_value=device):
            await worker.check_errors()
            (interface/'statistics/rx_errors').write_text('0')
            await worker.check_errors()
            (interface/'ifindex').write_text('8')
            (interface/'statistics/rx_errors').write_text('500')
            await worker.check_errors()
        worker.command.assert_not_called()
    asyncio.run(scenario())


def test_default_recovery_has_no_cooldown_or_hourly_limit(tmp_path):
    async def scenario():
        device=tmp_path/'camera';(device/'interface/net/eth1').mkdir(parents=True)
        (device/'busnum').write_text('4');(device/'devnum').write_text('16')
        worker=Recovery('camera',tmp_path/'state.json')
        worker.command=AsyncMock(return_value=True)
        worker.resets=[10000]*20
        assert worker.cooldown_s==0 and worker.max_resets is None
        with patch('deepsight_pi.hardware.gopro_recovery.camera_device',return_value=device):
            await worker.step(False,now=1,wall=10001,error_trigger=True)
            await worker.step(False,now=1.1,wall=10001.1,error_trigger=True)
        assert worker.command.await_count==2
        assert len(worker.resets)==22
    asyncio.run(scenario())

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from deepsight_pi.bridge.message_router import MessageRouter
from deepsight_shared.protocol import new_message


def make_router():
    host = Mock(send=AsyncMock(), recv_queue=asyncio.Queue())
    pico = Mock(send=AsyncMock(), recv_queue=asyncio.Queue())
    stm = Mock(send=AsyncMock(), recv_queue=asyncio.Queue())
    router = MessageRouter(host, pico, stm)
    router._telemetry_retry_s = .005
    router._telemetry_check_s = .005
    router._telemetry_stall_s = .03
    router._running = True
    return router, host, pico


def test_send_failure_restarts_real_telemetry_and_logs_recovery(caplog):
    async def scenario():
        router, host, pico = make_router()
        router._telemetry_stall_s = .5
        await pico.recv_queue.put(new_message('pico', 't', {'r': 1}))
        host.send.side_effect = [OSError('network unreachable')] + [None] * 100
        task = asyncio.create_task(router._supervise_telemetry())
        try:
            for _ in range(100):
                if 'Telemetry recovered' in caplog.text:
                    break
                await asyncio.sleep(.01)
            assert router._telemetry_restarts == 1
            assert any(c.args[0].type == 'sys.heartbeat' and c.args[0].node_id == 'pi'
                       for c in host.send.call_args_list)
            assert 'network unreachable' in caplog.text
            assert 'Telemetry recovered' in caplog.text
        finally:
            router._running = False
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    caplog.set_level(logging.INFO)
    asyncio.run(scenario())


def test_stalled_worker_is_cancelled_and_replaced(caplog):
    async def scenario():
        router, _, _ = make_router()
        starts = 0
        cancelled = asyncio.Event()
        recovered = asyncio.Event()
        async def worker():
            nonlocal starts
            starts += 1
            if starts == 1:
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            else:
                recovered.set()
                router._running = False
        router._generate_telemetry = worker
        await asyncio.wait_for(router._supervise_telemetry(), .5)
        assert cancelled.is_set() and recovered.is_set()
        assert starts == 2 and router._telemetry_restarts == 1
        assert 'no progress' in caplog.text
    asyncio.run(scenario())


def test_unexpected_normal_exit_is_restarted():
    async def scenario():
        router, _, _ = make_router()
        starts = 0
        async def worker():
            nonlocal starts
            starts += 1
            if starts == 2:
                router._running = False
        router._generate_telemetry = worker
        await asyncio.wait_for(router._supervise_telemetry(), .5)
        assert starts == 2 and router._telemetry_restarts == 1
    asyncio.run(scenario())


def test_shutdown_cancels_worker_without_restart(caplog):
    async def scenario():
        router, _, _ = make_router()
        cancelled = asyncio.Event()
        started = asyncio.Event()
        async def worker():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        router._generate_telemetry = worker
        task = asyncio.create_task(router._supervise_telemetry())
        router._tasks = [task]
        await started.wait()
        await router.stop()
        assert cancelled.is_set() and task.done()
        assert router._telemetry_restarts == 0
    asyncio.run(scenario())


def test_sensor_backlog_does_not_starve_pi_heartbeat():
    async def scenario():
        router, host, pico = make_router()
        for _ in range(150):
            await pico.recv_queue.put(new_message('pico', 'tel.depth', {'depth_m': 0}))
        async def send(msg):
            if msg.type == 'sys.heartbeat' and msg.node_id == 'pi':
                router._running = False
        host.send.side_effect = send
        await asyncio.wait_for(router._generate_telemetry(), .5)
        assert pico.recv_queue.qsize() == 50
        assert router._telemetry_last_progress > 0
    asyncio.run(scenario())

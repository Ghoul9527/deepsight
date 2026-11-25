import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import pytest
from deepsight_host.app import HostApp
from deepsight_host.video.stream_receiver import StreamReceiver

@pytest.mark.parametrize('start_ok,loops,expected_starts', [(False,2,2),(True,2,2)])
def test_failed_start_or_stale_video_retries(start_ok,loops,expected_starts):
    async def scenario():
        camera=SimpleNamespace(enable_wired_usb=AsyncMock(),claim_control=AsyncMock(),
            ensure_video_mode=AsyncMock(return_value=True),start_viewfinder=AsyncMock(return_value=start_ok))
        video=Mock(spec=StreamReceiver);video.stale.return_value=True
        app=SimpleNamespace(_running=True,_gopro_online=True,_gopro=camera,
                            _gopro_compatibility_checked=True,_video_source=video,
                            _fetch_presets=AsyncMock())
        ticks=0
        async def tick(_):
            nonlocal ticks
            ticks+=1
            if ticks>=loops:app._running=False
        with patch('deepsight_host.app.asyncio.sleep',side_effect=tick):
            await HostApp._manage_gopro_lifecycle(app)
        assert camera.start_viewfinder.await_count==expected_starts
    asyncio.run(scenario())

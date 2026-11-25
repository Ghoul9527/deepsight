from __future__ import annotations

import asyncio

import httpx

from deepsight_host.gopro.client import GoProClient
from deepsight_host.gopro.profile import firmware_version_tuple
from deepsight_host.gopro.settings_decode import decode_setting, preset_aspect_ratio
from deepsight_host.ui.gopro_control_dialog import _MODE_TABS, _pick_probe_option


def _mission_presets() -> dict:
    return {
        "activePresetId": 501,
        "presetGroupArray": [
            {
                "id": "PRESET_GROUP_ID_GENERAL",
                "presetArray": [
                    {
                        "id": 501,
                        "titleId": 10,
                        "mode": "FLAT_MODE_VIDEO",
                        "isVisible": 1,
                        "settingArray": [
                            {"id": 2, "value": 1},
                            {"id": 3, "value": 5},
                            {"id": 108, "value": 1},
                            {"id": 256, "value": 0},
                        ],
                    },
                    {"id": 502, "titleId": 3, "mode": 17, "settingArray": []},
                    {"id": 503, "titleId": 8, "mode": 13, "settingArray": []},
                ],
            }
        ],
    }


def test_firmware_version_handles_prefixed_camera_version():
    assert firmware_version_tuple("M1.01.02.02.70") == (2, 2, 70)


def test_normalize_mission_general_presets():
    presets, active = GoProClient.normalize_presets(_mission_presets())

    assert active == 501
    assert [preset["title"] for preset in presets] == ["Video", "Photo", "Time Lapse"]
    assert presets[0]["summary"] == "Dive · 4K · 60 · 16:9"
    assert preset_aspect_ratio(presets[0]["setting_array"]) == (16, 9)


def test_mission_setting_enums_are_current():
    assert decode_setting(3, 5) == "60"
    assert decode_setting(256, 0) == "Dive"
    assert decode_setting(257, 1) == "On"


def test_control_surface_is_video_only_and_uses_safe_probe_sentinel():
    assert [mode for mode, _label, _settings in _MODE_TABS] == ["video", "other"]
    assert _pick_probe_option(239, "12") == "65535"


def test_capture_mode_loads_dynamic_general_preset():
    asyncio.run(_test_capture_mode_loads_dynamic_general_preset())


async def _test_capture_mode_loads_dynamic_general_preset():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/gopro/camera/presets/get":
            return httpx.Response(200, json=_mission_presets())
        if request.url.path == "/gopro/camera/presets/load":
            return httpx.Response(200)
        return httpx.Response(404)

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await client.set_capture_mode("photo")
    finally:
        await client.close()

    assert requests[0].url.params["include-hidden"] == "1"
    assert requests[1].url.params["id"] == "502"


def test_compatibility_reads_mission_capabilities():
    asyncio.run(_test_compatibility_reads_mission_capabilities())


async def _test_compatibility_reads_mission_capabilities():
    responses = {
        "/gopro/camera/info": {
            "model_name": "MISSION 1 PRO",
            "firmware_version": "M1.01.02.02.70",
        },
        "/gopro/camera/capabilities": {
            "schemaVersion": "camera-capabilities/v1.0",
            "protocol": {"supports_2byte_ids": True},
        },
        "/gopro/version": {"version": "2.0"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = responses.get(request.url.path)
        return httpx.Response(200, json=payload) if payload else httpx.Response(404)

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        compatibility = await client.get_compatibility()
    finally:
        await client.close()

    assert compatibility.ready
    assert compatibility.labs_version_current
    assert compatibility.supports_two_byte_ids
    assert compatibility.open_gopro_version == "2.0"


def test_setting_probe_decodes_supported_options():
    asyncio.run(_test_setting_probe_decodes_supported_options())


async def _test_setting_probe_decodes_supported_options():
    def handler(request: httpx.Request) -> httpx.Response:
        if "option" not in request.url.params:
            return httpx.Response(200, json={"option": 5})
        return httpx.Response(403, json={
            "error": 3,
            "setting_id": 3,
            "option_id": 999,
            "supported_options": [
                {"id": 5, "display_name": "60.0"},
                {"id": 8, "display_name": "30.0"},
            ],
        })

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.probe_setting("3")
    finally:
        await client.close()

    assert result["current_option"] == "5"
    assert result["available"] == [
        {"id": 5, "name": "60.0"},
        {"id": 8, "name": "30.0"},
    ]
    assert not result["probe_changed"]


def test_status_uses_sd_kilobytes_and_mission_health_fields():
    asyncio.run(_test_status_uses_sd_kilobytes_and_mission_health_fields())


async def _test_status_uses_sd_kilobytes_and_mission_health_fields():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": {
            "6": 1, "8": 0, "10": 1, "13": 42, "35": 3600,
            "54": 64_000_000, "70": 83, "111": 1, "112": 2, "115": 1,
        }})

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        status = await client.get_status()
    finally:
        await client.close()

    assert status.storage_gb_free == 64.0
    assert status.recording_duration_s == 42
    assert status.remaining_video_time_s == 3600
    assert status.overheating and status.sd_write_error and status.usb_connected
    assert status.sd_card_errors == 2


def test_safe_stop_waits_for_file_finalization():
    asyncio.run(_test_safe_stop_waits_for_file_finalization())


async def _test_safe_stop_waits_for_file_finalization():
    state_reads = 0
    stopped = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal state_reads, stopped
        if request.url.path == "/gopro/camera/shutter/stop":
            stopped = True
            return httpx.Response(200)
        if request.url.path == "/gopro/camera/state":
            state_reads += 1
            if not stopped:
                return httpx.Response(200, json={"status": {"8": 1, "10": 1}})
            busy = state_reads < 3
            return httpx.Response(200, json={"status": {"8": int(busy), "10": 0}})
        return httpx.Response(404)

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await client.stop_recording_and_wait(timeout=1.0)
    finally:
        await client.close()

    assert stopped
    assert state_reads >= 3


def test_ensure_video_mode_preserves_active_video_preset():
    asyncio.run(_test_ensure_video_mode_preserves_active_video_preset())


async def _test_ensure_video_mode_preserves_active_video_preset():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/gopro/camera/presets/get":
            return httpx.Response(200, json=_mission_presets())
        return httpx.Response(404)

    client = GoProClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await client.ensure_video_mode()
    finally:
        await client.close()

    assert [request.url.path for request in requests] == ["/gopro/camera/presets/get"]


def test_configured_preset_order_preserves_active_and_unknown_entries():
    async def scenario():
        data = {"activePresetId": 10, "presetGroupArray": [{"presetArray": [
            {"id": 10, "customName": "水下通用4K"},
            {"id": 20, "customName": "Other"},
            {"id": 30, "customName": "水下通用1080p"},
        ]}]}
        client = GoProClient(preset_order=["水下通用1080p", "水下通用4K"])
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=data)))
        try:
            result = await client.get_preset_status()
            assert result["activePresetId"] == 10
            assert [p["id"] for p in result["presetGroupArray"][0]["presetArray"]] == [30, 10, 20]
        finally:
            await client.close()
    asyncio.run(scenario())

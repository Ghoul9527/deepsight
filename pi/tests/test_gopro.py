"""Tests for the GoPro controller module."""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared", "src"))

import pytest


def async_test(coro):
    """Helper to run async tests without pytest-asyncio."""
    return asyncio.run(coro)


# ── base.py ────────────────────────────────────────────

class TestGoProControllerABC:
    def test_abc_cannot_instantiate(self):
        from deepsight_pi.gopro.base import GoProController
        with pytest.raises(TypeError):
            GoProController()

    def test_abstract_methods_present(self):
        from deepsight_pi.gopro.base import GoProController
        methods = GoProController.__abstractmethods__
        # Must cover all functional groups
        assert "open" in methods
        assert "close" in methods
        assert "start_recording" in methods
        assert "stop_recording" in methods
        assert "get_status" in methods
        assert "list_media" in methods


class TestGoProStatusDataclass:
    def test_defaults(self):
        from deepsight_pi.gopro.base import GoProStatus
        s = GoProStatus()
        assert s.recording is False
        assert s.battery_pct == 0.0
        assert s.storage_gb_total == 0.0
        assert s.storage_gb_free == 0.0
        assert s.mode == "video"
        assert s.encoding is False
        assert s.busy is False
        assert s.usb_connected is False

    def test_field_assignment(self):
        from deepsight_pi.gopro.base import GoProStatus
        s = GoProStatus(
            recording=True, battery_pct=72.0,
            storage_gb_total=256.0, storage_gb_free=180.0,
            mode="video", encoding=True, busy=False,
            overheating=False, usb_connected=True,
            model_name="HERO13", firmware_version="1.0",
        )
        assert s.recording is True
        assert s.battery_pct == 72.0
        assert s.storage_gb_total == 256.0


class TestMediaFileDataclass:
    def test_defaults(self):
        from deepsight_pi.gopro.base import MediaFile
        m = MediaFile(name="", path="", size_bytes=0, created_iso="")
        assert m.name == ""
        assert m.path == ""
        assert m.size_bytes == 0

    def test_field_assignment(self):
        from deepsight_pi.gopro.base import MediaFile
        m = MediaFile(
            name="GX010001.MP4", path="/DCIM/100GOPRO/GX010001.MP4",
            size_bytes=123456789, created_iso="2026-05-10T14:30:00Z",
            duration_s=60.0, resolution="4K", fps=60,
        )
        assert m.name == "GX010001.MP4"
        assert m.path == "/DCIM/100GOPRO/GX010001.MP4"
        assert m.size_bytes == 123456789
        assert m.duration_s == 60.0
        assert m.resolution == "4K"


class TestMediaListDataclass:
    def test_defaults(self):
        from deepsight_pi.gopro.base import MediaList
        ml = MediaList()
        assert ml.files == []
        assert ml.total_count == 0
        assert ml.total_size_bytes == 0


# ── mock_gopro.py ──────────────────────────────────────

class TestMockGoPro:
    @pytest.fixture
    def g(self):
        from deepsight_pi.gopro.mock_gopro import MockGoPro
        return MockGoPro()

    def test_initial_not_connected(self, g):
        assert g.connected is False

    def test_open(self, g):
        assert async_test(g.open()) is True
        assert g.connected is True

    def test_close(self, g):
        async_test(g.open())
        async_test(g.close())
        assert g.connected is False

    def test_is_ready(self, g):
        assert async_test(g.is_ready()) is False
        async_test(g.open())
        assert async_test(g.is_ready()) is True

    def test_start_stop_recording(self, g):
        async_test(g.open())
        assert async_test(g.start_recording()) is True
        status = async_test(g.get_status())
        assert status.recording is True
        assert async_test(g.stop_recording()) is True
        status = async_test(g.get_status())
        assert status.recording is False

    def test_take_photo(self, g):
        async_test(g.open())
        assert async_test(g.take_photo()) is True

    def test_add_hilight(self, g):
        async_test(g.open())
        assert async_test(g.add_hilight()) is True

    def test_load_preset(self, g):
        async_test(g.open())
        assert async_test(g.load_preset(0)) is True

    def test_load_preset_group(self, g):
        async_test(g.open())
        assert async_test(g.load_preset_group(0)) is True
        status = async_test(g.get_preset_status())
        assert status["group_id"] == 1000
        assert len(status["presets"]) > 0

    def test_get_preset_status(self, g):
        async_test(g.open())
        s = async_test(g.get_preset_status())
        assert "presets" in s
        assert "active_preset_id" in s

    def test_set_video_resolution(self, g):
        async_test(g.open())
        assert async_test(g.set_video_resolution("1080")) is True
        assert async_test(g.get_all_settings())["video_resolution"] == "1080"

    def test_set_frame_rate(self, g):
        async_test(g.open())
        assert async_test(g.set_frame_rate(30)) is True
        assert async_test(g.get_all_settings())["frame_rate"] == "30"

    def test_set_video_lens(self, g):
        async_test(g.open())
        assert async_test(g.set_video_lens("LINEAR")) is True

    def test_set_hypersmooth(self, g):
        async_test(g.open())
        assert async_test(g.set_hypersmooth("BOOST")) is True

    def test_set_turbo_mode(self, g):
        async_test(g.open())
        assert async_test(g.set_turbo_mode(True)) is True

    def test_get_status(self, g):
        async_test(g.open())
        status = async_test(g.get_status())
        from deepsight_pi.gopro.base import GoProStatus
        assert isinstance(status, GoProStatus)
        assert status.usb_connected is True
        assert isinstance(status.battery_pct, float)
        assert isinstance(status.storage_gb_free, float)

    def test_get_battery(self, g):
        async_test(g.open())
        pct = async_test(g.get_battery_pct())
        assert isinstance(pct, float)
        assert 0.0 <= pct <= 100.0

    def test_get_storage_free(self, g):
        async_test(g.open())
        gb = async_test(g.get_storage_free_gb())
        assert isinstance(gb, float)
        assert gb > 0

    def test_is_encoding(self, g):
        async_test(g.open())
        assert async_test(g.is_encoding()) is False
        async_test(g.start_recording())
        assert async_test(g.is_encoding()) is True

    def test_get_all_statuses(self, g):
        async_test(g.open())
        s = async_test(g.get_all_statuses())
        assert isinstance(s, dict)

    def test_list_media(self, g):
        async_test(g.open())
        ml = async_test(g.list_media())
        from deepsight_pi.gopro.base import MediaList
        assert isinstance(ml, MediaList)
        assert ml.total_count == 2
        assert len(ml.files) == 2

    def test_download_file(self, g, tmp_path):
        async_test(g.open())
        result = async_test(g.download_file("/DCIM/100GOPRO/GOPR0001.MP4", str(tmp_path)))
        assert result is not None
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    def test_download_last_capture(self, g, tmp_path):
        async_test(g.open())
        result = async_test(g.download_last_capture(str(tmp_path)))
        assert result is not None

    def test_delete_file(self, g):
        async_test(g.open())
        count_before = async_test(g.list_media()).total_count
        async_test(g.delete_file("/DCIM/100GOPRO/GOPR0001.MP4"))
        count_after = async_test(g.list_media()).total_count
        assert count_after == count_before - 1

    def test_delete_all_media(self, g):
        async_test(g.open())
        assert async_test(g.delete_all_media()) is True
        ml = async_test(g.list_media())
        assert ml.total_count == 0

    def test_get_thumbnail(self, g):
        async_test(g.open())
        thumb = async_test(g.get_thumbnail("/DCIM/100GOPRO/GOPR0001.MP4"))
        assert isinstance(thumb, bytes)

    def test_get_telemetry(self, g):
        async_test(g.open())
        tel = async_test(g.get_telemetry("/DCIM/100GOPRO/GOPR0001.MP4"))
        assert isinstance(tel, bytes)

    def test_power_off(self, g):
        async_test(g.open())
        assert async_test(g.power_off()) is True
        assert g.connected is False

    def test_sleep(self, g):
        async_test(g.open())
        assert async_test(g.sleep()) is True

    def test_reboot(self, g):
        async_test(g.open())
        assert async_test(g.reboot()) is True

    def test_get_date_time(self, g):
        async_test(g.open())
        dt = async_test(g.get_date_time())
        assert isinstance(dt, str)
        assert len(dt) > 0

    def test_set_date_time(self, g):
        async_test(g.open())
        assert async_test(g.set_date_time()) is True

    def test_get_hardware_info(self, g):
        async_test(g.open())
        info = async_test(g.get_hardware_info())
        assert isinstance(info, dict)
        assert "model_name" in info

    def test_get_camera_capabilities(self, g):
        async_test(g.open())
        caps = async_test(g.get_camera_capabilities())
        assert isinstance(caps, dict)

    def test_get_all_settings(self, g):
        async_test(g.open())
        settings = async_test(g.get_all_settings())
        assert isinstance(settings, dict)
        assert "video_resolution" in settings

    def test_set_setting_generic(self, g):
        async_test(g.open())
        assert async_test(g.set_setting("custom_key", "custom_val")) is True
        assert async_test(g.get_all_settings())["custom_key"] == "custom_val"


# ── real_gopro.py ──────────────────────────────────────

class TestRealGoProNoSDK:
    def test_init_without_sdk(self):
        from deepsight_pi.gopro.real_gopro import RealGoPro
        gopro = RealGoPro()
        assert gopro.connected is False

    def test_open_fails_without_sdk(self):
        from deepsight_pi.gopro.real_gopro import RealGoPro
        gopro = RealGoPro()
        assert async_test(gopro.open()) is False


# ── factory ────────────────────────────────────────────

class TestCreateGoProFactory:
    def test_mock_true_returns_mock(self):
        from deepsight_pi.gopro import create_gopro
        from deepsight_pi.gopro.mock_gopro import MockGoPro
        gopro = create_gopro(mock=True)
        assert isinstance(gopro, MockGoPro)

    def test_mock_false_returns_real(self):
        from deepsight_pi.gopro import create_gopro
        from deepsight_pi.gopro.real_gopro import RealGoPro
        gopro = create_gopro(mock=False)
        assert isinstance(gopro, RealGoPro)

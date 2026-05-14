"""Mock GoPro controller — full GoProController implementation for development."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from deepsight_pi.gopro.base import (
    GoProController, GoProStatus, MediaFile, MediaList,
)

logger = logging.getLogger("pi.gopro.mock")


class MockGoPro(GoProController):
    """Stateful mock of a GoPro Hero camera. All methods are no-ops
    that return sensible defaults and log their calls."""

    def __init__(self):
        self._recording = False
        self._encoding = False
        self._battery = 85.0
        self._storage_total = 256.0
        self._storage_free = 180.3
        self._mode = "video"
        self._preset_group = 0
        self._connected = False
        self._settings: dict[str, str] = {
            "video_resolution": "4K",
            "frame_rate": "60",
            "video_lens": "WIDE",
            "hypersmooth": "BOOST",
            "video_bit_rate": "HIGH",
            "max_lens_mod": "NONE",
            "video_aspect_ratio": "16_9",
            "profiles": "STANDARD",
            "bit_depth": "10_BIT",
            "media_format": "VIDEO",
        }
        self._media: list[MediaFile] = [
            MediaFile("GOPR0001.MP4", "/DCIM/100GOPRO/GOPR0001.MP4",
                      524288000, "2026-05-10T08:30:00", 120.5, "4K", 60),
            MediaFile("GOPR0002.MP4", "/DCIM/100GOPRO/GOPR0002.MP4",
                      262144000, "2026-05-10T08:32:00", 60.0, "4K", 60),
        ]

    # ── Properties ────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Connection ────────────────────────────────────

    async def open(self) -> bool:
        logger.info("[MOCK] GoPro USB connected")
        self._connected = True
        return True

    async def close(self):
        logger.info("[MOCK] GoPro USB disconnected")
        self._connected = False

    async def is_ready(self) -> bool:
        return self._connected

    # ── Shutter ───────────────────────────────────────

    async def start_recording(self) -> bool:
        self._recording = True
        self._encoding = True
        logger.info("[MOCK] GoPro REC start")
        return True

    async def stop_recording(self) -> bool:
        self._recording = False
        self._encoding = False
        logger.info("[MOCK] GoPro REC stop")
        return True

    async def take_photo(self) -> bool:
        logger.info("[MOCK] GoPro photo taken")
        return True

    async def add_hilight(self) -> bool:
        logger.info("[MOCK] GoPro HiLight tagged")
        return True

    # ── Presets ───────────────────────────────────────

    async def load_preset(self, preset_id: int) -> bool:
        logger.info("[MOCK] GoPro load preset: %d", preset_id)
        return True

    async def load_preset_group(self, group_id: int) -> bool:
        mode_map = {0: "video", 1: "photo", 2: "timelapse"}
        self._mode = mode_map.get(group_id, "video")
        self._preset_group = group_id
        logger.info("[MOCK] GoPro preset group: %s", self._mode)
        return True

    async def get_preset_status(self) -> dict:
        return {
            "group_id": 1000,
            "active_preset_id": 0,
            "presets": [
                {"id": 0, "title_id": 0, "title": "Activity",
                 "icon": 0, "mode": 12, "is_visible": True},
                {"id": 1, "title_id": 1, "title": "Standard",
                 "icon": 1, "mode": 12, "is_visible": True},
                {"id": 2, "title_id": 2, "title": "Cinematic",
                 "icon": 2, "mode": 12, "is_visible": True},
                {"id": 3, "title_id": 3, "title": "Ultra Slo-Mo",
                 "icon": 3, "mode": 12, "is_visible": True},
                {"id": 4, "title_id": 4, "title": "Basic",
                 "icon": 4, "mode": 12, "is_visible": True},
                {"id": 5, "title_id": 5, "title": "5.3K 30",
                 "icon": 5, "mode": 12, "is_visible": True},
                {"id": 6, "title_id": 6, "title": "4K 60",
                 "icon": 6, "mode": 12, "is_visible": True},
                {"id": 7, "title_id": 7, "title": "1080p 120",
                 "icon": 7, "mode": 12, "is_visible": True},
                {"id": 8, "title_id": 8, "title": "HDR",
                 "icon": 8, "mode": 12, "is_visible": True},
                {"id": 9, "title_id": 9, "title": "Log",
                 "icon": 9, "mode": 12, "is_visible": True},
            ],
        }

    # ── Settings ──────────────────────────────────────

    async def set_video_resolution(self, resolution: str) -> bool:
        self._settings["video_resolution"] = resolution
        return True

    async def set_frame_rate(self, fps: int) -> bool:
        self._settings["frame_rate"] = str(fps)
        return True

    async def set_video_lens(self, lens: str) -> bool:
        self._settings["video_lens"] = lens
        return True

    async def set_hypersmooth(self, level: str) -> bool:
        self._settings["hypersmooth"] = level
        return True

    async def set_video_bit_rate(self, rate: str) -> bool:
        self._settings["video_bit_rate"] = rate
        return True

    async def set_max_lens_mod(self, mod: str) -> bool:
        self._settings["max_lens_mod"] = mod
        return True

    async def set_video_aspect_ratio(self, ratio: str) -> bool:
        self._settings["video_aspect_ratio"] = ratio
        return True

    async def set_profiles(self, profile: str) -> bool:
        self._settings["profiles"] = profile
        return True

    async def set_bit_depth(self, bits: str) -> bool:
        self._settings["bit_depth"] = bits
        return True

    async def set_media_format(self, fmt: str) -> bool:
        self._settings["media_format"] = fmt
        return True

    async def set_setting(self, name: str, value) -> bool:
        self._settings[name] = str(value)
        return True

    async def get_all_settings(self) -> dict:
        return dict(self._settings)

    # ── Status ────────────────────────────────────────

    async def get_status(self) -> GoProStatus:
        self._battery = max(0.0, self._battery - 0.01)
        return GoProStatus(
            recording=self._recording,
            battery_pct=self._battery,
            storage_gb_total=self._storage_total,
            storage_gb_free=self._storage_free,
            mode=self._mode,
            encoding=self._encoding,
            busy=False,
            sd_card_error=False,
            overheating=False,
            usb_connected=True,
            model_name="HERO13 Black (MOCK)",
            firmware_version="H25.01.01.00",
        )

    async def get_battery_pct(self) -> float:
        return self._battery

    async def get_storage_free_gb(self) -> float:
        return self._storage_free

    async def is_encoding(self) -> bool:
        return self._encoding

    async def get_all_statuses(self) -> dict:
        return {"battery": self._battery, "encoding": self._encoding}

    # ── Media ─────────────────────────────────────────

    async def list_media(self) -> MediaList:
        return MediaList(files=self._media, total_count=len(self._media),
                         total_size_bytes=sum(f.size_bytes for f in self._media))

    async def download_file(self, remote_path: str, local_dir: str) -> str | None:
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        fname = remote_path.rsplit("/", 1)[-1]
        local = f"{local_dir}/{fname}"
        with open(local, 'wb') as f:
            f.write(b"\x00" * 1024)
        logger.info("[MOCK] Downloaded %s → %s", remote_path, local)
        return local

    async def download_last_capture(self, local_dir: str) -> str | None:
        return await self.download_file("/DCIM/100GOPRO/GOPR0001.MP4", local_dir)

    async def delete_file(self, remote_path: str) -> bool:
        self._media = [m for m in self._media if m.path != remote_path]
        logger.info("[MOCK] Deleted %s", remote_path)
        return True

    async def delete_all_media(self) -> bool:
        self._media.clear()
        logger.info("[MOCK] All media deleted")
        return True

    async def get_thumbnail(self, remote_path: str) -> bytes | None:
        return b"\xff\xd8"

    async def get_telemetry(self, remote_path: str) -> bytes | None:
        return b'{"mock_telemetry": true}\n'

    # ── USB turbo transfer ────────────────────────────

    async def set_turbo_mode(self, enable: bool) -> bool:
        logger.info("[MOCK] Turbo transfer: %s", "ON" if enable else "OFF")
        return True

    # ── Power ─────────────────────────────────────────

    async def power_off(self) -> bool:
        logger.info("[MOCK] GoPro power off")
        self._connected = False
        return True

    async def sleep(self) -> bool:
        logger.info("[MOCK] GoPro sleep")
        return True

    async def reboot(self) -> bool:
        logger.info("[MOCK] GoPro reboot")
        return True

    async def get_date_time(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    async def set_date_time(self) -> bool:
        return True

    # ── Hardware info ─────────────────────────────────

    async def get_hardware_info(self) -> dict:
        return {"model_name": "HERO13 Black (MOCK)", "firmware": "H25.01.01.00"}

    async def get_camera_capabilities(self) -> dict:
        return {"supports_hdr": True, "supports_log": True}

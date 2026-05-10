"""GoPro camera controller — wired USB-C ABC interface.

Wraps open-gopro WiredGoPro for Hero 9–13 cameras connected via USB-C.
Video preview is handled by HDMI capture (CaptureDevice), NOT this interface.
All methods use HTTP over USB; no BLE or WiFi.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("pi.gopro")


@dataclass
class GoProStatus:
    recording: bool = False
    battery_pct: float = 0.0
    storage_gb_total: float = 0.0
    storage_gb_free: float = 0.0
    mode: str = "video"
    encoding: bool = False
    busy: bool = False
    sd_card_error: bool = False
    overheating: bool = False
    usb_connected: bool = False
    model_name: str = ""
    firmware_version: str = ""


@dataclass
class MediaFile:
    name: str
    path: str
    size_bytes: int
    created_iso: str
    duration_s: float = 0.0
    resolution: str = ""
    fps: int = 0
    is_photo: bool = False


@dataclass
class MediaList:
    files: list[MediaFile] = field(default_factory=list)
    total_count: int = 0
    total_size_bytes: int = 0


class GoProController(ABC):
    """Wired GoPro camera interface — HTTP over USB-C.

    Video preview comes from HDMI capture (not this interface).
    All methods are async. Implementations: MockGoPro, RealGoPro.
    """

    # ── Connection ───────────────────────────────────

    @abstractmethod
    async def open(self) -> bool:
        """Open USB connection. Camera must be plugged in via USB-C."""

    @abstractmethod
    async def close(self):
        """Close USB connection, release resources."""

    @abstractmethod
    async def is_ready(self) -> bool:
        """Camera connected and accepting commands."""

    @property
    @abstractmethod
    def connected(self) -> bool: ...

    # ── Shutter ──────────────────────────────────────

    @abstractmethod
    async def start_recording(self) -> bool: ...

    @abstractmethod
    async def stop_recording(self) -> bool: ...

    @abstractmethod
    async def take_photo(self) -> bool: ...

    @abstractmethod
    async def add_hilight(self) -> bool:
        """Tag the current moment with a HiLight marker."""

    # ── Presets ──────────────────────────────────────

    @abstractmethod
    async def load_preset(self, preset_id: int) -> bool: ...

    @abstractmethod
    async def load_preset_group(self, group_id: int) -> bool:
        """Load a preset group: 0=video, 1=photo, 2=timelapse."""

    @abstractmethod
    async def get_preset_status(self) -> dict: ...

    # ── Settings (video-focused, via http_setting) ────

    @abstractmethod
    async def set_video_resolution(self, resolution: str) -> bool:
        """'4K', '5.3K', '1080' etc."""

    @abstractmethod
    async def set_frame_rate(self, fps: int) -> bool:
        """24, 30, 60, 120, 240 etc."""

    @abstractmethod
    async def set_video_lens(self, lens: str) -> bool:
        """'WIDE', 'LINEAR', 'SUPERVIEW', 'HYPERVIEW'."""

    @abstractmethod
    async def set_hypersmooth(self, level: str) -> bool:
        """'OFF', 'STANDARD', 'HIGH', 'BOOST', 'AUTO_BOOST'."""

    @abstractmethod
    async def set_video_bit_rate(self, rate: str) -> bool:
        """'STANDARD', 'HIGH', 'MAX'."""

    @abstractmethod
    async def set_max_lens_mod(self, mod: str) -> bool: ...

    @abstractmethod
    async def set_video_aspect_ratio(self, ratio: str) -> bool: ...

    @abstractmethod
    async def set_profiles(self, profile: str) -> bool:
        """'STANDARD', 'HDR', 'LOG'."""

    @abstractmethod
    async def set_bit_depth(self, bits: str) -> bool:
        """'8_BIT', '10_BIT'."""

    @abstractmethod
    async def set_media_format(self, fmt: str) -> bool: ...

    @abstractmethod
    async def set_setting(self, name: str, value) -> bool:
        """Generic setting setter."""

    @abstractmethod
    async def get_all_settings(self) -> dict: ...

    # ── Status ───────────────────────────────────────

    @abstractmethod
    async def get_status(self) -> GoProStatus:
        """Snapshot of critical status fields."""

    @abstractmethod
    async def get_battery_pct(self) -> float: ...

    @abstractmethod
    async def get_storage_free_gb(self) -> float: ...

    @abstractmethod
    async def is_encoding(self) -> bool: ...

    @abstractmethod
    async def get_all_statuses(self) -> dict: ...

    # ── Media (TF card → Host via Pi) ─────────────────

    @abstractmethod
    async def list_media(self) -> MediaList: ...

    @abstractmethod
    async def download_file(self, remote_path: str, local_dir: str) -> str | None:
        """Download one file; returns local path or None."""

    @abstractmethod
    async def download_last_capture(self, local_dir: str) -> str | None: ...

    @abstractmethod
    async def delete_file(self, remote_path: str) -> bool: ...

    @abstractmethod
    async def delete_all_media(self) -> bool: ...

    @abstractmethod
    async def get_thumbnail(self, remote_path: str) -> bytes | None: ...

    @abstractmethod
    async def get_telemetry(self, remote_path: str) -> bytes | None:
        """Extract GPMF telemetry from a recording."""

    # ── USB transfer ─────────────────────────────────

    @abstractmethod
    async def set_turbo_mode(self, enable: bool) -> bool:
        """Enable turbo transfer for faster file downloads."""

    # ── Power ────────────────────────────────────────

    @abstractmethod
    async def power_off(self) -> bool: ...

    @abstractmethod
    async def sleep(self) -> bool: ...

    @abstractmethod
    async def reboot(self) -> bool: ...

    @abstractmethod
    async def get_date_time(self) -> str: ...

    @abstractmethod
    async def set_date_time(self) -> bool:
        """Sync camera clock to this machine."""

    # ── Hardware info ────────────────────────────────

    @abstractmethod
    async def get_hardware_info(self) -> dict: ...

    @abstractmethod
    async def get_camera_capabilities(self) -> dict: ...

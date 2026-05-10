"""Real GoPro controller — wired USB-C via open-gopro WiredGoPro.

Physical topology:
  GoPro USB-C ──▶ Pi USB 3.0  (control — this module)
  GoPro MicroHDMI ──▶ Capture dongle ──▶ Pi USB 3.0  (video — CaptureDevice)

Requires: pip install open-gopro
Supports Hero 9–13 via USB wired control.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from deepsight_pi.gopro.base import (
    GoProController, GoProStatus, MediaFile, MediaList,
)

logger = logging.getLogger("pi.gopro.real")


class RealGoPro(GoProController):
    """Wraps open_gopro.WiredGoPro for USB-C wired control.

    Usage:
        gopro = RealGoPro()
        await gopro.open()
        await gopro.start_recording()
        ...
        await gopro.close()
    """

    def __init__(self):
        self._gopro = None
        self._connected = False
        self._sdk_available = False
        self._check_sdk()

    def _check_sdk(self):
        try:
            import open_gopro
            self._sdk_available = True
        except ImportError:
            logger.warning("open-gopro SDK not installed. Run: pip install open-gopro")
            self._sdk_available = False

    # ── Properties ───────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Connection ───────────────────────────────────

    async def open(self) -> bool:
        if not self._sdk_available:
            logger.error("open-gopro SDK not installed")
            return False

        try:
            from open_gopro import WiredGoPro
            self._gopro = WiredGoPro()
            await self._gopro.open()
            self._connected = True
            logger.info("GoPro connected via USB-C")

            # Sync clock
            try:
                await self._gopro.http_command.set_date_time_tz_dst()
            except Exception:
                pass

            return True
        except Exception as e:
            logger.error("GoPro USB open failed: %s", e)
            self._gopro = None
            return False

    async def close(self):
        if self._gopro is not None:
            try:
                await self._gopro.close()
            except Exception as e:
                logger.debug("GoPro close error: %s", e)
            finally:
                self._gopro = None
        self._connected = False

    async def is_ready(self) -> bool:
        if self._gopro is None:
            return False
        try:
            return await self._gopro.is_ready()
        except Exception:
            return False

    # ── Shutter ──────────────────────────────────────

    async def start_recording(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(1))

    async def stop_recording(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(0))

    async def take_photo(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(1))

    async def add_hilight(self) -> bool:
        return await self._http(lambda g: g.http_command.add_file_hilight())

    # ── Presets ──────────────────────────────────────

    async def load_preset(self, preset_id: int) -> bool:
        return await self._http(lambda g: g.http_command.load_preset(preset=preset_id))

    async def load_preset_group(self, group_id: int) -> bool:
        return await self._http(lambda g: g.http_command.load_preset_group(group=group_id))

    async def get_preset_status(self) -> dict:
        return await self._get_dict(lambda g: g.http_command.get_preset_status())

    # ── Settings ─────────────────────────────────────

    async def set_video_resolution(self, resolution: str) -> bool:
        return await self._set_http_setting("video_resolution", resolution)

    async def set_frame_rate(self, fps: int) -> bool:
        mapping = {24: "NUM_24_0", 30: "NUM_30_0", 60: "NUM_60_0",
                   100: "NUM_100_0", 120: "NUM_120_0", 240: "NUM_240_0"}
        val = mapping.get(int(fps), f"NUM_{int(fps)}_0")
        return await self._set_http_setting("frame_rate", val)

    async def set_video_lens(self, lens: str) -> bool:
        return await self._set_http_setting("video_lens", lens.upper())

    async def set_hypersmooth(self, level: str) -> bool:
        return await self._set_http_setting("hypersmooth", level.upper())

    async def set_video_bit_rate(self, rate: str) -> bool:
        return await self._set_http_setting("video_bit_rate", rate.upper())

    async def set_max_lens_mod(self, mod: str) -> bool:
        return await self._set_http_setting("max_lens_mod", mod.upper())

    async def set_video_aspect_ratio(self, ratio: str) -> bool:
        return await self._set_http_setting("video_aspect_ratio", ratio.upper())

    async def set_profiles(self, profile: str) -> bool:
        return await self._set_http_setting("profiles", profile.upper())

    async def set_bit_depth(self, bits: str) -> bool:
        return await self._set_http_setting("bit_depth", bits.upper())

    async def set_media_format(self, fmt: str) -> bool:
        return await self._set_http_setting("media_format", fmt.upper())

    async def set_setting(self, name: str, value) -> bool:
        return await self._set_http_setting(name, value)

    async def get_all_settings(self) -> dict:
        return await self._get_dict(lambda g: g.http_command.get_camera_state())

    async def _set_http_setting(self, name: str, value) -> bool:
        """Set a setting via http_setting by attribute name."""
        return await self._http(lambda g: _set_attr(g.http_setting, name, value))

    # ── Status ───────────────────────────────────────

    async def get_status(self) -> GoProStatus:
        try:
            state = await self._gopro.http_command.get_camera_state()
            s = state.data if hasattr(state, 'data') else {}
        except Exception:
            return GoProStatus()

        # WiredGoPro returns camera state as a dict or object
        # Keys vary by firmware; use safe gets
        try:
            status_dict = s.get("status", s) if isinstance(s, dict) else vars(s)
        except TypeError:
            return GoProStatus()

        return GoProStatus(
            recording=bool(_safe_get(status_dict, "encoding_active", 0)),
            battery_pct=float(_safe_get(status_dict, "internal_battery_percentage", 0)),
            storage_gb_total=float(_safe_get(status_dict, "sd_card_capacity", 0)) / 1e9,
            storage_gb_free=float(_safe_get(status_dict, "sd_card_remaining", 0)) / 1e9,
            mode="video",
            encoding=bool(_safe_get(status_dict, "encoding_active", 0)),
            busy=bool(_safe_get(status_dict, "system_busy", 0)),
            overheating=bool(_safe_get(status_dict, "overheating", 0)),
            usb_connected=bool(_safe_get(status_dict, "usb_connected", 1)),
        )

    async def get_battery_pct(self) -> float:
        return await self._get_val(
            lambda g: g.http_command.get_camera_state(),
            lambda data: float(_safe_get(data, "internal_battery_percentage", 0)),
            0.0)

    async def get_storage_free_gb(self) -> float:
        v = await self._get_val(
            lambda g: g.http_command.get_camera_state(),
            lambda data: float(_safe_get(data, "sd_card_remaining", 0)),
            0)
        return v / 1e9

    async def is_encoding(self) -> bool:
        return await self._get_val(
            lambda g: g.http_command.get_camera_state(),
            lambda data: bool(_safe_get(data, "encoding_active", 0)),
            False)

    async def get_all_statuses(self) -> dict:
        return await self._get_dict(lambda g: g.http_command.get_camera_state())

    # ── Media ────────────────────────────────────────

    async def list_media(self) -> MediaList:
        resp = await self._http(lambda g: g.http_command.get_media_list())
        if not resp:
            return MediaList()
        try:
            ml = resp.data
            files = []
            for item in ml.files if hasattr(ml, 'files') else []:
                files.append(MediaFile(
                    name=getattr(item, 'name', ''),
                    path=str(getattr(item, 'path', '')),
                    size_bytes=getattr(item, 'size', 0),
                    created_iso=getattr(item, 'created', ''),
                    duration_s=getattr(item, 'duration', 0.0),
                    resolution=getattr(item, 'resolution', ''),
                    fps=getattr(item, 'fps', 0),
                ))
            return MediaList(files=files, total_count=len(files),
                             total_size_bytes=sum(f.size_bytes for f in files))
        except Exception as e:
            logger.error("list_media parse error: %s", e)
            return MediaList()

    async def download_file(self, remote_path: str, local_dir: str) -> str | None:
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        fname = os.path.basename(remote_path)
        local = os.path.join(local_dir, fname)

        resp = await self._http(
            lambda g: g.http_command.download_file(url=remote_path))
        if resp and hasattr(resp, 'data') and resp.data:
            with open(local, 'wb') as f:
                f.write(resp.data)
            logger.info("Downloaded %s → %s (%d bytes)",
                         remote_path, local, len(resp.data))
            return local
        return None

    async def download_last_capture(self, local_dir: str) -> str | None:
        resp = await self._http(
            lambda g: g.http_command.get_last_captured_media())
        if resp and hasattr(resp, 'data'):
            path = str(getattr(resp.data, 'path', ''))
            if path:
                return await self.download_file(path, local_dir)
        return None

    async def delete_file(self, remote_path: str) -> bool:
        return await self._http(
            lambda g: g.http_command.delete_file(url=remote_path))

    async def delete_all_media(self) -> bool:
        return await self._http(
            lambda g: g.http_command.delete_all_media())

    async def get_thumbnail(self, remote_path: str) -> bytes | None:
        resp = await self._http(
            lambda g: g.http_command.get_thumbnail(url=remote_path))
        return resp.data if hasattr(resp, 'data') else None

    async def get_telemetry(self, remote_path: str) -> bytes | None:
        resp = await self._http(
            lambda g: g.http_command.get_telemetry(url=remote_path))
        return resp.data if hasattr(resp, 'data') else None

    # ── USB turbo transfer ───────────────────────────

    async def set_turbo_mode(self, enable: bool) -> bool:
        return await self._http(
            lambda g: g.http_command.set_turbo_mode(1 if enable else 0))

    # ── Power ────────────────────────────────────────

    async def power_off(self) -> bool:
        # Power down over USB — may not work on all models
        return await self._http(lambda g: g.http_command.reboot())  # closest available

    async def sleep(self) -> bool:
        return False  # Not available over HTTP/wired

    async def reboot(self) -> bool:
        return await self._http(lambda g: g.http_command.reboot())

    async def get_date_time(self) -> str:
        return await self._get_val(
            lambda g: g.http_command.get_date_time(),
            lambda data: str(data) if data else "", "")

    async def set_date_time(self) -> bool:
        return await self._http(
            lambda g: g.http_command.set_date_time_tz_dst())

    # ── Hardware info ────────────────────────────────

    async def get_hardware_info(self) -> dict:
        return await self._get_dict(
            lambda g: g.http_command.get_camera_info())

    async def get_camera_capabilities(self) -> dict:
        return {}  # Not available over HTTP alone

    # ── Internal helpers ─────────────────────────────

    async def _http(self, fn) -> bool:
        if self._gopro is None:
            return False
        try:
            resp = await fn(self._gopro)
            return resp if resp is not None else True
        except Exception as e:
            logger.debug("GoPro HTTP error: %s", e)
            return False

    async def _get_val(self, get_fn, extract_fn, default):
        """Get a value: call *get_fn*, extract with *extract_fn*, return *default* on error."""
        if self._gopro is None:
            return default
        try:
            resp = await get_fn(self._gopro)
            data = resp.data if hasattr(resp, 'data') else resp
            return extract_fn(data)
        except Exception as e:
            logger.debug("GoPro get error: %s", e)
            return default

    async def _get_dict(self, get_fn) -> dict:
        if self._gopro is None:
            return {}
        try:
            resp = await get_fn(self._gopro)
            data = resp.data if hasattr(resp, 'data') else resp
            if isinstance(data, dict):
                return data
            if hasattr(data, '__dict__'):
                return vars(data)
            return {"value": str(data)}
        except Exception as e:
            logger.debug("GoPro get dict error: %s", e)
            return {}


def _set_attr(obj, name: str, value):
    """Set a dotted attribute on *obj*."""
    parts = name.split(".")
    target = obj
    for p in parts[:-1]:
        target = getattr(target, p)
    attr = getattr(target, parts[-1])
    return attr.set(value)


def _safe_get(d, key, default):
    """Safe dict get that also tries attribute access."""
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)

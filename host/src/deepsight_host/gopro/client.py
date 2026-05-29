"""GoPro HTTP client — talks to GoPro through Pi TCP forward (Pi:8080→GoPro:8080)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from deepsight_host.gopro.settings_decode import preset_summary

logger = logging.getLogger("host.gopro")

# Preset title names from GoPro API (int and string forms)
PRESET_TITLES: dict = {
    0: "Activity", 1: "Standard", 2: "Cinematic",
    3: "Ultra Slo-Mo", 4: "Basic", 5: "5.3K 30", 6: "4K 60",
    7: "1080p 120", 8: "HDR", 9: "Log", 10: "Video",
    11: "Slo-Mo", 12: "Photo", 13: "Burst", 14: "Night",
    15: "Time Lapse", 16: "Night Lapse", 17: "Star Trails",
    18: "Light Painting", 19: "Vehicle Lights",
    # String enum variants from real GoPro API
    "PRESET_TITLE_ACTIVITY": "Activity",
    "PRESET_TITLE_STANDARD": "Standard",
    "PRESET_TITLE_CINEMATIC": "Cinematic",
    "PRESET_TITLE_ULTRA_SLO_MO": "Ultra Slo-Mo",
    "PRESET_TITLE_BASIC": "Basic",
    "PRESET_TITLE_5_3K_30": "5.3K 30",
    "PRESET_TITLE_4K_60": "4K 60",
    "PRESET_TITLE_1080P_120": "1080p 120",
    "PRESET_TITLE_HDR": "HDR",
    "PRESET_TITLE_LOG": "Log",
    "PRESET_TITLE_VIDEO": "Video",
    "PRESET_TITLE_SLO_MO": "Slo-Mo",
    "PRESET_TITLE_PHOTO": "Photo",
    "PRESET_TITLE_BURST": "Burst",
    "PRESET_TITLE_NIGHT": "Night",
    "PRESET_TITLE_TIME_WARP": "Time Lapse",
    "PRESET_TITLE_NIGHT_LAPSE": "Night Lapse",
    "PRESET_TITLE_STAR_TRAIL": "Star Trails",
    "PRESET_TITLE_LIGHT_PAINTING": "Light Painting",
    "PRESET_TITLE_VEHICLE_LIGHTS": "Vehicle Lights",
    "PRESET_TITLE_TIME_LAPSE": "Time Lapse",
    "PRESET_TITLE_TIMELAPSE": "Time Lapse",
    "PRESET_TITLE_STANDARD_ENDURANCE": "Endurance",
    "PRESET_TITLE_ULTRA_SLO_MO_2": "Ultra Slo-Mo",
    "PRESET_TITLE_BURST_SLOMO": "Burst Slo-Mo",
    "PRESET_TITLE_LIGHT_TRAIL": "Light Trail",
    "PRESET_TITLE_USER_DEFINED_CUSTOM_NAME": "Custom",
}
PRESET_TITLES_DEFAULT = "Preset"


def _resolve_title(title_id) -> str:
    """Resolve preset title from int or string ID."""
    if title_id in PRESET_TITLES:
        return PRESET_TITLES[title_id]
    if isinstance(title_id, str):
        # "PRESET_TITLE_TIME_WARP" → "Time Warp"
        name = title_id.replace("PRESET_TITLE_", "").replace("_", " ").title()
        return name
    return f"{PRESET_TITLES_DEFAULT} {title_id}"


@dataclass
class GoProStatus:
    recording: bool = False
    battery_pct: float = 0.0
    storage_gb_free: float = 0.0
    mode: str = "video"
    model_name: str = ""
    busy: bool = False
    overheating: bool = False


class GoProClient:
    """Async HTTP client for GoPro camera (via Pi TCP forward).

    GoPro checks the HTTP Host header and rejects requests with a
    different host.  ``real_host`` is set as the Host header so GoPro
    accepts the request even though the actual TCP connection goes to
    the Pi's forwarded port.
    """

    def __init__(self, base_url: str = "http://192.168.20.51:8080",
                 real_host: str = "172.25.132.51"):
        self._base = base_url
        self._real_host = real_host
        self._client: httpx.AsyncClient | None = None

    async def open(self):
        headers = {"Host": self._real_host}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(3.0), headers=headers)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_ready(self) -> bool:
        """Check if GoPro is reachable."""
        return await self._get("/gopro/camera/state")

    # ── Shutter ──────────────────────────────────────

    async def start_recording(self) -> bool:
        # HERO13 shutter: try GET first (per OpenAPI spec), then POST
        if await self._get("/gopro/camera/shutter/start"):
            return True
        return await self._post("/gopro/camera/shutter/start")

    async def stop_recording(self) -> bool:
        if await self._get("/gopro/camera/shutter/stop"):
            return True
        return await self._post("/gopro/camera/shutter/stop")

    # ── Stream ───────────────────────────────────────

    async def start_viewfinder(self, port: int = 8554) -> bool:
        """Start the camera's live preview (viewfinder) stream.

        GoPro sends MPEG-TS UDP to the source IP of this HTTP request
        on the specified port.  With Pi SNAT, GoPro sees the Pi's USB IP
        as the source, so UDP goes to Pi:port.  Pi's socat relays to Host.
        """
        return await self._get(f"/gopro/camera/stream/start?port={port}")

    async def stop_viewfinder(self) -> bool:
        """Stop the camera's live preview stream."""
        return await self._get("/gopro/camera/stream/stop")

    async def enable_wired_usb(self, enable: bool = True) -> bool:
        """Enable/disable wired USB camera control.

        Must be enabled before shutter/recording commands will work.
        """
        p = 1 if enable else 0
        return await self._get(f"/gopro/camera/control/wired_usb?p={p}")

    # ── Presets ──────────────────────────────────────

    async def load_preset(self, preset_id: int) -> bool:
        return await self._get(f"/gopro/camera/presets/load?id={preset_id}")

    async def load_preset_group(self, group_id: int) -> bool:
        return await self._get(f"/gopro/camera/presets/set_group?id={group_id}")

    async def get_preset_status(self) -> dict | None:
        """Returns raw preset status from GoPro, or None."""
        return await self._get_json("/gopro/camera/presets/get")

    # ── Settings ─────────────────────────────────────

    async def set_setting(self, setting_id: str | int, value: str) -> bool:
        return await self._get(
            f"/gopro/camera/setting?setting={setting_id}&option={value}")

    async def get_setting(self, setting_id: str | int) -> int | None:
        """Read current option value for a numeric setting ID."""
        data = await self._get_json(
            f"/gopro/camera/setting?setting={setting_id}")
        if data:
            return data.get("option")
        return None

    async def get_all_settings(self) -> dict:
        """Get full camera state."""
        data = await self._get_json("/gopro/camera/state")
        return data if data else {}

    # ── Status ───────────────────────────────────────

    async def get_status(self) -> GoProStatus:
        """Snapshot of critical status fields.

        Raises ConnectionError when the GoPro is unreachable so callers
        can detect offline state.

        Status IDs (HERO13):
          2: internal_battery_bars (0-4)
          6: overheating (1=yes)
          8: busy (1=yes)
          10: encoding (1=recording)
          35: remaining_video_time_seconds
          54: sd_card_remaining_bytes
          70: internal_battery_pct (0-100)
        """
        data = await self._get_json("/gopro/camera/state")
        if not data:
            raise ConnectionError("GoPro unreachable")
        status = data.get("status", data)
        battery_pct = float(_safe_get(status, '70', 0))
        if battery_pct <= 0:
            battery_bars = int(_safe_get(status, '2', 0))
            battery_pct = float(battery_bars) / 4.0 * 100.0
        sd_bytes = int(_safe_get(status, '54', 0))
        return GoProStatus(
            recording=bool(int(_safe_get(status, '10', 0))),
            battery_pct=battery_pct,
            storage_gb_free=float(sd_bytes) / 1e9 if sd_bytes > 0 else 0.0,
            model_name=str(data.get("model_name", "")),
            busy=bool(int(_safe_get(status, '8', 0))),
            overheating=bool(int(_safe_get(status, '6', 0))),
        )

    async def get_camera_info(self) -> dict:
        data = await self._get_json("/gopro/camera/info")
        return data if data else {}

    # ── Probe ────────────────────────────────────────

    async def probe_setting(self, setting_id: str) -> dict:
        """Probe available options for a setting.

        Sends GET with probe option to trigger error-3 response
        containing available_options. Restores original value.

        Returns: {setting, current_option, available, probe_changed}
        """
        result = {
            "setting": setting_id,
            "current_option": "",
            "available": None,
            "probe_changed": False,
        }
        try:
            sid = int(setting_id)
        except (ValueError, TypeError):
            return result

        # Read current value
        current = await self.get_setting(sid)
        result["current_option"] = str(current) if current is not None else ""

        # Use a known-invalid option to trigger error-3
        ok = await self.set_setting(sid, "999")
        if ok:
            # The probe option was accepted — restore original
            result["probe_changed"] = True
            if current is not None:
                await self.set_setting(sid, str(current))

        return result

    # ── Media ────────────────────────────────────────

    async def list_media(self, video_only: bool = True) -> list[dict] | None:
        """List media files on SD card. Returns flat list of {directory,
        filename, size, created} dicts, or None on failure."""
        data = await self._get_json("/gopro/media/list")
        if not data:
            logger.info("GoPro media list: empty response")
            return None
        logger.info("GoPro media list: keys=%s, media_count=%s",
                    list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                    len(data.get("media", [])) if isinstance(data, dict) else "N/A")
        files: list[dict] = []
        for m in data.get("media", []):
            d = m.get("d", "")
            for f in m.get("fs", []):
                fn = f.get("n", "")
                if video_only and not fn.upper().endswith(".MP4"):
                    continue
                files.append({
                    "directory": d,
                    "filename": fn,
                    "size": int(f.get("s", 0)),
                    "created": int(f.get("cre", 0)),
                })
        logger.info("GoPro media list: %d video files found", len(files))
        return files

    async def get_thumbnail(self, directory: str, filename: str) -> bytes | None:
        """Fetch JPEG thumbnail for a media file."""
        path = f"{directory}/{filename}"
        return await self._get_bytes(
            f"/gopro/media/thumbnail?path={path}")

    async def download_file(self, directory: str, filename: str,
                            dest_path: str, progress_cb=None) -> bool:
        """Stream a media file to disk.  Calls progress_cb(done, total)
        periodically if provided (on the async thread)."""
        if not self._client:
            return False
        try:
            url = f"{self._base}/videos/DCIM/{directory}/{filename}"
            async with self._client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return False
                total = int(resp.headers.get("content-length", 0))
                done = 0
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)
                        done += len(chunk)
                        if progress_cb and total > 0:
                            progress_cb(done, total)
            return True
        except Exception as e:
            logger.info("GoPro download error: %s/%s → %s",
                        directory, filename, e)
            return False

    async def delete_file(self, directory: str, filename: str) -> bool:
        """Delete a single media file from the SD card."""
        path = f"{directory}/{filename}"
        return await self._get(f"/gopro/media/delete/file?path={path}")

    async def delete_group(self, directory: str, filename: str) -> bool:
        """Delete a grouped/chaptered media item by its first file."""
        path = f"{directory}/{filename}"
        return await self._get(
            f"/gp/gpControl/command/storage/delete/group?p={path}")

    # ── Preset helpers ───────────────────────────────

    @staticmethod
    def normalize_presets(data: dict, target_group: int = 1000) -> tuple[list[dict], int]:
        """Normalize preset status from GoPro API format.

        Returns (presets, active_preset_id).
        """
        if not isinstance(data, dict):
            return [], -1

        # Mock format: {"presets": [...], "active_preset_id": N}
        if "presets" in data:
            return data.get("presets", []), data.get("active_preset_id", -1)

        # Real GoPro API: {"presetGroupArray": [{id, presetArray, ...}]}
        groups = (data.get("presetGroupArray") or data.get("groups")
                  or data.get("preset_group_array") or [])
        for g in groups:
            if not isinstance(g, dict):
                continue
            gid = g.get("id", 0)
            # GoPro returns string IDs like "PRESET_GROUP_ID_VIDEO"
            if isinstance(gid, str):
                gid = {"PRESET_GROUP_ID_VIDEO": 1000,
                       "PRESET_GROUP_ID_PHOTO": 1001,
                       "PRESET_GROUP_ID_TIMELAPSE": 1002}.get(gid, -1)
            if gid == target_group:
                raw = (g.get("presetArray") or g.get("preset_array")
                       or g.get("presets") or [])
                presets = [
                    {
                        "id": p.get("id", -1),
                        "title": (
                            p.get("customName") or p.get("title") or ""
                            or _resolve_title(p.get("titleId") or p.get("title_id", -1))
                        ),
                        "title_id": p.get("titleId") or p.get("title_id", -1),
                        "icon": p.get("icon", -1),
                        "mode": p.get("mode", -1),
                        "is_visible": p.get("is_visible", True),
                        "setting_array": p.get("settingArray", []),
                        "summary": preset_summary(p.get("settingArray", [])),
                    }
                    for p in raw if isinstance(p, dict)
                ]
                active = g.get("active_preset_id", -1)
                return presets, active

        return [], -1

    # ── Internal ─────────────────────────────────────

    async def _get(self, path: str) -> bool:
        if not self._client:
            return False
        try:
            r = await self._client.get(f"{self._base}{path}")
            if r.status_code != 200:
                logger.info("GoPro HTTP %d: %s %s  body=%s",
                           r.status_code, "GET", path, r.text[:200] if r.text else "")
            return r.status_code == 200
        except Exception as e:
            logger.info("GoPro HTTP error: GET %s → %s", path, e)
            return False

    async def _post(self, path: str) -> bool:
        if not self._client:
            return False
        try:
            r = await self._client.post(f"{self._base}{path}")
            if r.status_code != 200:
                logger.info("GoPro HTTP %d: %s %s  body=%s",
                           r.status_code, "POST", path, r.text[:200] if r.text else "")
            return r.status_code == 200
        except Exception as e:
            logger.info("GoPro HTTP error: POST %s → %s", path, e)
            return False

    async def _get_bytes(self, path: str) -> bytes | None:
        if not self._client:
            return None
        try:
            r = await self._client.get(f"{self._base}{path}")
            if r.status_code == 200:
                return r.content
        except Exception as e:
            logger.debug("GoPro HTTP bytes error: %s → %s", path, e)
        return None

    async def _get_json(self, path: str) -> dict | None:
        if not self._client:
            return None
        try:
            r = await self._client.get(f"{self._base}{path}")
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug("GoPro HTTP json error: %s → %s", path, e)
        return None


def _safe_get(d, key, default):
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)

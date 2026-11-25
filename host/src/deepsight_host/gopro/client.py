"""Open GoPro HTTP client for MISSION 1 PRO through the Pi gateway."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from deepsight_host.gopro.profile import (
    CAPTURE_MODE_IDS,
    GENERAL_PRESET_GROUP,
    LEGACY_PRESET_GROUPS,
    MISSION_1_PRO_LABS_FIRMWARE,
    MISSION_1_PRO_MIN_OPEN_GOPRO_FIRMWARE,
    MISSION_1_PRO_MODEL,
    CameraCompatibility,
    firmware_version_tuple,
    is_mission_1_pro,
    normalize_model_name,
)
from deepsight_host.gopro.settings_decode import preset_summary

logger = logging.getLogger("host.gopro")

# Preset title names from GoPro API (int and string forms)
PRESET_TITLES: dict = {
    0: "Activity", 1: "Standard", 2: "Cinematic", 3: "Photo",
    4: "Live Burst", 5: "Burst", 6: "Night", 7: "TimeWarp",
    8: "Time Lapse", 9: "Night Lapse", 10: "Video", 11: "Slo-Mo",
    33: "Looping", 46: "HDR", 48: "Log", 58: "Basic",
    59: "Ultra Slo-Mo", 76: "Star Trails", 77: "Light Painting",
    78: "Light Trail", 106: "Burst Slo-Mo", 131: "Time Lapse Video",
    132: "Time Lapse Photo", 133: "Night Lapse Video",
    134: "Night Lapse Photo", 143: "SuperView",
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
    remaining_video_time_s: int = 0
    recording_duration_s: int = 0
    sd_write_error: bool = False
    sd_card_errors: int = 0
    usb_connected: bool = False


class GoProClient:
    """Async HTTP client for GoPro camera (via Pi TCP forward).

    GoPro checks the HTTP Host header and rejects requests with a
    different host.  ``real_host`` is set as the Host header so GoPro
    accepts the request even though the actual TCP connection goes to
    the Pi's forwarded port.
    """

    def __init__(
        self,
        base_url: str = "http://192.168.3.161:8080",
        real_host: str = "172.25.132.51",
        expected_model: str = MISSION_1_PRO_MODEL,
        expected_labs_version: str = MISSION_1_PRO_LABS_FIRMWARE,
        preset_order: list[str] | None = None,
    ):
        self._base = base_url
        self._real_host = real_host
        self._preset_order = preset_order or []
        self._expected_model = expected_model
        self._expected_labs_version = expected_labs_version
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

    async def keep_alive(self) -> bool:
        """Keep the Open GoPro control session alive."""
        return await self._get("/gopro/camera/keep_alive")

    async def claim_control(self, enable: bool = True) -> bool:
        """Claim or release camera UI control for this external client."""
        return await self._get(
            "/gopro/camera/control/set_ui_controller", params={"p": 2 if enable else 0})

    # ── Shutter ──────────────────────────────────────

    async def start_recording(self) -> bool:
        if not await self.wait_until_idle():
            return False
        return await self._get("/gopro/camera/shutter/start")

    async def stop_recording(self) -> bool:
        return await self._get("/gopro/camera/shutter/stop")

    async def stop_recording_and_wait(self, timeout: float = 15.0) -> bool:
        """Stop recording and wait until the camera has finalized the file."""
        status = await self.get_status()
        if not status.recording and not status.busy:
            return True
        if status.recording and not await self.stop_recording():
            return False
        return await self.wait_until_idle(timeout=timeout)

    async def wait_until_idle(self, timeout: float = 10.0) -> bool:
        """Wait for encoding and post-capture file activity to finish."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                status = await self.get_status()
            except ConnectionError:
                return False
            if not status.recording and not status.busy:
                return True
            await asyncio.sleep(0.25)
        return False

    # ── Stream ───────────────────────────────────────

    async def start_viewfinder(self, port: int = 8554) -> bool:
        """Start the camera's live preview (viewfinder) stream.

        GoPro sends MPEG-TS UDP to the source IP of this HTTP request
        on the specified port.  With Pi SNAT, GoPro sees the Pi's USB IP
        as the source, so UDP goes to Pi:port.  Pi's socat relays to Host.
        """
        return await self._get("/gopro/camera/stream/start", params={"port": port})

    async def stop_viewfinder(self) -> bool:
        """Stop the camera's live preview stream."""
        return await self._get("/gopro/camera/stream/stop")

    async def enable_wired_usb(self, enable: bool = True) -> bool:
        """Enable/disable wired USB camera control.

        Must be enabled before shutter/recording commands will work.
        """
        p = 1 if enable else 0
        return await self._get("/gopro/camera/control/wired_usb", params={"p": p})

    # ── Presets ──────────────────────────────────────

    async def load_preset(self, preset_id: int) -> bool:
        return await self._get("/gopro/camera/presets/load", params={"id": preset_id})

    async def load_preset_group(self, group_id: int) -> bool:
        return await self._get("/gopro/camera/presets/set_group", params={"id": group_id})

    async def get_preset_status(self, include_hidden: bool = False) -> dict | None:
        """Returns raw preset status from GoPro, or None."""
        data = await self._get_json(
            "/gopro/camera/presets/get",
            params={"include-hidden": 1 if include_hidden else 0},
        )
        if data is None:
            return None
        if _first_present(data, "activePresetId", "active_preset_id") is None:
            state = await self._get_json("/gopro/camera/state") or {}
            status = state.get("status", state)
            active = _safe_get(status, "97", None)
            if active is not None:
                data = dict(data)
                data["activePresetId"] = active
        if self._preset_order:
            rank = {name: index for index, name in enumerate(self._preset_order)}
            for group in data.get("presetGroupArray", []):
                group.get("presetArray", []).sort(
                    key=lambda p: rank.get(p.get("customName", ""), len(rank)))
        return data

    async def set_capture_mode(self, mode: str) -> bool:
        """Switch a MISSION camera's top-level mode using its dynamic presets."""
        mode = mode.lower()
        if mode not in CAPTURE_MODE_IDS:
            raise ValueError(f"Unsupported capture mode: {mode}")
        data = await self.get_preset_status(include_hidden=True)
        if data:
            presets, _ = self.normalize_presets(data, target_group=GENERAL_PRESET_GROUP)
            preferred = CAPTURE_MODE_IDS[mode]
            for mode_id in preferred:
                match = next((p for p in presets if _enum_int(p.get("mode")) == mode_id), None)
                if match is not None:
                    return await self.load_preset(int(match["id"]))
        # Older cameras expose mode as separate preset groups. This fallback
        # keeps the wrapper useful during bench tests with legacy fixtures.
        return await self.load_preset_group(LEGACY_PRESET_GROUPS[mode])

    async def ensure_video_mode(self) -> bool:
        """Keep an existing MISSION video preset, switching only from non-video."""
        data = await self.get_preset_status(include_hidden=True)
        if data:
            presets, active = self.normalize_presets(data, target_group=GENERAL_PRESET_GROUP)
            current = next((preset for preset in presets if preset.get("id") == active), None)
            if current is not None and _enum_int(current.get("mode")) in CAPTURE_MODE_IDS["video"]:
                return True
        return await self.set_capture_mode("video")

    # ── Settings ─────────────────────────────────────

    async def set_setting(self, setting_id: str | int, value: str) -> bool:
        if not await self.wait_until_idle():
            return False
        return await self._get(
            "/gopro/camera/setting",
            params={"setting": setting_id, "option": value},
        )

    async def get_setting(self, setting_id: str | int) -> int | None:
        """Read current option value for a numeric setting ID."""
        queried = await self._get_json(
            "/gopro/camera/setting", params={"setting": setting_id})
        if queried is not None and queried.get("option") is not None:
            return int(queried["option"])

        # Some firmware versions omit query responses but include the value in
        # camera state, so retain a read-only fallback.
        data = await self.get_all_settings()
        settings = data.get("settings", data.get("setting", {}))
        if isinstance(settings, dict):
            value = _safe_get(settings, str(setting_id), None)
            if value is not None:
                return int(value)
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

        Status IDs (MISSION 1 PRO):
          2: internal_battery_bars (0-4)
          6: overheating (1=yes)
          8: busy (1=yes)
          10: encoding (1=recording)
          35: remaining_video_time_seconds
          54: sd_card_remaining_kilobytes
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
        sd_kb = int(_safe_get(status, '54', 0))
        return GoProStatus(
            recording=bool(int(_safe_get(status, '10', 0))),
            battery_pct=battery_pct,
            storage_gb_free=float(sd_kb) / 1e6 if sd_kb > 0 else 0.0,
            model_name=str(data.get("model_name", "")),
            busy=bool(int(_safe_get(status, '8', 0))),
            overheating=bool(int(_safe_get(status, '6', 0))),
            remaining_video_time_s=int(_safe_get(status, '35', 0)),
            recording_duration_s=int(_safe_get(status, '13', 0)),
            sd_write_error=bool(int(_safe_get(status, '111', 0))),
            sd_card_errors=int(_safe_get(status, '112', 0)),
            usb_connected=bool(int(_safe_get(status, '115', 0))),
        )

    async def get_camera_info(self) -> dict:
        data = await self._get_json("/gopro/camera/info")
        return data if data else {}

    async def get_capabilities(self) -> dict:
        """Read the MISSION camera capability descriptor."""
        return await self._get_json("/gopro/camera/capabilities") or {}

    async def get_open_gopro_version(self) -> str:
        data = await self._get_json("/gopro/version") or {}
        return str(data.get("version", ""))

    async def get_compatibility(self) -> CameraCompatibility:
        """Inspect model, firmware and protocol without mutating the camera."""
        info = await self.get_camera_info()
        capabilities = await self.get_capabilities()
        firmware = str(info.get("firmware_version", ""))
        firmware_tuple = firmware_version_tuple(firmware)
        minimum_tuple = firmware_version_tuple(MISSION_1_PRO_MIN_OPEN_GOPRO_FIRMWARE)
        labs_tuple = firmware_version_tuple(self._expected_labs_version)
        protocol = capabilities.get("protocol", {})
        return CameraCompatibility(
            model_name=str(info.get("model_name", "")),
            firmware_version=firmware,
            open_gopro_version=await self.get_open_gopro_version(),
            capabilities_schema=str(capabilities.get("schemaVersion", "")),
            supports_two_byte_ids=bool(protocol.get("supports_2byte_ids", False)),
            model_supported=(
                is_mission_1_pro(info.get("model_name", ""))
                if is_mission_1_pro(self._expected_model)
                else normalize_model_name(info.get("model_name", ""))
                == normalize_model_name(self._expected_model)
            ),
            open_gopro_supported=bool(firmware_tuple and firmware_tuple >= minimum_tuple),
            labs_version_current=bool(firmware_tuple and firmware_tuple >= labs_tuple),
        )

    # ── Probe ────────────────────────────────────────

    async def probe_setting(
        self, setting_id: str, probe_option: str = "65535"
    ) -> dict:
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

        if not self._client:
            return result

        try:
            response = await self._client.get(
                f"{self._base}/gopro/camera/setting",
                params={"setting": sid, "option": probe_option},
            )
            payload = response.json() if response.content else {}
            supported = payload.get("supported_options")
            if isinstance(supported, list):
                result["available"] = [
                    {
                        "id": option.get("id"),
                        "name": option.get("display_name", str(option.get("id", ""))),
                    }
                    for option in supported if isinstance(option, dict)
                ]
            elif response.status_code == 403:
                result["available"] = []
            if response.status_code == 200:
                # The probe value was accepted, so immediately restore the
                # original option before returning to the UI.
                result["probe_changed"] = True
                if current is not None:
                    await self.set_setting(sid, str(current))
        except Exception as exc:
            logger.debug("GoPro setting probe failed for %s: %s", sid, exc)

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
    def normalize_presets(
        data: dict, target_group: int = GENERAL_PRESET_GROUP
    ) -> tuple[list[dict], int]:
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
        selected_group = None
        for g in groups:
            if not isinstance(g, dict):
                continue
            gid = g.get("id", 0)
            # GoPro returns string IDs like "PRESET_GROUP_ID_VIDEO"
            if isinstance(gid, str):
                gid = {"PRESET_GROUP_ID_VIDEO": 1000,
                       "PRESET_GROUP_ID_PHOTO": 1001,
                       "PRESET_GROUP_ID_TIMELAPSE": 1002,
                       "PRESET_GROUP_ID_GENERAL": 2000}.get(gid, -1)
            if gid == target_group:
                selected_group = g
                break
        if selected_group is None and groups:
            selected_group = next((g for g in groups if isinstance(g, dict)), None)
        if selected_group is not None:
            g = selected_group
            raw = (g.get("presetArray") or g.get("preset_array")
                   or g.get("presets") or [])
            presets = [
                {
                    "id": p.get("id", -1),
                    "title": (
                        p.get("customName") or p.get("custom_name")
                        or p.get("title")
                        or _resolve_title(
                            _first_present(p, "titleId", "title_id", default=-1))
                    ),
                    "title_id": _first_present(
                        p, "titleId", "title_id", default=-1),
                    "icon": p.get("icon", -1),
                    "mode": p.get("mode", -1),
                    "is_visible": bool(_first_present(
                        p, "isVisible", "is_visible", default=1)),
                    "setting_array": _first_present(
                        p, "settingArray", "setting_array", default=[]),
                    "summary": preset_summary(_first_present(
                        p, "settingArray", "setting_array", default=[])),
                }
                for p in raw if isinstance(p, dict)
            ]
            active = _first_present(
                g, "activePresetId", "active_preset_id", default=-1)
            if active == -1:
                active = _first_present(
                    data, "activePresetId", "active_preset_id", default=-1)
            return presets, active

        return [], -1

    # ── Internal ─────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None) -> bool:
        if not self._client:
            return False
        try:
            r = await self._client.get(f"{self._base}{path}", params=params)
            if r.status_code != 200:
                logger.info("GoPro HTTP %d: %s %s  body=%s",
                           r.status_code, "GET", path, r.text[:200] if r.text else "")
            return r.status_code == 200
        except Exception as e:
            logger.info("GoPro HTTP error: GET %s → %s", path, e)
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

    async def _get_json(self, path: str, params: dict | None = None) -> dict | None:
        if not self._client:
            return None
        try:
            r = await self._client.get(f"{self._base}{path}", params=params)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug("GoPro HTTP json error: %s → %s", path, e)
        return None


def _safe_get(d, key, default):
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)


def _first_present(d: dict, *keys: str, default=None):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _enum_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.lstrip("-").isdigit():
            return int(value)
        names = {
            "FLAT_MODE_VIDEO": 12,
            "FLAT_MODE_TIME_LAPSE_VIDEO": 13,
            "FLAT_MODE_PHOTO_SINGLE": 16,
            "FLAT_MODE_PHOTO": 17,
            "FLAT_MODE_PHOTO_NIGHT": 18,
            "FLAT_MODE_PHOTO_BURST": 19,
            "FLAT_MODE_TIME_LAPSE_PHOTO": 20,
            "FLAT_MODE_NIGHT_LAPSE_PHOTO": 21,
            "FLAT_MODE_TIME_WARP_VIDEO": 24,
            "FLAT_MODE_NIGHT_LAPSE_VIDEO": 26,
            "FLAT_MODE_SLOMO": 27,
            "FLAT_MODE_VIDEO_STAR_TRAIL": 29,
            "FLAT_MODE_VIDEO_LIGHT_PAINTING": 30,
            "FLAT_MODE_VIDEO_LIGHT_TRAIL": 31,
            "FLAT_MODE_VIDEO_BURST_SLOMO": 32,
            "FLAT_MODE_VIDEO_LOW_LIGHT": 36,
        }
        return names.get(value)
    return None

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
            timeout=httpx.Timeout(8.0), headers=headers)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_ready(self) -> bool:
        """Check if GoPro is reachable."""
        return await self._get("/gopro/camera/state")

    # ── Shutter ──────────────────────────────────────

    async def start_recording(self) -> bool:
        return await self._get("/gopro/camera/shutter/start?enable=1")

    async def stop_recording(self) -> bool:
        return await self._get("/gopro/camera/shutter/start?enable=0")

    # ── Stream ───────────────────────────────────────

    async def start_viewfinder(self, port: int = 8554) -> bool:
        """Start the camera's live preview (viewfinder) stream.

        GoPro sends MPEG-TS UDP to the source IP of this HTTP request
        on the specified port.  With Pi SNAT, GoPro sees the Pi's USB IP
        as the source, so UDP goes to Pi:port.  Pi's socat relays to Host.
        """
        return await self._get(f"/gopro/camera/stream/start?port={port}")

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
        """
        data = await self._get_json("/gopro/camera/state")
        if not data:
            raise ConnectionError("GoPro unreachable")
        status = data.get("status", data)
        return GoProStatus(
            recording=bool(_safe_get(status, "encoding_active", 0)),
            battery_pct=float(_safe_get(status, "internal_battery_percentage", 0)),
            storage_gb_free=float(_safe_get(status, "sd_card_remaining", 0)) / 1e9,
            model_name=str(data.get("model_name", "")),
            busy=bool(_safe_get(status, "system_busy", 0)),
            overheating=bool(_safe_get(status, "overheating", 0)),
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
            return r.status_code == 200
        except Exception as e:
            logger.debug("GoPro HTTP error: %s %s → %s", path, type(e).__name__, e)
            return False

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

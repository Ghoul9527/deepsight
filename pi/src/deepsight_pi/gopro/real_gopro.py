"""Real GoPro controller — wired USB-C HTTP API.

Physical topology:
  GoPro MicroHDMI ──▶ Capture dongle ──▶ Pi USB 3.0  (video)
  GoPro USB-C ──▶ Pi USB 3.0                        (control)

Camera must be set to "GoPro Connect" mode via Preferences.
This exposes a USB Ethernet interface (usb0) with HTTP API access.
No BLE. No WiFi. HDMI output and USB control coexist on HERO13.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time

from deepsight_pi.gopro.base import (
    GoProController, GoProStatus, MediaFile, MediaList,
)

logger = logging.getLogger("pi.gopro.real")

# GoPro USB Ethernet defaults
GOPRO_USB_IFACE = "usb0"
GOPRO_HTTP_PORT = 8080
KEEP_ALIVE_INTERVAL = 120  # ping camera every 2 min to keep WiFi alive
MAX_STARTUP_WAIT = 10  # seconds to wait for USB interface DHCP


class RealGoPro(GoProController):
    """Wired USB-C GoPro controller.

    Usage:
        gopro = RealGoPro()
        await gopro.open()
        await gopro.start_recording()
        ...
        await gopro.close()
    """

    def __init__(self, usb_iface: str = GOPRO_USB_IFACE,
                 wifi_ssid: str = "", wifi_password: str = ""):
        self._usb_iface = usb_iface
        self._wifi_ssid = wifi_ssid
        self._wifi_password = wifi_password
        self._gopro = None
        self._connected = False
        self._keep_alive_task: asyncio.Task | None = None
        self._gopro_ip: str | None = None
        self._using_wifi = False

    # ── Properties ───────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Connection ───────────────────────────────────

    async def open(self) -> bool:
        """Open wired connection to GoPro via USB-C Ethernet.

        Tries USB Ethernet first (GoPro Connect mode).
        Falls back to WiFi direct if USB is unavailable.
        """
        # Try USB Ethernet first
        if await self._connect_usb():
            self._using_wifi = False
            self._keep_alive_task = asyncio.create_task(self._periodic_keep_alive())
            return True

        # Fall back to WiFi if configured
        if self._wifi_ssid:
            logger.info("USB not available, trying WiFi...")
            if await self._connect_wifi():
                self._using_wifi = True
                self._keep_alive_task = asyncio.create_task(self._periodic_keep_alive())
                return True

        logger.error("Cannot connect to GoPro: no USB Ethernet or WiFi AP found")
        return False

    async def _connect_usb(self) -> bool:
        """Connect to GoPro HTTP API over USB Ethernet (GoPro Connect mode).

        The camera must be in GoPro Connect mode (Preferences → USB → GoPro Connect).
        This creates a usb0 network interface with IP from camera's DHCP server.
        HDMI output and USB control coexist on HERO13 in this mode.
        """
        try:
            # Find GoPro IP on USB Ethernet interface
            gopro_ip = await self._discover_gopro_usb_ip()
            if not gopro_ip:
                logger.debug("GoPro USB Ethernet not found on %s", self._usb_iface)
                return False

            # Verify HTTP API is reachable
            if not await self._check_http_api(gopro_ip):
                logger.debug("GoPro HTTP API not reachable at %s:%d",
                             gopro_ip, GOPRO_HTTP_PORT)
                return False

            self._gopro_ip = gopro_ip
            self._gopro = _GoProHTTPClient(gopro_ip, GOPRO_HTTP_PORT)
            await self._gopro.open()
            self._connected = True
            logger.info("GoPro connected via USB Ethernet at %s:%d",
                        gopro_ip, GOPRO_HTTP_PORT)
            return True

        except Exception as e:
            logger.debug("USB connection attempt failed: %s", e)
            return False

    async def _discover_gopro_usb_ip(self) -> str | None:
        """Discover GoPro's IP address on the USB Ethernet interface.

        GoPro runs a DHCP server; the Pi gets an IP via DHCP on usb0.
        The GoPro itself is typically at the gateway address.

        Returns:
            str: GoPro IP address, or None if not found.
        """
        # Wait briefly for DHCP to settle
        for _ in range(MAX_STARTUP_WAIT):
            ip_info = await self._get_iface_info(self._usb_iface)
            if ip_info and ip_info.get("inet"):
                break
            await asyncio.sleep(1.0)

        if not ip_info or not ip_info.get("inet"):
            logger.debug("No IP on %s — is GoPro in GoPro Connect mode?",
                         self._usb_iface)
            return None

        # The GoPro is usually the gateway on the USB network
        gateway = ip_info.get("gateway", "")
        if gateway and await self._check_http_api(gateway):
            return gateway

        # Try common GoPro USB IPs
        candidates = [
            f"172.20.{x}.1" for x in range(16, 32)
        ] + [
            f"172.28.{x}.1" for x in range(0, 16)
        ]
        for ip in candidates:
            if await self._check_http_api(ip):
                return ip

        return None

    async def _get_iface_info(self, iface: str) -> dict:
        """Get IP info for a network interface via 'ip' command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "-4", "-j", "addr", "show", iface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=3.0
            )
            if proc.returncode != 0:
                return {}

            import json
            data = json.loads(stdout)
            if not data:
                return {}

            addr_info = data[0].get("addr_info", [])
            result = {}
            for entry in addr_info:
                if entry.get("family") == "inet":
                    result["inet"] = entry.get("local", "")
                    result["gateway"] = ""  # need 'ip route' for gateway
                    break

            # Get gateway via 'ip route'
            if result.get("inet"):
                route_proc = await asyncio.create_subprocess_exec(
                    "ip", "-4", "route", "show", "dev", iface, "default",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                route_stdout, _ = await asyncio.wait_for(
                    route_proc.communicate(), timeout=3.0
                )
                if route_proc.returncode == 0 and route_stdout:
                    m = re.search(r"via\s+([\d.]+)", route_stdout.decode())
                    if m:
                        result["gateway"] = m.group(1)

            return result
        except Exception:
            return {}

    async def _check_http_api(self, ip: str) -> bool:
        """Quick check if a GoPro HTTP API is reachable at the given IP."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((ip, GOPRO_HTTP_PORT))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _connect_wifi(self) -> bool:
        """Fallback: connect to GoPro WiFi AP directly via nmcli."""
        if not self._wifi_ssid:
            return False

        try:
            # Ensure WiFi is unblocked
            subprocess.run(
                ["sudo", "rfkill", "unblock", "wifi"],
                capture_output=True, timeout=5,
            )

            # Check if already connected
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "connection", "show"],
                capture_output=True, text=True, timeout=5,
            )
            if self._wifi_ssid not in result.stdout:
                logger.info("Connecting to GoPro WiFi AP: %s", self._wifi_ssid)
                subprocess.run(
                    ["sudo", "nmcli", "device", "wifi", "connect",
                     self._wifi_ssid, "password", self._wifi_password,
                     "ifname", "wlan0"],
                    capture_output=True, text=True, timeout=15,
                )

            # GoPro WiFi AP is at fixed IP 10.5.5.9
            gopro_ip = "10.5.5.9"
            if not await self._check_http_api(gopro_ip):
                logger.error("GoPro HTTP API not reachable over WiFi at %s", gopro_ip)
                return False

            self._gopro_ip = gopro_ip
            self._gopro = _GoProHTTPClient(gopro_ip, GOPRO_HTTP_PORT)
            await self._gopro.open()
            self._connected = True
            logger.info("GoPro connected via WiFi AP at %s:%d",
                        gopro_ip, GOPRO_HTTP_PORT)
            return True

        except Exception as e:
            logger.error("WiFi connection failed: %s", e)
            return False

    async def _periodic_keep_alive(self):
        """Send periodic requests to prevent GoPro auto-shutdown."""
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)
        while self._connected:
            try:
                await self.get_battery_pct()
            except Exception:
                pass
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)

    async def close(self):
        self._connected = False
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
        if self._gopro is not None:
            try:
                await self._gopro.close()
            except Exception as e:
                logger.debug("GoPro close error: %s", e)
            finally:
                self._gopro = None

    async def is_ready(self) -> bool:
        if self._gopro is None:
            return False
        try:
            return await self._gopro.is_ready()
        except Exception:
            return False

    # ── Shutter ──────────────────────────────────────

    async def start_recording(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(
            _Toggle.ENABLE))

    async def stop_recording(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(
            _Toggle.DISABLE))

    async def take_photo(self) -> bool:
        return await self._http(lambda g: g.http_command.set_shutter(
            _Toggle.ENABLE))

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
        return await self._http(lambda g: _set_attr(g.http_setting, name, value))

    # ── Status ───────────────────────────────────────

    async def get_status(self) -> GoProStatus:
        try:
            resp = await self._gopro.http_command.get_camera_state()
            s = resp.data if hasattr(resp, 'data') else {}
        except Exception:
            return GoProStatus()

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
            usb_connected=True,
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
        from pathlib import Path
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        fname = remote_path.split("/")[-1]
        local = str(Path(local_dir) / fname)

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
        return await self._http(lambda g: g.http_command.delete_all_media())

    async def get_thumbnail(self, remote_path: str) -> bytes | None:
        resp = await self._http(
            lambda g: g.http_command.get_thumbnail(url=remote_path))
        return resp.data if hasattr(resp, 'data') else None

    async def get_telemetry(self, remote_path: str) -> bytes | None:
        resp = await self._http(
            lambda g: g.http_command.get_telemetry(url=remote_path))
        return resp.data if hasattr(resp, 'data') else None

    # ── Turbo transfer ───────────────────────────────

    async def set_turbo_mode(self, enable: bool) -> bool:
        return await self._http(
            lambda g: g.http_command.set_turbo_mode(1 if enable else 0))

    # ── Power ────────────────────────────────────────

    async def power_off(self) -> bool:
        return await self._http(lambda g: g.http_command.power_down())

    async def sleep(self) -> bool:
        return await self._http(lambda g: g.http_command.sleep())

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
        return {}

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


# ── Toggle enum (avoids importing open-gopro just for this) ──

class _Toggle:
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"


# ── Direct HTTP Client (works over USB Ethernet or WiFi) ──

class _GoProHTTPClient:
    """Minimal async HTTP client for GoPro HTTP API.

    Works over USB Ethernet (GoPro Connect) or WiFi AP.
    Wraps aiohttp to provide http_command/http_setting interface.
    """

    def __init__(self, host: str, port: int):
        self._base = f"http://{host}:{port}"
        self._session = None

    async def open(self):
        import aiohttp
        self._session = aiohttp.ClientSession()
        self.http_command = _HTTPCommands(self._session, self._base)
        self.http_setting = _HTTPSettings(self._session, self._base)

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def is_ready(self) -> bool:
        return self._session is not None


class _HTTPCommands:
    """HTTP command wrapper matching open-gopro's http_command interface."""

    def __init__(self, session, base_url: str):
        self._s = session
        self._b = base_url

    async def set_shutter(self, shutter) -> bool:
        val = 1 if str(shutter).endswith("ENABLE") else 0
        return await self._get(f"/gopro/camera/shutter/start?enable={val}")

    async def power_down(self) -> bool:
        return await self._get("/gopro/camera/power_off")

    async def sleep(self) -> bool:
        return await self._get("/gopro/camera/sleep")

    async def reboot(self) -> bool:
        return await self._get("/gopro/camera/restart")

    async def load_preset(self, preset) -> bool:
        return await self._get(f"/gopro/camera/presets/load?id={preset}")

    async def load_preset_group(self, group) -> bool:
        return await self._get(f"/gopro/camera/presets/set_group?id={group}")

    async def set_date_time_tz_dst(self) -> bool:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        dt = now.strftime("%Y_%m_%d_%H_%M_%S")
        return await self._get(f"/gopro/camera/date_time?date={dt}")

    async def get_camera_state(self):
        return await self._get_json("/gopro/camera/state")

    async def get_camera_info(self):
        return await self._get_json("/gopro/camera/info")

    async def get_media_list(self):
        return await self._get_json("/gopro/media/list")

    async def get_last_captured_media(self):
        return await self._get_json("/gopro/media/last_captured")

    async def get_preset_status(self):
        return await self._get_json("/gopro/camera/presets/get")

    async def add_file_hilight(self) -> bool:
        return await self._get("/gopro/media/hilight/file?path=last")

    async def set_turbo_mode(self, mode: int) -> bool:
        return await self._get(f"/gopro/camera/turbo?mode={mode}")

    async def download_file(self, url: str):
        return await self._get_json(url)

    async def delete_file(self, url: str) -> bool:
        async with self._s.delete(f"{self._b}{url}") as resp:
            return resp.status == 200

    async def delete_all_media(self) -> bool:
        return await self._get("/gopro/media/delete_all")

    async def get_thumbnail(self, url: str):
        async with self._s.get(f"{self._b}{url}") as resp:
            return _FakeResponse(await resp.read())

    async def get_telemetry(self, url: str):
        async with self._s.get(f"{self._b}{url}") as resp:
            return _FakeResponse(await resp.read())

    async def get_date_time(self):
        return await self._get_json("/gopro/camera/date_time")

    async def _get(self, path: str) -> bool:
        try:
            async with self._s.get(f"{self._b}{path}") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def _get_json(self, path: str):
        try:
            async with self._s.get(f"{self._b}{path}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return _FakeResponse(data)
        except Exception:
            pass
        return None


class _HTTPSettings:
    """HTTP settings wrapper matching open-gopro's http_setting interface."""

    def __init__(self, session, base_url: str):
        self._s = session
        self._b = base_url
        for name in ["video_resolution", "frame_rate", "video_lens",
                      "hypersmooth", "video_bit_rate", "max_lens_mod",
                      "video_aspect_ratio", "profiles", "bit_depth",
                      "media_format"]:
            setattr(self, name, _SettingProxy(session, base_url, name))


class _SettingProxy:
    def __init__(self, session, base_url: str, name: str):
        self._s = session
        self._b = base_url
        self._name = name

    async def set(self, value) -> bool:
        try:
            async with self._s.get(
                f"{self._b}/gopro/camera/setting?setting={self._name}&value={value}"
            ) as resp:
                return resp.status == 200
        except Exception:
            return False


class _FakeResponse:
    """Minimal object mimicking open-gopro's GoProResp for code compatibility."""
    def __init__(self, data):
        self.data = data


# ── Module-level helpers ─────────────────────────────

def _set_attr(obj, name: str, value):
    parts = name.split(".")
    target = obj
    for p in parts[:-1]:
        target = getattr(target, p)
    attr = getattr(target, parts[-1])
    return attr.set(value)


def _safe_get(d, key, default):
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)

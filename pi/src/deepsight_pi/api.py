"""FastAPI / WebSocket control API for the Pi node."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from deepsight_pi.config import PiConfig
from deepsight_shared.protocol import Message

logger = logging.getLogger("pi.api")

app = FastAPI(title="DeepSight Pi API")
_clients: list[WebSocket] = []


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    logger.info("WebSocket client connected")
    try:
        while True:
            data = await ws.receive_text()
            msg = Message.from_json(data)
            msg_bridge = _message_handler
            if msg_bridge:
                await msg_bridge(msg)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        _clients.remove(ws)


@app.get("/health")
async def get_health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    return {"status": "online", "node": "pi"}


@app.get("/gopro/status")
async def get_gopro_status():
    controller = _get_gopro()
    if controller is None:
        return {"error": "GoPro controller not available"}
    try:
        status = await controller.get_status()
        return {
            "connected": controller.connected,
            "recording": status.recording,
            "battery_pct": status.battery_pct,
            "storage_gb_total": status.storage_gb_total,
            "storage_gb_free": status.storage_gb_free,
            "mode": status.mode,
            "encoding": status.encoding,
            "busy": status.busy,
            "overheating": status.overheating,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/gopro/record/start")
async def gopro_start_recording():
    controller = _get_gopro()
    if controller is None:
        return {"error": "GoPro controller not available"}
    ok = await controller.start_recording()
    return {"success": ok}


@app.post("/gopro/record/stop")
async def gopro_stop_recording():
    controller = _get_gopro()
    if controller is None:
        return {"error": "GoPro controller not available"}
    ok = await controller.stop_recording()
    return {"success": ok}


@app.post("/gopro/connect")
async def gopro_connect():
    """Manually trigger GoPro connection (WiFi or USB)."""
    controller = _get_gopro()
    if controller is None:
        return {"error": "GoPro controller not available"}
    try:
        ok = await controller.open()
        return {"success": ok, "connected": controller.connected}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/gopro/scan")
async def gopro_scan_wifi():
    """Scan for GoPro WiFi AP from Pi's wlan0."""
    import subprocess
    try:
        # Ensure WiFi is unblocked
        subprocess.run(
            ["sudo", "rfkill", "unblock", "wifi"],
            capture_output=True, timeout=5,
        )
        # Scan
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY",
             "device", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=15,
        )
        networks = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":")
                if len(parts) >= 2:
                    networks.append({
                        "ssid": parts[0],
                        "signal": parts[1] if len(parts) > 1 else "",
                    })
        # Filter for GoPro-like SSIDs
        gopro_nets = [n for n in networks
                      if "GP" in n["ssid"].upper() or "GOPRO" in n["ssid"].upper()]
        return {
            "success": True,
            "total_networks": len(networks),
            "gopro_networks": gopro_nets,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/stream/mode/viewfinder")
async def stream_mode_viewfinder():
    """Switch to Viewfinder preview mode (720p-class, low latency)."""
    manager = _get_stream_manager()
    if manager is None:
        return {"error": "Stream manager not available"}
    try:
        await manager.start_viewfinder(_get_stream_relay())
        return {"success": True, "mode": "viewfinder"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/stream/mode/webcam")
async def stream_mode_webcam():
    """Switch to Webcam preview mode (1080p, higher quality)."""
    manager = _get_stream_manager()
    if manager is None:
        return {"error": "Stream manager not available"}
    try:
        await manager.start_webcam(_get_stream_relay())
        return {"success": True, "mode": "webcam"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/stream/stop")
async def stream_stop():
    """Stop the GoPro preview stream."""
    manager = _get_stream_manager()
    if manager is None:
        return {"error": "Stream manager not available"}
    try:
        await manager.stop()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/stream/status")
async def stream_status():
    """Get current stream mode and status."""
    manager = _get_stream_manager()
    if manager is None:
        return {"mode": None, "running": False}
    return {
        "mode": manager.mode,
        "running": manager.running,
        "pcr_latency_ms": manager.pcr_latency_ms,
    }


@app.get("/gopro/media")
async def gopro_list_media():
    controller = _get_gopro()
    if controller is None:
        return {"error": "GoPro controller not available"}
    media_list = await controller.list_media()
    return {
        "total_count": media_list.total_count,
        "total_size_bytes": media_list.total_size_bytes,
        "files": [
            {
                "name": f.name,
                "path": f.path,
                "size_bytes": f.size_bytes,
                "duration_s": f.duration_s,
                "resolution": f.resolution,
            }
            for f in media_list.files
        ],
    }


_message_handler = None
_gopro_controller = None
_stream_manager = None
_stream_relay = None


def _get_gopro():
    return _gopro_controller


def _get_stream_manager():
    return _stream_manager


def _get_stream_relay():
    return _stream_relay


class PiApi:
    def __init__(self, config: PiConfig, node):
        self._config = config
        self._node = node
        self._server = None
        global _message_handler, _gopro_controller, _stream_manager, _stream_relay
        _gopro_controller = node.gopro
        _stream_manager = getattr(node, 'stream_manager', None)
        _stream_relay = getattr(node, 'stream_relay', None)

    def set_message_handler(self, handler):
        global _message_handler
        _message_handler = handler

    async def start(self):
        self._server = uvicorn.Server(
            config=uvicorn.Config(
                app, host="0.0.0.0", port=self._config.ws_port,
                log_level="info",
            )
        )
        asyncio.create_task(self._server.serve())
        logger.info("Pi API started on :%d", self._config.ws_port)

    async def stop(self):
        if self._server:
            self._server.should_exit = True

    async def broadcast(self, msg: Message):
        for client in _clients:
            try:
                await client.send_text(msg.to_json())
            except Exception:
                pass

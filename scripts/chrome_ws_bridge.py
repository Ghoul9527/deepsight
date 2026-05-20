#!/usr/bin/env python3
"""Chrome WebSocket Gamepad Bridge for DeepSight Host.

Starts an HTTP + WebSocket server that serves the gamepad tester page
and receives gamepad state via Web Gamepad API over WebSocket.

Chrome must be used — it has the signing/entitlements that macOS 26 requires
for USB HID gamepad access.

Output format (stdout, one JSON line per frame):
  {"ts": 1234567890.123, "axes": [lx,ly,rx,ry,lt,rt], "buttons": [0,1,...], "hat": [x,y]}
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import threading
import time

import websockets
from websockets.asyncio.server import serve

PORT = 9877
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(SCRIPT_DIR, "gamepad_tester.html")

_gpad_state: dict = {"axes": [0.0] * 6, "buttons": [0] * 13, "hat": [0, 0]}
_gpad_lock = threading.Lock()
_server_ready = threading.Event()
_running = True
_ws_recv_count = 0

# Read the HTML file once at startup
with open(HTML_PATH, "r", encoding="utf-8") as f:
    _HTML_CONTENT = f.read().encode("utf-8")


async def process_request(connection, request):
    """Serve the HTML page via HTTP, upgrade /ws to WebSocket."""
    if request.path == "/ws":
        # Let websockets handle the WebSocket upgrade
        return None
    # Serve the HTML page for everything else
    response = connection.respond(200, _HTML_CONTENT.decode("utf-8"))
    del response.headers["Content-Type"]
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


async def ws_handler(websocket):
    """Receive gamepad state from Chrome and update shared state."""
    global _ws_recv_count
    try:
        async for message in websocket:
            _ws_recv_count += 1
            try:
                data = json.loads(message)
                axes = data.get("axes", [0.0] * 6)
                if len(axes) < 6:
                    axes = axes + [0.0] * (6 - len(axes))
                buttons = data.get("buttons", [0] * 13)
                if len(buttons) < 13:
                    buttons = buttons + [0] * (13 - len(buttons))
                hat = data.get("hat", [0, 0])
                with _gpad_lock:
                    _gpad_state["axes"] = axes[:6]
                    _gpad_state["buttons"] = buttons[:13]
                    _gpad_state["hat"] = hat[:2]
            except Exception:
                pass
    except Exception:
        pass


async def main_async():
    global _running

    server = await serve(
        ws_handler,
        "127.0.0.1",
        PORT,
        ping_interval=None,
        process_request=process_request,
    )
    _server_ready.set()

    print(f"Chrome bridge: open http://localhost:{PORT} in Chrome", file=sys.stderr)
    sys.stderr.flush()

    while _running:
        await asyncio.sleep(0.004)
        with _gpad_lock:
            state = dict(_gpad_state)
        axes_str = ",".join(f"{v:.4f}" for v in state["axes"])
        buttons_str = ",".join(str(v) for v in state["buttons"])
        hat = state["hat"]
        ts = time.time()
        line = (
            f'{{"ts":{ts:.3f},"axes":[{axes_str}],'
            f'"buttons":[{buttons_str}],"hat":[{hat[0]},{hat[1]}]}}'
        )
        print(line, flush=True)

    server.close()
    await server.wait_closed()


def main():
    global _running

    def on_signal(sig, frame):
        global _running
        _running = False

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

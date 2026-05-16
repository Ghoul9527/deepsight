#!/usr/bin/env python3
"""Chrome WebSocket Gamepad Bridge for DeepSight Host.

Starts a WebSocket server and generates an HTML page that reads gamepad state
via the Web Gamepad API (navigator.getGamepads) and streams it over WebSocket.

Usage:
  python scripts/chrome_ws_bridge.py

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


def get_url():
    """Return the file:// URL for the gamepad tester page."""
    return f"file://{HTML_PATH}"


_ws_recv_count = 0
_ws_recv_logged = False

async def ws_handler(websocket):
    """Receive gamepad state from Chrome and update shared state."""
    global _ws_recv_count, _ws_recv_logged
    async for message in websocket:
        _ws_recv_count += 1
        if not _ws_recv_logged and _ws_recv_count <= 3:
            print(f"Chrome bridge: received message #{_ws_recv_count}", file=sys.stderr, flush=True)
            _ws_recv_logged = True
        try:
            data = json.loads(message)
            # Normalize to bridge format: 6 axes, 13 buttons
            axes = data.get("axes", [0.0] * 6)
            if len(axes) < 6:
                axes = axes + [0.0] * (6 - len(axes))

            buttons = data.get("buttons", [0] * 13)
            # Pad buttons if less than 13
            if len(buttons) < 13:
                buttons = buttons + [0] * (13 - len(buttons))

            hat = data.get("hat", [0, 0])

            with _gpad_lock:
                _gpad_state["axes"] = axes[:6]
                _gpad_state["buttons"] = buttons[:13]
                _gpad_state["hat"] = hat[:2]
        except Exception:
            pass


async def main_async():
    global _running
    url = get_url()

    server = await serve(
        ws_handler, "127.0.0.1", PORT, ping_interval=None
    )
    _server_ready.set()

    print(f"Chrome bridge: WebSocket server on ws://127.0.0.1:{PORT}", file=sys.stderr)
    print(f"Chrome bridge: open {url} in Chrome", file=sys.stderr)
    sys.stderr.flush()

    # Output loop — writes latest gamepad state to stdout at ~250Hz
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

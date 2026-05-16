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
import tempfile
import threading
import time

import websockets
from websockets.asyncio.server import serve

PORT = 9877
HTML_PATH = os.path.join(tempfile.gettempdir(), "deepsight_gamepad.html")

_gpad_state: dict = {"axes": [0.0] * 6, "buttons": [0] * 13, "hat": [0, 0]}
_gpad_lock = threading.Lock()
_server_ready = threading.Event()
_running = True

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>DeepSight Gamepad</title>
<style>body{background:#111;color:#0f0;font:16px monospace;padding:20px}
#log{white-space:pre;margin-top:10px;color:#888} .ok{color:#0f0} .err{color:red}</style>
</head><body>
<h1>DeepSight Gamepad Bridge</h1>
<p id="status" class="err">Connecting...</p>
<pre id="log"></pre>
<script>
const status = document.getElementById('status');
const logEl = document.getElementById('log');
function log(msg) { logEl.textContent += msg + '\\n'; }

let ws;
function connect() {
  ws = new WebSocket('ws://localhost:""" + str(PORT) + """');
  ws.onopen = () => { status.textContent = 'Connected — streaming gamepad data'; status.className='ok'; };
  ws.onclose = () => { status.textContent = 'Disconnected — retrying...'; status.className='err'; setTimeout(connect, 2000); };
  ws.onerror = () => ws.close();
}
connect();

function poll() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const gps = navigator.getGamepads();
    let gp = gps[0];
    // Search all slots for a connected gamepad
    if (!gp || !gp.connected) {
      for (let i = 0; i < gps.length; i++) {
        if (gps[i] && gps[i].connected) { gp = gps[i]; break; }
      }
    }
    if (gp && gp.connected) {
      const msg = JSON.stringify({
        ts: Date.now() / 1000,
        axes: [
          gp.axes[0] || 0, gp.axes[1] || 0, gp.axes[2] || 0,
          gp.axes[3] || 0, gp.axes[4] || 0, gp.axes[5] || 0,
        ],
        buttons: Array.from(gp.buttons).map(b => b.value > 0.5 ? 1 : 0),
        hat: [
          (gp.buttons[14]?.pressed ? 1 : 0) - (gp.buttons[15]?.pressed ? 1 : 0),
          (gp.buttons[12]?.pressed ? 1 : 0) - (gp.buttons[13]?.pressed ? 1 : 0),
        ],
      });
      ws.send(msg);
    }
  }
  requestAnimationFrame(poll);
}
poll();
</script></body></html>"""


def write_html():
    """Write the HTML page so the user can open it in Chrome."""
    with open(HTML_PATH, "w") as f:
        f.write(HTML)
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
    url = write_html()

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

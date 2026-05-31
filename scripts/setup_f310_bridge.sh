#!/usr/bin/env bash
# setup_f310_bridge.sh — Build and install the F310 USB HID bridge with setuid
#
# The bridge uses IOUSBHostDevice DeviceCapture to read F310 D-mode HID
# reports directly from USB, bypassing macOS HIDRM on macOS 26+.
# setuid root is needed because DeviceCapture requires root privileges
# (or the com.apple.vm.device-access entitlement).
#
# Usage: ./scripts/setup_f310_bridge.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$PROJECT_DIR/scripts/f310_bridge.m"
BIN="$PROJECT_DIR/scripts/f310_bridge"
INSTALL_PATH="/usr/local/bin/deepsight_f310_bridge"

echo "=== F310 Bridge Setup ==="

# 1. Build
echo "→ Building $SRC ..."
clang -framework Foundation -framework IOUSBHost -framework IOKit \
    -Os -o "$BIN" "$SRC"
echo "   Built: $BIN"

# 2. Install
echo "→ Installing to $INSTALL_PATH ..."
sudo cp "$BIN" "$INSTALL_PATH"

# 3. setuid root (needed for IOUSBHostDevice DeviceCapture)
echo "→ Setting setuid root ..."
sudo chown root:wheel "$INSTALL_PATH"
sudo chmod 4755 "$INSTALL_PATH"
echo "   Permissions: $(ls -la "$INSTALL_PATH" | awk '{print $1, $3, $4}')"

# 4. Test (dry run — will fail if F310 not connected, that's OK)
echo "→ Testing bridge ..."
"$INSTALL_PATH" --debug &
PID=$!
sleep 1
if kill -0 "$PID" 2>/dev/null; then
    echo "   Bridge running (PID $PID) — looks good!"
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
else
    echo "   Bridge exited immediately — F310 not connected? (non-fatal)"
fi

echo ""
echo "=== Setup complete ==="
echo "Bridge installed at: $INSTALL_PATH"
echo "Run manually: $INSTALL_PATH [--debug]"
echo "Python controller.py will auto-detect and use it."

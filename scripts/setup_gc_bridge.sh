#!/usr/bin/env bash
# Setup GCController bridge — build, sign, install
#
# The bridge uses Apple GameController.framework. On first run with a
# properly signed .app bundle (Developer ID), macOS will prompt for
# game controller permission.
#
# During development, this bridge may return all zeros until TCC
# permission is granted. The USB bridge serves as fallback.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/gc_bridge.swift"
INSTALL_PATH="/usr/local/bin/deepsight_gc_bridge"

echo "=== Build GCController Bridge ==="
swiftc -Onone -g -o "$INSTALL_PATH" "$SRC"
echo "  compiled: $INSTALL_PATH"

echo "=== Sign (ad-hoc, no entitlements) ==="
codesign --sign - --force "$INSTALL_PATH"
echo "  signed"

echo "=== Verify ==="
codesign -d -v "$INSTALL_PATH" 2>&1 | head -3
echo ""
echo "✓ GCController bridge installed to $INSTALL_PATH"
echo ""
echo "During development, use the USB bridge for actual input."
echo "The GCController bridge will work after packaging with Developer ID."

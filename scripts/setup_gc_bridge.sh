#!/usr/bin/env bash
# Build the package-local helper. No sudo or /usr/local install required.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="$SCRIPT_DIR/../host/src/deepsight_host/native/DeepSightGamepad.app"
mkdir -p "$BUNDLE/Contents/MacOS"
cp "$SCRIPT_DIR/gc_bridge_info.plist" "$BUNDLE/Contents/Info.plist"
xcrun swiftc -O "$SCRIPT_DIR/gc_bridge.swift" -framework AppKit -framework GameController -o "$BUNDLE/Contents/MacOS/gc_bridge"
# CODE_SIGN_IDENTITY can select a distribution identity for release packaging.
SIGN_ID="${CODE_SIGN_IDENTITY:-}"
if [ -z "$SIGN_ID" ]; then
  SIGN_ID="$(security find-identity -v -p codesigning | sed -nE 's/.* ([A-F0-9]{40}) ".*/\1/p' | head -1)"
fi
if [ -z "$SIGN_ID" ]; then
  echo 'No code-signing identity available. Set CODE_SIGN_IDENTITY to a usable identity.' >&2
  exit 1
fi
codesign --force --sign "$SIGN_ID" "$BUNDLE"
codesign --verify --strict "$BUNDLE"
echo "Built signed gamepad helper: $BUNDLE"

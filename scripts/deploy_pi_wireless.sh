#!/bin/bash
# deploy_pi_wireless.sh — Deploy WiFi/BLE GoPro control updates to Raspberry Pi 5
# Run from the deepsight repo root

set -e
PI_HOST="${1:-192.168.20.14}"
PI_USER="${2:-tony}"
PI_DIR="/home/tony/deepsight"

echo "=== Deploying WiFi/BLE GoPro control to Pi at $PI_HOST ==="

# 1. Copy updated files
echo ""
echo "[1/5] Copying source files..."
scp pi/src/deepsight_pi/gopro/real_gopro.py "$PI_USER@$PI_HOST:$PI_DIR/pi/src/deepsight_pi/gopro/real_gopro.py"
scp pi/src/deepsight_pi/gopro/__init__.py "$PI_USER@$PI_HOST:$PI_DIR/pi/src/deepsight_pi/gopro/__init__.py"
scp pi/src/deepsight_pi/config.py "$PI_USER@$PI_HOST:$PI_DIR/pi/src/deepsight_pi/config.py"
scp pi/src/deepsight_pi/main.py "$PI_USER@$PI_HOST:$PI_DIR/pi/src/deepsight_pi/main.py"
scp configs/pi_config.yaml "$PI_USER@$PI_HOST:$PI_DIR/configs/pi_config.yaml"

# 2. Install dependencies
echo ""
echo "[2/5] Installing Python dependencies..."
ssh "$PI_USER@$PI_HOST" "source deepsight-venv/bin/activate && pip install bleak aiohttp" 2>/dev/null || \
    ssh "$PI_USER@$PI_HOST" "pip3 install --break-system-packages bleak aiohttp"

# 3. Enable Bluetooth + WiFi
echo ""
echo "[3/5] Ensuring Bluetooth and WiFi are enabled..."
ssh "$PI_USER@$PI_HOST" "sudo rfkill unblock bluetooth; sudo rfkill unblock wifi; sudo systemctl enable bluetooth; sudo systemctl start bluetooth; echo 'Bluetooth status:'; systemctl is-active bluetooth"

# 4. Set display resolution to 1080p
echo ""
echo "[4/5] Setting Pi display resolution to 1080p..."
ssh "$PI_USER@$PI_HOST" '
# Raspberry Pi OS Bookworm uses KMS driver by default
# Resolution is controlled via cmdline.txt for console, or config.txt for legacy
CMDLINE="/boot/firmware/cmdline.txt"
CONFIG="/boot/firmware/config.txt"

# Check for KMS video mode in cmdline.txt
if grep -q "video=HDMI-A-1" "$CMDLINE" 2>/dev/null; then
    echo "KMS video= already set in cmdline.txt"
elif grep -q "vc4-kms" "$CONFIG" 2>/dev/null; then
    echo "KMS driver detected — adding video= to cmdline.txt"
    sudo sed -i 's/$/ video=HDMI-A-1:1920x1080M@60/' "$CMDLINE"
    echo "Added 1080p KMS video mode to cmdline.txt"
else
    # Legacy display driver
    if ! grep -q "hdmi_group=2" "$CONFIG" 2>/dev/null; then
        echo "" | sudo tee -a "$CONFIG"
        echo "# 1080p display" | sudo tee -a "$CONFIG"
        echo "hdmi_group=2" | sudo tee -a "$CONFIG"
        echo "hdmi_mode=82" | sudo tee -a "$CONFIG"
        echo "Set 1080p via hdmi_group/hdmi_mode in config.txt"
    fi
fi
echo "Reboot required for resolution change to take effect"
'

# 5. Restart deepsight service
echo ""
echo "[5/5] Restarting deepsight service..."
ssh "$PI_USER@$PI_HOST" "sudo systemctl restart deepsight-pi && echo 'Service restarted' || echo 'No systemd service found — restart manually'"

echo ""
echo "=== Deployment complete ==="
echo "Check logs on Pi: journalctl -u deepsight-pi -f"

# DeepSight Hardware Setup & Debug Guide

## Hardware Checklist

### Confirmed
| Item | Status | Notes |
|------|--------|-------|
| GoPro Hero 13 + Media Mod | Acquired | USB-C (control) + MicroHDMI (video) |
| GoPro → Pi USB-C cable | Acquired | Wired control via HTTP |
| GoPro → Capture dongle MicroHDMI | Acquired | Uncompressed video out |
| HDMI capture dongle → Pi USB 3.0 | Acquired | Appears as /dev/video0 (UVC) |
| Raspberry Pi 5 | Acquired | VideoCore VII GPU for H.264 HW encode |
| Pico + PCA9685 driver board | Acquired | 16ch 12-bit PWM for servos/lights |
| Logitech F310 gamepad | Acquired | DirectInput/XInput, works cross-platform |
| Ethernet switch (100Mbps) | Acquired | Sufficient for test phase (see note) |

### To Acquire
| Item | Recommendation |
|------|---------------|
| Pi → Pico jumper wires | Dupont female-female, 4 wires (5V, GND, TX, RX) |
| Pi → STM32 jumper wires | Dupont female-female, 4 wires |
| Servo power supply | Separate 5-6V rail (do NOT power servos from Pi 5V pin) |
| Ethernet cables (x2) | Cat5e or better, Pi→Switch, Switch→Host |

### 100Mbps vs 1000Mbps Switch

**100Mbps is sufficient for testing.** Here's why:

| Stream | Bitrate | % of 100Mbps |
|--------|---------|-------------|
| H.264 video (8Mbps) | 8 Mbps | 8% |
| UDP commands | < 0.1 Mbps | < 0.1% |
| WebSocket telemetry | < 0.1 Mbps | < 0.1% |
| **Total** | **~8.2 Mbps** | **~8%** |

The video encoder uses 8Mbps CBR with 12M maxrate — well within 100Mbps.
Upgrade to gigabit only if you later need multiple 4K streams or raw video.

---

## Step 1: Flash & Test Pico Firmware

### Flash
```bash
# Install MicroPython on Pico (if not already)
# Hold BOOTSEL, connect USB, copy .uf2 to RPI-RP2 drive

# Copy project files
cd deepsight
python -m deepsight_tools.cli flash pico
```

### Test (standalone, USB to Host)
```bash
screen /dev/tty.usbmodem* 115200
# Should see: "Pico DeepSight Node v1.0"
# Send: {"type":"sys.heartbeat"}
# Expect: {"type":"sys.ack",...}
```

### Wire Pico → PCA9685
```
Pico Pin 1  (GP0, I2C0 SDA) → PCA9685 SDA
Pico Pin 2  (GP1, I2C0 SCL) → PCA9685 SCL
Pico Pin 36 (3V3 OUT)        → PCA9685 VCC (logic)
Pico Pin 38 (GND)            → PCA9685 GND
External 5-6V                → PCA9685 V+ (servo power)
```

### Wire Pico → Pi (UART)
```
Pico Pin 7  (GP5, UART1 TX)  → Pi Pin 10 (GPIO15, UART0 RX)
Pico Pin 8  (GP6, UART1 RX)  → Pi Pin 8  (GPIO14, UART0 TX)
Pico Pin 36 (3V3)             → Pi Pin 1  (3V3) — optional if USB powered
Pico Pin 38 (GND)             → Pi Pin 6  (GND)
```

### Test PCA9685
```python
# On Pico REPL:
from lib.servo import PCA9685ServoDriver
s = PCA9685ServoDriver()
s.set_angle(0, 90)  # Servo 0 → center
```

---

## Step 2: Pi 5 OS Setup

### Install dependencies
```bash
ssh pi@raspberrypi.local

# System packages
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg

# Verify ffmpeg
ffmpeg -version

# Verify hardware encoder available
ffmpeg -encoders 2>/dev/null | grep h264_v4l2m2m
# Should show: V..... h264_v4l2m2m (codec h264)

# Deploy code
cd ~/deepsight
./scripts/install_deps.sh
./scripts/setup_venv.sh
```

### Enable UART on Pi
```bash
sudo raspi-config
# Interface Options → Serial Port
#   Login shell over serial: NO
#   Serial port hardware: YES
# Reboot
sudo reboot

# After reboot, verify:
ls -la /dev/ttyAMA0  # Should exist (this connects to Pico)
```

### Configure Pi for real hardware
Edit `configs/pi_config.yaml`:
```yaml
serial:
  pico_port: "/dev/ttyAMA0"   # Real UART
  stm32_port: "mock"          # Real later: /dev/ttyAMA1

gopro:
  mock: false                 # Real GoPro over USB

capture:
  mock: false
  device: "/dev/video0"

video:
  codec: "h264_v4l2m2m"
  bitrate: "8M"
  stream_port: 8554
```

---

## Step 3: GoPro + Capture Card Verification

### Check GoPro USB control
```bash
# Plug GoPro USB-C → Pi USB 3.0
lsusb
# Should show GoPro device (05ac:12ab or similar)

# Test wired control
curl http://10.5.5.9/gp/gpControl/status
# Should return JSON with camera status
```

### Check HDMI capture dongle
```bash
# Plug capture dongle HDMI → GoPro, USB → Pi
ls -la /dev/video*
# Should show /dev/video0 (and possibly /dev/video1)

# Check UVC capabilities
v4l2-ctl -d /dev/video0 --list-formats-ext
# Should list supported resolutions (expect 1920x1080@60)

# Quick capture test
ffmpeg -f v4l2 -input_format mjpeg -video_size 1920x1080 \
       -i /dev/video0 -vframes 1 test_frame.jpg
# Verify test_frame.jpg shows GoPro feed
```

---

## Step 4: Video Pipeline End-to-End Test

### Start Pi encoder in TCP server mode
```bash
ssh pi@raspberrypi.local
cd ~/deepsight
.venv/bin/python3 -m deepsight_pi.main
# Log should show: "Encoder: h264_v4l2m2m 1920x1080@60 → tcp://0.0.0.0:8554"
# "Video loop started"
```

### Test stream from Host
```bash
# On Host machine:
python3 -c "
import cv2
cap = cv2.VideoCapture('tcp://raspberrypi.local:8554')
ret, frame = cap.read()
if ret:
    cv2.imwrite('pi_stream_test.jpg', frame)
    print('OK: frame saved, shape:', frame.shape)
else:
    print('FAIL: no frame received')
cap.release()
"
```

### Common issues:
| Symptom | Cause | Fix |
|---------|-------|-----|
| `ffmpeg not found` | ffmpeg not installed | `sudo apt install ffmpeg` |
| `h264_v4l2m2m: No such file` | Missing HW codec | Fall back: `codec: "libx264"` in config |
| `Connection refused` | Encoder not running | Check Pi logs for encoder errors |
| Black/green frame | Capture card not getting signal | Check HDMI cable, GoPro powered on, not in menus |
| `Broken pipe` | Host disconnected | Normal on shutdown; encoder auto-restarts |
| High CPU (>50%) | Software encode fallback | Verify `h264_v4l2m2m` is loaded; `lsmod | grep v4l2` |

---

## Step 5: Pi ↔ Pico Communication Test

```bash
# On Pi:
screen /dev/ttyAMA0 115200
# Send: {"type":"sys.heartbeat","node_id":"pi","msg_id":"test"}
# Pico should respond with ack

# Or run full Pi node:
.venv/bin/python3 -m deepsight_pi.main
# Log should show PicoLink connected and heartbeating
```

---

## Step 6: Full System Bring-Up

### Order matters:
1. Power on GoPro, set to Video mode
2. Connect HDMI capture dongle
3. Power on Pico (via USB or Pi 5V pin)
4. Power on STM32 (if connected)
5. Boot Pi 5, start Pi node
6. Start Host application

### Start Host (mock mode — no Pi required)
```bash
cd deepsight
.venv/bin/python3 -m deepsight_host.main
```

### Start Host (real mode — Pi streaming)
Edit `configs/host_config.yaml`:
```yaml
video:
  stream_url: "tcp://raspberrypi.local:8554"
```

```bash
.venv/bin/python3 -m deepsight_host.main
# Video preview should show GoPro feed with tracking overlay
```

---

## Step 7: Controller Test

```bash
# Verify F310 is detected
python3 -c "
from deepsight_host.control.controller import GameController
c = GameController()
c.start()
# Move joysticks — servo sliders should move in the GUI
"
```

The F310 works out of the box on macOS, Linux, and Windows. No driver needed. The switch on the back should be set to "X" (XInput mode).

---

## Debug Checklist Per Component

### GoPro
- [ ] USB-C connected to Pi USB 3.0 port (not USB 2.0)
- [ ] Camera powered on, in Video mode
- [ ] `curl http://10.5.5.9/gp/gpControl/status` returns JSON
- [ ] Not in menus/settings screen (blocks some HTTP commands)

### Capture Card
- [ ] MicroHDMI seated firmly in Media Mod
- [ ] USB dongle in Pi USB 3.0 port (blue)
- [ ] `/dev/video0` exists
- [ ] `v4l2-ctl -d /dev/video0 --list-formats-ext` shows 1920x1080

### Encoder
- [ ] `ffmpeg -encoders | grep h264_v4l2m2m` shows hardware encoder
- [ ] No ffmpeg errors on start
- [ ] `ss -tlnp | grep 8554` shows port listening

### Network
- [ ] Pi and Host on same subnet (both connected to switch)
- [ ] `ping raspberrypi.local` works from Host
- [ ] `nc -zv raspberrypi.local 8554` shows port open
- [ ] `nc -zv raspberrypi.local 5100` shows UDP port (Pi API)

### Pico + Sensors
- [ ] I2C scan finds PCA9685 at 0x40: `i2c.scan()`
- [ ] Servos move on command
- [ ] UART link shows bidirectional traffic

---

## Quick Smoke Test (All Mock)

If hardware isn't ready, verify the full software stack:

```bash
# Terminal 1: Pi (mock mode)
cd deepsight
.venv/bin/python3 -m deepsight_pi.main
# → Creates mock capture frames, encodes to tcp://0.0.0.0:8554

# Terminal 2: Check stream
.venv/bin/python3 -c "
import cv2
cap = cv2.VideoCapture('tcp://127.0.0.1:8554')
for _ in range(5):
    ret, f = cap.read()
    print(f'Frame: {f.shape if ret else \"MISS\"}')
"
# → Should print 5 frames with test pattern

# Terminal 3: Host
.venv/bin/python3 -m deepsight_host.main
# → GUI opens, video preview shows test pattern, tracking active
```

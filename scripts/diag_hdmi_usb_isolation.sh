#!/bin/bash
# HDMI vs USB-C 信道隔离诊断脚本
# 运行在 Pi 上，验证 GoPro HDMI 输出和 USB GoPro Connect 是否冲突
#
# 用法:
#   chmod +x diag_hdmi_usb_isolation.sh
#   ./diag_hdmi_usb_isolation.sh
#
# 测试矩阵:
#   T1: 仅 HDMI (USB-C 不插) → 基线
#   T2: HDMI + USB-C 仅充电 (相机不设 GoPro Connect) → 测试 USB 供电是否影响
#   T3: HDMI + USB-C GoPro Connect 模式 → 测试 USB Ethernet 是否影响 HDMI
#
# 每个测试：运行 30 秒，采集帧率/黑帧/丢帧统计数据

set -euo pipefail

GOPRO_SSID="${GOPRO_SSID:-GP25108532}"
GOPRO_PW="${GOPRO_PW:-fZM-HDn-fsg}"
DURATION="${DURATION:-30}"
REPORT_FILE="/tmp/gopro_isolation_report.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$REPORT_FILE"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN${NC} $*" | tee -a "$REPORT_FILE"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ERR${NC} $*" | tee -a "$REPORT_FILE"; }

# ── USB Topology ───────────────────────────────────────

dump_usb_topo() {
    log "=== USB Bus Topology (lsusb -t) ==="
    lsusb -t 2>/dev/null || true
    echo
    log "=== USB Devices (lsusb) ==="
    lsusb 2>/dev/null || true
    echo
    log "=== USB Bus -> Device Mapping ==="
    for bus in /sys/bus/usb/devices/usb*; do
        [ -d "$bus" ] || continue
        busnum=$(basename "$bus" | sed 's/usb//')
        # Find all devices on this bus
        for dev in "$bus"/[0-9]*-*; do
            [ -d "$dev" ] || continue
            vendor=$(cat "$dev/idVendor" 2>/dev/null || echo "????")
            product=$(cat "$dev/idProduct" 2>/dev/null || echo "????")
            speed=$(cat "$dev/speed" 2>/dev/null || echo "?")
            # speed: -1=SuperSpeed(5G), 1.5=Low, 12=Full, 480=High
            case "$speed" in
                5000) spd="SS(5G)" ;;
                480)  spd="HS(480M)" ;;
                12)   spd="FS(12M)" ;;
                1.5)  spd="LS(1.5M)" ;;
                *)    spd="speed=$speed" ;;
            esac
            echo "  bus${busnum}  ${vendor}:${product}  ${spd}  $(basename "$dev")"
        done
    done
    echo
}

# ── V4L2 Device Info ──────────────────────────────────

find_capture_device() {
    # Find the HDMI capture dongle by persistent path or fallback
    local dev=""
    for candidate in \
        "/dev/v4l/by-id/usb-Actions_Micro_UGREEN-25854_-66318299-video-index0" \
        "/dev/v4l/by-id/usb-MACROSILICON_USB_Video-video-index0" \
        "/dev/video2" "/dev/video1" "/dev/video0"; do
        if [ -e "$candidate" ]; then
            dev="$candidate"
            break
        fi
    done
    echo "$dev"
}

dump_v4l2_info() {
    local dev="$1"
    log "=== V4L2 Device: $dev ==="
    if [ ! -e "$dev" ]; then
        err "  Device not found!"
        return
    fi
    real=$(realpath "$dev" 2>/dev/null || echo "$dev")
    log "  真实路径: $real"
    log "  支持格式:"
    v4l2-ctl -d "$dev" --list-formats-ext 2>/dev/null | head -40 || true
    echo
    # Check USB power management
    local video_name=$(basename "$real")
    local power_control="/sys/class/video4linux/${video_name}/device/power/control"
    if [ -f "$power_control" ]; then
        log "  USB 电源管理: $(cat "$power_control")"
    fi
}

# ── Frame Capture Monitor ─────────────────────────────

run_capture_monitor() {
    local label="$1"
    local duration="$2"
    local capture_dev="$3"
    local output_dir="/tmp/gopro_diag"
    mkdir -p "$output_dir"
    local stats_file="${output_dir}/${label}_stats.txt"

    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log " 测试: $label"
    log " 时长: ${duration}s"
    log " 设备: $capture_dev"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    python3 - "$capture_dev" "$duration" "$stats_file" <<'PYEOF'
import sys
import time
import json
import numpy as np

try:
    import cv2
except ImportError:
    print("ERROR:OpenCV not installed", file=sys.stderr)
    sys.exit(1)

device = sys.argv[1]
duration = int(sys.argv[2])
stats_file = sys.argv[3]

cap = cv2.VideoCapture(device)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FPS, 60)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

if not cap.isOpened():
    print("ERROR:Cannot open capture device", file=sys.stderr)
    sys.exit(1)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)
fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc = "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4))
print(f"CAPTURE_INFO:{actual_w}x{actual_h} @ {actual_fps:.1f}fps codec={fourcc}")

# Stats
total_frames = 0
black_frames = 0   # mean brightness < 5
dark_frames = 0    # mean brightness < 30
dropped_intervals = 0
prev_time = time.time()
start_time = prev_time
frame_times = []

# Black threshold: average pixel < 5 = black screen
BLACK_THRESHOLD = 5
DARK_THRESHOLD = 30

while time.time() - start_time < duration:
    ret, frame = cap.read()
    now = time.time()
    if not ret or frame is None:
        dropped_intervals += 1
        continue
    total_frames += 1
    mean_brightness = float(np.mean(frame))
    if mean_brightness < BLACK_THRESHOLD:
        black_frames += 1
    elif mean_brightness < DARK_THRESHOLD:
        dark_frames += 1
    frame_times.append(now - prev_time)
    prev_time = now

cap.release()
elapsed = time.time() - start_time

# Compute frame interval stats
if len(frame_times) > 1:
    intervals = np.array(frame_times[1:])  # skip first (includes init)
    avg_interval = float(np.mean(intervals))
    std_interval = float(np.std(intervals))
    # FPS = 1 / mean interval
    effective_fps = 1.0 / avg_interval if avg_interval > 0 else 0
    # Count gaps > 2x expected interval (= dropped frames)
    expected_interval = 1.0 / max(actual_fps, 1)
    gaps = int(np.sum(intervals > expected_interval * 2.5))
else:
    avg_interval = 0
    std_interval = 0
    effective_fps = 0
    gaps = 0

result = {
    "test_label": sys.argv[0],
    "duration_s": round(elapsed, 1),
    "total_frames": total_frames,
    "effective_fps": round(effective_fps, 2),
    "avg_interval_ms": round(avg_interval * 1000, 2),
    "std_interval_ms": round(std_interval * 1000, 2),
    "black_frames": black_frames,
    "black_pct": round(100 * black_frames / max(total_frames, 1), 1),
    "dark_frames": dark_frames,
    "dark_pct": round(100 * dark_frames / max(total_frames, 1), 1),
    "frame_time_gaps": gaps,
    "dropped_reads": dropped_intervals,
}
print("RESULT:" + json.dumps(result, ensure_ascii=False))
with open(stats_file, "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
PYEOF

    local rc=$?
    if [ $rc -ne 0 ]; then
        err "  捕获监视器退出码: $rc"
    fi

    # Display results
    if [ -f "$stats_file" ]; then
        log "  结果:"
        python3 -c "
import json
with open('$stats_file') as f:
    d = json.load(f)
print(f'    总帧数:     {d[\"total_frames\"]}')
print(f'    有效FPS:    {d[\"effective_fps\"]}')
print(f'    帧间隔:     {d[\"avg_interval_ms\"]}ms ± {d[\"std_interval_ms\"]}ms')
print(f'    黑帧(avg<5): {d[\"black_frames\"]} ({d[\"black_pct\"]}%)')
print(f'    暗帧(avg<30):{d[\"dark_frames\"]} ({d[\"dark_pct\"]}%)')
print(f'    间隔>2.5x:   {d[\"frame_time_gaps\"]}')
print(f'    读取失败:   {d[\"dropped_reads\"]}')
"
    fi
    echo
}

# ── Check GoPro HTTP API ──────────────────────────────

check_gopro_http() {
    local ip="$1"
    local timeout="${2:-3}"
    curl -s --connect-timeout "$timeout" "http://${ip}:8080/gopro/camera/state" >/dev/null 2>&1
}

find_gopro_ip() {
    # Try common GoPro IPs
    for ip in 172.20.16.1 172.20.17.1 172.20.18.1 172.20.19.1 \
              172.20.20.1 172.20.21.1 172.28.0.1 172.28.1.1 \
              172.28.2.1 10.5.5.9; do
        if check_gopro_http "$ip" 1; then
            echo "$ip"
            return
        fi
    done
    echo ""
}

# ── Main Test Sequence ────────────────────────────────

main() {
    echo "" > "$REPORT_FILE"
    log "GoPro HDMI/USB 信道隔离诊断"
    log "=============================="
    log "时间: $(date)"
    log "主机: $(hostname)"
    log "内核: $(uname -r)"
    echo

    # ── Prerequisites ──
    CAPTURE_DEV=$(find_capture_device)
    if [ -z "$CAPTURE_DEV" ] || [ ! -e "$CAPTURE_DEV" ]; then
        err "未找到 HDMI 采集设备！请确认采集卡已插入。"
        err "可用 V4L2 设备:"
        ls -la /dev/v4l/by-id/ 2>/dev/null || ls -la /dev/video* 2>/dev/null || true
        exit 1
    fi
    log "采集设备: $CAPTURE_DEV"
    dump_usb_topo
    dump_v4l2_info "$CAPTURE_DEV"

    # ── T1: HDMI Only (no USB-C) ──
    log ""
    log "╔══════════════════════════════════════════════════════╗"
    log "║  T1: 仅 HDMI (拔掉 USB-C)                           ║"
    log "╚══════════════════════════════════════════════════════╝"
    log ""
    log ">>> 请确保 GoPro USB-C 已从 Pi 拔掉 <<<"
    log ">>> GoPro 开机，MicroHDMI → 采集卡 → Pi USB <<<"
    log ">>> 按 Enter 开始 T1..."
    read -r

    dump_usb_topo
    run_capture_monitor "T1_hdmi_only" "$DURATION" "$CAPTURE_DEV"

    # ── T2: HDMI + USB-C charging only ──
    log ""
    log "╔══════════════════════════════════════════════════════╗"
    log "║  T2: HDMI + USB-C 仅充电                            ║"
    log "╚══════════════════════════════════════════════════════╝"
    log ""
    log ">>> 请插入 GoPro USB-C 到 Pi 的 USB 口 <<<"
    log ">>> 相机 USB 模式设为: 仅充电 (NOT GoPro Connect) <<<"
    log ">>> 按 Enter 开始 T2..."
    read -r

    dump_usb_topo
    # Check if usb0 appeared (should NOT in charge-only mode)
    if ip link show usb0 >/dev/null 2>&1; then
        warn "  检测到 usb0 接口 — 相机可能处于 GoPro Connect 模式！"
        warn "  请确认相机 USB 设置为 '仅充电'"
    fi
    run_capture_monitor "T2_hdmi_plus_charge" "$DURATION" "$CAPTURE_DEV"

    # ── T3: HDMI + USB-C GoPro Connect ──
    log ""
    log "╔══════════════════════════════════════════════════════╗"
    log "║  T3: HDMI + USB-C GoPro Connect 模式                ║"
    log "╚══════════════════════════════════════════════════════╝"
    log ""
    log ">>> 请将相机 USB 模式切换为: GoPro Connect <<<"
    log ">>> 等待 usb0 接口出现 (观察 ip link) <<<"
    log ">>> 按 Enter 开始 T3..."
    read -r

    dump_usb_topo

    # Check usb0 status
    if ip link show usb0 >/dev/null 2>&1; then
        log "  usb0 状态:"
        ip -4 addr show usb0 2>/dev/null | grep inet || log "    (无 IP)"
    else
        warn "  usb0 未出现！GoPro Connect 模式可能未正确启用"
    fi

    # Try to find GoPro HTTP API
    GOPRO_IP=$(find_gopro_ip)
    if [ -n "$GOPRO_IP" ]; then
        log "  GoPro HTTP API 可达: http://${GOPRO_IP}:8080"
        log "  相机状态:"
        curl -s "http://${GOPRO_IP}:8080/gopro/camera/state" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -20 || true
    else
        warn "  GoPro HTTP API 不可达"
    fi

    # Monitor dmesg for USB errors during capture
    log "  开始捕获监控 (同时记录 dmesg 错误)..."
    dmesg -c >/dev/null 2>&1 || true  # clear ring buffer
    run_capture_monitor "T3_hdmi_plus_connect" "$DURATION" "$CAPTURE_DEV"

    # Check dmesg for USB errors
    log "  捕获期间的 dmesg (过滤 USB/error):"
    dmesg 2>/dev/null | grep -iE "usb|error|fail|reset|disconnect|bandwidth|over.cur" | tail -20 || log "    (无相关日志)"
    echo

    # ── Summary ──
    log ""
    log "╔══════════════════════════════════════════════════════╗"
    log "║  诊断报告摘要                                       ║"
    log "╚══════════════════════════════════════════════════════╝"
    log ""
    log "完整报告: $REPORT_FILE"
    log "统计数据: /tmp/gopro_diag/"
    echo

    # Compare results
    compare_results

    log ""
    log "诊断完成。如果 T3 的黑帧/丢帧显著高于 T1，"
    log "说明 HDMI 和 USB GoPro Connect 存在信道冲突。"
    log "如果 T1-T3 数据无明显差异，则问题在其他地方。"
}

compare_results() {
    echo "测试对比:"
    echo "  Test  Frames  Eff_FPS  Black%  Dark%  Gaps  Errors"
    echo "  ----  ------  -------  ------  -----  ----  ------"
    for f in /tmp/gopro_diag/T*_stats.txt; do
        [ -f "$f" ] || continue
        label=$(basename "$f" _stats.txt)
        python3 -c "
import json
with open('$f') as fh:
    d = json.load(fh)
print(f'  ${label:6s} {d[\"total_frames\"]:5d}   {d[\"effective_fps\"]:6.1f}   {d[\"black_pct\"]:5.1f}%  {d[\"dark_pct\"]:5.1f}%  {d[\"frame_time_gaps\"]:4d}   {d[\"dropped_reads\"]:4d}')
"
    done
    echo
}

main "$@"

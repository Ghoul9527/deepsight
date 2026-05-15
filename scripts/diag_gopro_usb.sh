#!/bin/bash
# GoPro USB-C splitter diagnostic
# Run on Pi: bash diag_gopro_usb.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
check() { echo -e "  $1"; }

echo "============================================"
echo " GoPro USB-C Splitter Diagnostic"
echo " $(date)"
echo "============================================"
echo ""

# ── 1. Check USB devices ──
echo "── USB Devices ──"
if lsusb | grep -qi gopro; then
    pass "GoPro detected in USB bus"
    lsusb | grep -i gopro
else
    info "GoPro not found by name in lsusb. Full USB tree:"
    lsusb
fi
echo ""

# ── 2. Check network interfaces ──
echo "── dmesg USB Events (last 20 lines) ──"
dmesg | grep -i -E "usb|gopro|eth|rndis|cdc" | tail -20 || echo "  (none)"
echo ""

echo "── Network Interfaces (ALL up/down) ──"
# List all interfaces regardless of name
for f in /sys/class/net/*; do
    [ -d "$f" ] || continue
    name=$(basename "$f")
    [ "$name" = "lo" ] && continue
    state=$(cat "$f/operstate" 2>/dev/null || echo "unknown")
    check "Interface $name: state=$state"
    ip -4 addr show "$name" 2>/dev/null | grep inet && {
        check "Routes:"
        ip -4 route show dev "$name" 2>/dev/null | head -5 || true
    } || echo "    (no IPv4)"
    echo ""
done
echo ""

# ── 3. Check for GoPro USB Ethernet IP ──
echo "── GoPro IP Discovery ──"
FOUND_IP=""
for iface in $(ls /sys/class/net/); do
    # skip lo, wlan, eth0 (main)
    [ "$iface" = "lo" ] && continue
    [ "$iface" = "wlan0" ] && continue
    [ "$iface" = "eth0" ] && continue

    gateway=$(ip -4 route show dev "$iface" default 2>/dev/null | grep -oP 'via \K[\d.]+' || true)
    inet=$(ip -4 -j addr show "$iface" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d:
    for a in d[0].get('addr_info',[]):
        if a.get('family')=='inet':
            print(a.get('local',''))
            break
" 2>/dev/null || true)

    [ -z "$inet" ] && continue

    info "$iface: inet=$inet gateway=$gateway"

    # Try gateway first (GoPro is usually the DHCP server)
    for candidate in "$gateway" "${inet%.*}.1" "${inet%.*}.51"; do
        [ -z "$candidate" ] && continue
        check "  Attempting HTTP connection to $candidate:8080 ..."
        if timeout 2 bash -c "echo >/dev/tcp/$candidate/8080" 2>/dev/null; then
            pass "GoPro HTTP API reachable at $candidate:8080"
            FOUND_IP="$candidate"
            break 2
        fi
    done
    echo ""
done

if [ -z "$FOUND_IP" ]; then
    # Broader scan: try known GoPro USB subnets
    info "Gateway check failed, scanning known GoPro subnets..."
    for subnet in "172.20.{0..31}.1" "172.21.{0..31}.1" "172.22.{0..31}.1" \
                  "172.23.{0..31}.1" "172.24.{0..31}.1" "172.25.{0..31}.1" \
                  "172.26.{0..31}.1" "172.27.{0..31}.1" "172.28.{0..31}.1" \
                  "172.29.{0..31}.1" "172.30.{0..31}.1" "172.31.{0..31}.1" \
                  "10.5.5.9"; do
        if timeout 1 bash -c "echo >/dev/tcp/$subnet/8080" 2>/dev/null; then
            pass "GoPro HTTP API reachable at $subnet:8080"
            FOUND_IP="$subnet"
            break
        fi
    done
fi

if [ -z "$FOUND_IP" ]; then
    fail "Cannot reach GoPro HTTP API on any address"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Is GoPro in 'GoPro Connect' mode? (Preferences → USB → GoPro Connect)"
    echo "  2. Does the USB-C splitter pass data? (many are charge-only)"
    echo "  3. Try without the splitter: GoPro USB-C → Pi directly"
    echo "  4. Check dmesg for USB events: dmesg | tail -30"
    exit 1
fi

echo ""

# ── 4. Test GoPro HTTP API ──
echo "── GoPro HTTP API Tests ──"

check "Camera info..."
CAM_INFO=$(curl -s --connect-timeout 3 "http://$FOUND_IP:8080/gp/gpControl/info" 2>&1 || true)
if [ -n "$CAM_INFO" ]; then
    pass "Camera info endpoint responding"
    echo "$CAM_INFO" | python3 -c "
import json,sys
d=json.load(sys.stdin)
info=d.get('info',{})
print(f\"    Model:      {info.get('model_name','?')} ({info.get('model_number','?')})\")
print(f\"    Firmware:   {info.get('firmware_version','?')}\")
print(f\"    Serial:     {info.get('serial_number','?')}\")
" 2>/dev/null || echo "    Raw: $CAM_INFO"
else
    fail "Camera info endpoint not responding"
fi

echo ""
check "Camera status..."
STATUS=$(curl -s --connect-timeout 3 "http://$FOUND_IP:8080/gp/gpControl/status" 2>&1 || true)
if [ -n "$STATUS" ]; then
    pass "Status endpoint responding"
    echo "$STATUS" | python3 -c "
import json,sys
d=json.load(sys.stdin)
s=d.get('status',{})
# Battery
b=s.get('33',0); bp=s.get('34',0)
print(f'    Battery:    {b}% (percent2={bp}%)')
# Recording
r=s.get('8',0)
print(f'    Recording:  {\"YES\" if r==1 else \"no\"} (state={r})')
# Mode
m=s.get('43',-1)
modes={0:'Video',1:'Photo',2:'MultiShot',3:'Timelapse'}
print(f'    Mode:       {modes.get(m,str(m))} (id={m})')
# Storage
sd=s.get('54',0)
print(f'    SD remain:  {sd} units')
# Temp
t=s.get('37',0)
print(f'    Battery T:  {t}°C')
" 2>/dev/null || echo "    Raw: $STATUS"
else
    fail "Status endpoint not responding"
fi

echo ""
check "Media list (first 3 files)..."
MEDIA=$(curl -s --connect-timeout 5 "http://$FOUND_IP:8080/gp/gpMediaList" 2>&1 || true)
if [ -n "$MEDIA" ]; then
    echo "$MEDIA" | python3 -c "
import json,sys
d=json.load(sys.stdin)
media=d.get('media',[])
count=d.get('total_count',len(media))
print(f'    Total files: {count}')
for m in media[:3]:
    for f in m.get('fs',[]):
        n=f.get('n','?')
        s=int(f.get('s',0))
        print(f'    - {n} ({s/1e6:.0f}MB)')
" 2>/dev/null || echo "    Raw (truncated): ${MEDIA:0:300}"
else
    info "Media list not available (camera may be recording or busy)"
fi

echo ""
echo "============================================"
echo -e "${GREEN} Diagnostic complete. GoPro IP: $FOUND_IP${NC}"
echo "============================================"

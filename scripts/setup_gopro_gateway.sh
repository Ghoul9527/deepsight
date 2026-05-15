#!/bin/bash
# GoPro USB Ethernet gateway setup — idempotent, zero Python.
# Runs on Pi (or NanoPi/OpenWrt). Enables Host ↔ GoPro routing.
#
# Usage: sudo ./setup_gopro_gateway.sh [host_ip] [gopro_ip] [udp_port]
#   host_ip  - Host computer IP (default: 192.168.20.50)
#   gopro_ip - GoPro USB Ethernet IP (default: auto-detect)
#   udp_port - UDP stream port (default: 8554)
#
# On first run, detects GoPro USB interface and applies persistent config.

set -euo pipefail

HOST_IP="${1:-192.168.20.50}"
GOPRO_IP="${2:-}"
UDP_PORT="${3:-8554}"

# ── Detect GoPro USB Ethernet interface ──

detect_gopro_iface() {
    # GoPro USB Ethernet appears as usb0, eth1, enx*, etc.
    # It always has a 172.x.x.x address assigned by the GoPro DHCP server.
    for iface in $(ip -o link show | awk -F': ' '{print $2}' | grep -E 'usb|eth[1-9]|enx'); do
        local ip
        ip=$(ip -4 -o addr show "$iface" 2>/dev/null | awk '{print $4}' | grep '^172\.' | head -1)
        if [ -n "$ip" ]; then
            echo "$iface"
            return 0
        fi
    done
    return 1
}

detect_gopro_ip() {
    # GoPro is the DHCP server on USB Ethernet — it's the gateway of the 172.x subnet.
    # Typically 172.25.132.51, 172.28.128.51, or 172.20.16.51.
    for candidate in 172.25.132.51 172.28.128.51 172.20.16.51 172.20.17.51 172.20.18.51 172.20.19.51; do
        if curl -s --connect-timeout 2 "http://${candidate}:8080/gopro/camera/state" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

# ── Auto-detect ──

GOPRO_IFACE=$(detect_gopro_iface || true)
if [ -z "${GOPRO_IFACE:-}" ]; then
    echo "ERROR: No GoPro USB Ethernet interface found (looked for 172.x on usb/eth1/enx)"
    exit 1
fi

if [ -z "$GOPRO_IP" ]; then
    GOPRO_IP=$(detect_gopro_ip || true)
    if [ -z "$GOPRO_IP" ]; then
        echo "ERROR: GoPro interface $GOPRO_IFACE found but GoPro not responding on HTTP"
        exit 1
    fi
fi

echo "GoPro interface: $GOPRO_IFACE"
echo "GoPro IP:        $GOPRO_IP"
echo "Host IP:         $HOST_IP"
echo "UDP port:        $UDP_PORT"

# ── IP forwarding ──

echo 1 > /proc/sys/net/ipv4/ip_forward
if ! grep -q '^net.ipv4.ip_forward = 1' /etc/sysctl.conf 2>/dev/null; then
    echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf
    echo "  → IP forwarding enabled (persistent)"
else
    echo "  → IP forwarding already enabled"
fi

# ── SNAT: Host traffic to GoPro gets masqueraded ──
# This ensures GoPro always sends UDP back to the gateway, not directly to Host.
# Supports both nftables (modern) and iptables (legacy).

setup_snat() {
    local iface="$1"

    # Prefer nftables (NanoPi/OpenWrt compatible)
    if command -v nft &>/dev/null; then
        if ! sudo nft list table ip nat &>/dev/null; then
            sudo nft add table ip nat
        fi
        if ! sudo nft list chain ip nat postrouting &>/dev/null; then
            sudo nft add chain ip nat postrouting { type nat hook postrouting priority 100 \; }
        fi
        if ! sudo nft list chain ip nat postrouting 2>/dev/null | grep -q "oifname \"$iface\" masquerade"; then
            sudo nft add rule ip nat postrouting oifname "$iface" masquerade
            echo "  → SNAT rule added (nftables) for $iface"
        else
            echo "  → SNAT rule already exists (nftables) for $iface"
        fi
    elif command -v iptables &>/dev/null; then
        if ! iptables -t nat -C POSTROUTING -o "$iface" -j MASQUERADE 2>/dev/null; then
            iptables -t nat -A POSTROUTING -o "$iface" -j MASQUERADE
            echo "  → SNAT rule added (iptables) for $iface"
        else
            echo "  → SNAT rule already exists (iptables) for $iface"
        fi
    else
        echo "ERROR: Neither nftables nor iptables found"
        return 1
    fi
}

setup_snat "$GOPRO_IFACE"

# ── TCP relay: Host → GoPro HTTP ──
# Host talks to Pi:8080, socat forwards to GoPro:8080.
# This avoids needing a route to the GoPro subnet on the Host.

TCP_PORT=8080
SOCAT_TCP_PID=$(pgrep -f "socat.*TCP4.*:${TCP_PORT}" || true)
if [ -n "${SOCAT_TCP_PID:-}" ]; then
    kill "$SOCAT_TCP_PID" 2>/dev/null || true
    sleep 0.5
fi

nohup socat "TCP4-LISTEN:${TCP_PORT},fork,reuseaddr" "TCP4:${GOPRO_IP}:${TCP_PORT}" >/dev/null 2>&1 &
echo "  → TCP relay started: :${TCP_PORT} → ${GOPRO_IP}:${TCP_PORT} (PID $!)"

# ── UDP relay: GoPro → Host ──
# socat listens on the Pi and forwards to Host.
# GoPro sends UDP to the Pi's USB IP (because of SNAT on HTTP requests).

SOCAT_PID=$(pgrep -f "socat.*UDP4.*:${UDP_PORT}" || true)
if [ -n "${SOCAT_PID:-}" ]; then
    kill "$SOCAT_PID" 2>/dev/null || true
    sleep 0.5
fi

nohup socat "UDP4-LISTEN:${UDP_PORT},fork,reuseaddr" "UDP4:${HOST_IP}:${UDP_PORT}" >/dev/null 2>&1 &
echo "  → UDP relay started: :${UDP_PORT} → ${HOST_IP}:${UDP_PORT} (PID $!)"

echo ""
echo "Gateway setup complete."
echo "Host HTTP → Pi:${TCP_PORT} → GoPro:${TCP_PORT}"
echo "Host UDP  ← Pi:${UDP_PORT} ← GoPro (viewfinder stream)"
echo "No route to GoPro subnet needed on Host."
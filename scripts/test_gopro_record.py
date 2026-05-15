#!/usr/bin/env python3
"""GoPro WiFi 录制测试 — 在 Pi 上直接运行。

用法:
    python3 test_gopro_record.py [--ssid GP25108532] [--password fZM-HDn-fsg]

流程:
    1. 通过 nmcli 连接 GoPro WiFi AP
    2. 发送 HTTP 开始录制命令
    3. 等待 5 分钟
    4. 发送 HTTP 停止录制命令
"""

from __future__ import annotations

import asyncio
import argparse
import subprocess
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gopro_test")

GOPRO_IP = "10.5.5.9"
GOPRO_PORT = 8080
GOPRO_HTTP = f"http://{GOPRO_IP}:{GOPRO_PORT}"
WIFI_IFACE = "wlan0"


async def main():
    parser = argparse.ArgumentParser(description="GoPro WiFi 录制测试")
    parser.add_argument("--ssid", default="GP25108532")
    parser.add_argument("--password", default="fZM-HDn-fsg")
    parser.add_argument("--duration", type=int, default=300,
                        help="录制时长（秒），默认 300 (5分钟)")
    parser.add_argument("--skip-wifi", action="store_true",
                        help="跳过 WiFi 连接（已连时使用）")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GoPro WiFi 录制测试")
    logger.info("=" * 60)

    # ── Step 1: Connect WiFi ──
    if not args.skip_wifi:
        logger.info("Step 1: 连接 GoPro WiFi AP (%s)...", args.ssid)
        if not await connect_wifi(args.ssid, args.password):
            logger.error("WiFi 连接失败，退出")
            return 1
    else:
        logger.info("Step 1: 跳过 WiFi 连接（--skip-wifi）")

    # ── Step 2: Verify GoPro HTTP API reachable ──
    logger.info("Step 2: 检查 GoPro HTTP API 连通性...")
    if not await check_gopro():
        logger.error("GoPro HTTP API 不可达 (%s:%d)", GOPRO_IP, GOPRO_PORT)
        return 1

    # ── Step 3: Get camera status ──
    logger.info("Step 3: 获取相机状态...")
    status = await get_camera_state()
    if status:
        battery = status.get("status", {}).get("internal_battery_percentage", "?")
        encoding = status.get("status", {}).get("encoding_active", "?")
        logger.info("  电池: %s%%  正在录制: %s", battery, encoding)

    # ── Step 4: Start recording ──
    logger.info("Step 4: 开始录制...")
    if await start_recording():
        logger.info("  ✓ 录制已开始")
    else:
        logger.error("  ✗ 录制开始失败")
        return 1

    # ── Step 5: Wait ──
    duration = args.duration
    logger.info("Step 5: 等待 %d 秒 (%d 分钟)...", duration, duration // 60)
    remaining = duration
    while remaining > 0:
        if remaining % 30 == 0 or remaining <= 10:
            logger.info("  剩余 %d 秒...", remaining)
        await asyncio.sleep(1)
        remaining -= 1

    # ── Step 6: Stop recording ──
    logger.info("Step 6: 停止录制...")
    if await stop_recording():
        logger.info("  ✓ 录制已停止")
    else:
        logger.error("  ✗ 录制停止失败")
        return 1

    # ── Step 7: Final status ──
    logger.info("Step 7: 最终状态...")
    status = await get_camera_state()
    if status:
        battery = status.get("status", {}).get("internal_battery_percentage", "?")
        encoding = status.get("status", {}).get("encoding_active", "?")
        logger.info("  电池: %s%%  正在录制: %s", battery, encoding)

    logger.info("=" * 60)
    logger.info("测试完成！")
    logger.info("=" * 60)
    return 0


# ── WiFi ────────────────────────────────────────────

async def connect_wifi(ssid: str, password: str) -> bool:
    """Connect to GoPro WiFi AP via nmcli."""
    try:
        # Ensure WiFi is unblocked
        subprocess.run(
            ["sudo", "rfkill", "unblock", "wifi"],
            capture_output=True, timeout=5,
        )

        # Check if already connected
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "connection", "show"],
            capture_output=True, text=True, timeout=5,
        )
        if ssid in result.stdout:
            logger.info("  已连接到 %s", ssid)
            return True

        # Scan for the GoPro AP
        logger.info("  扫描 WiFi...")
        scan = subprocess.run(
            ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=10,
        )
        if ssid in scan.stdout:
            logger.info("  发现 %s", ssid)
        else:
            logger.warning("  WiFi 扫描未发现 %s（可能是隐藏 AP）", ssid)

        # Connect
        logger.info("  正在连接 %s...", ssid)
        result = subprocess.run(
            ["sudo", "nmcli", "device", "wifi", "connect",
             ssid, "password", password,
             "ifname", WIFI_IFACE],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0:
            logger.info("  WiFi 连接成功!")
            return True
        else:
            logger.error("  WiFi 连接失败: %s", result.stderr.strip())
            return False

    except subprocess.TimeoutExpired:
        logger.error("  WiFi 操作超时")
        return False
    except Exception as e:
        logger.error("  WiFi 错误: %s", e)
        return False


# ── GoPro HTTP API ─────────────────────────────────

async def check_gopro() -> bool:
    """Check if GoPro HTTP API is reachable."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((GOPRO_IP, GOPRO_PORT))
    sock.close()
    return result == 0


async def start_recording() -> bool:
    """Start GoPro recording via HTTP."""
    import aiohttp
    url = f"{GOPRO_HTTP}/gopro/camera/shutter/start?enable=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                ok = resp.status == 200
                logger.debug("  start_recording: HTTP %d", resp.status)
                return ok
    except Exception as e:
        logger.error("  start_recording error: %s", e)
        return False


async def stop_recording() -> bool:
    """Stop GoPro recording via HTTP."""
    import aiohttp
    url = f"{GOPRO_HTTP}/gopro/camera/shutter/start?enable=0"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                ok = resp.status == 200
                logger.debug("  stop_recording: HTTP %d", resp.status)
                return ok
    except Exception as e:
        logger.error("  stop_recording error: %s", e)
        return False


async def get_camera_state() -> dict | None:
    """Get GoPro camera status via HTTP."""
    import aiohttp
    url = f"{GOPRO_HTTP}/gopro/camera/state"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug("  get_camera_state error: %s", e)
    return None


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

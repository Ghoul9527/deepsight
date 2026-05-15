#!/usr/bin/env python3
"""从 MacBook/Host 通过 UDP 向 Pi 发送 GoPro 录制命令。

流程:
    1. 通过 UDP 向 Pi 发送 GoPro 连接命令
    2. 发送开始录制命令
    3. 等待 5 分钟
    4. 发送停止录制命令
    5. 检查 GoPro 状态

通信路径: Host → UDP(5100) → Pi → MessageRouter → GoProController → HTTP → GoPro
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gopro_test")

PI_ADDRESS = "192.168.20.51"
PI_UDP_PORT = 5100


async def send_udp_command(msg_json: str) -> None:
    """Send a JSON message to Pi via UDP."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.sendto(msg_json.encode(), (PI_ADDRESS, PI_UDP_PORT))
    sock.close()
    logger.debug("  UDP sent → %s:%d", PI_ADDRESS, PI_UDP_PORT)


def make_message(node_id: str, msg_type: str, payload: dict) -> str:
    """Build a DeepSight protocol JSON message."""
    import json
    import uuid
    import time as _time
    return json.dumps({
        "msg_id": str(uuid.uuid4())[:8],
        "timestamp_ns": int(_time.time() * 1e9),
        "node_id": node_id,
        "type": msg_type,
        "version": "1.0",
        "payload": payload,
    })


async def check_gopro_status_http():
    """Check GoPro status via Pi HTTP API."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{PI_ADDRESS}:5101/gopro/status", timeout=5
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug("Status check error: %s", e)
    return None


async def main():
    logger.info("=" * 60)
    logger.info("GoPro 录制测试 — Host → UDP → Pi → GoPro")
    logger.info("=" * 60)

    # Step 1: Check current GoPro status
    logger.info("\n[1/5] 检查 GoPro 当前状态...")
    status = await check_gopro_status_http()
    if status:
        logger.info("  connected: %s", status.get("connected"))
        logger.info("  recording: %s", status.get("recording"))
        logger.info("  battery: %s%%", status.get("battery_pct"))
    else:
        logger.warning("  无法获取 GoPro 状态")

    # Step 2: Send GoPro connect command via UDP
    logger.info("\n[2/5] 发送 GoPro 连接命令 (UDP)...")
    connect_msg = make_message("host", "sys.heartbeat", {"action": "gopro_connect"})
    await send_udp_command(connect_msg)
    logger.info("  已发送连接请求")

    # Wait a bit for connection
    logger.info("  等待连接建立 (5s)...")
    await asyncio.sleep(5)

    # Check status again
    status = await check_gopro_status_http()
    if status:
        if status.get("connected"):
            logger.info("  ✓ GoPro 已连接")
        else:
            logger.warning("  ⚠ GoPro 仍显示未连接（WiFi AP 可能没开）")

    # Step 3: Send START recording command via UDP
    logger.info("\n[3/5] 发送开始录制命令 (UDP → cmd.gopro.record)...")
    start_msg = make_message("host", "cmd.gopro.record", {"start": True})
    await send_udp_command(start_msg)
    logger.info("  已发送开始录制命令")
    await asyncio.sleep(1)

    # Verify
    status = await check_gopro_status_http()
    if status:
        recording = status.get("recording", False)
        if recording:
            logger.info("  ✓ 相机正在录制")
        else:
            logger.warning("  ⚠ 相机未显示录制状态")

    # Step 4: Wait 5 minutes
    duration = 300  # 5 minutes
    logger.info("\n[4/5] 等待 %d 秒 (%d 分钟)...", duration, duration // 60)
    start_time = time.monotonic()
    remaining = duration
    while remaining > 0:
        if remaining % 30 == 0 or remaining <= 10:
            elapsed = time.monotonic() - start_time
            logger.info("  剩余 %d 秒 (已过 %.0f 秒)...", remaining, elapsed)
            # Check status periodically
            status = await check_gopro_status_http()
            if status:
                logger.info("    录制中: %s  电池: %s%%",
                           status.get("recording"), status.get("battery_pct"))
        await asyncio.sleep(1)
        remaining -= 1

    # Step 5: Send STOP recording command via UDP
    logger.info("\n[5/5] 发送停止录制命令 (UDP → cmd.gopro.record)...")
    stop_msg = make_message("host", "cmd.gopro.record", {"start": False})
    await send_udp_command(stop_msg)
    logger.info("  已发送停止录制命令")
    await asyncio.sleep(2)

    # Final status
    status = await check_gopro_status_http()
    if status:
        logger.info("\n最终状态:")
        logger.info("  connected: %s", status.get("connected"))
        logger.info("  recording: %s", status.get("recording"))
        logger.info("  battery: %s%%", status.get("battery_pct"))

    logger.info("\n" + "=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

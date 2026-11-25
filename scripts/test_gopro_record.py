#!/usr/bin/env python3
"""GoPro MISSION USB 录制测试 — 在 Pi 上直接运行。

用法:
    python3 test_gopro_record.py --url http://172.2X.1YZ.51:8080

流程:
    1. 通过 USB 网络检查 MISSION 1 PRO
    2. 发送 HTTP 开始录制命令
    3. 等待指定时长
    4. 停止录制并等待文件封装完成
"""

from __future__ import annotations

import asyncio
import argparse
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gopro_test")

GOPRO_HTTP = "http://172.25.132.51:8080"


async def main():
    global GOPRO_HTTP
    parser = argparse.ArgumentParser(description="GoPro MISSION USB 录制测试")
    parser.add_argument("--url", default=GOPRO_HTTP,
                        help="相机 USB HTTP 地址")
    parser.add_argument("--duration", type=int, default=300,
                        help="录制时长（秒），默认 300 (5分钟)")
    args = parser.parse_args()
    GOPRO_HTTP = args.url.rstrip("/")

    logger.info("=" * 60)
    logger.info("GoPro MISSION USB 录制测试")
    logger.info("=" * 60)

    # ── Step 1: Verify GoPro HTTP API reachable ──
    logger.info("Step 1: 检查 GoPro USB HTTP API 连通性...")
    if not await check_gopro():
        logger.error("GoPro HTTP API 不可达 (%s)", GOPRO_HTTP)
        return 1

    # ── Step 3: Get camera status ──
    logger.info("Step 3: 获取相机状态...")
    status = await get_camera_state()
    if status:
        battery = status.get("status", {}).get("70", "?")
        encoding = status.get("status", {}).get("10", "?")
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
    if await stop_recording() and await wait_finalized():
        logger.info("  ✓ 录制已停止，文件封装完成")
    else:
        logger.error("  ✗ 录制停止失败")
        return 1

    # ── Step 7: Final status ──
    logger.info("Step 7: 最终状态...")
    status = await get_camera_state()
    if status:
        battery = status.get("status", {}).get("70", "?")
        encoding = status.get("status", {}).get("10", "?")
        logger.info("  电池: %s%%  正在录制: %s", battery, encoding)

    logger.info("=" * 60)
    logger.info("测试完成！")
    logger.info("=" * 60)
    return 0


# ── GoPro HTTP API ─────────────────────────────────

async def check_gopro() -> bool:
    """Check if GoPro HTTP API is reachable."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GOPRO_HTTP}/gopro/camera/info", timeout=3
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


async def start_recording() -> bool:
    """Start GoPro recording via HTTP."""
    import aiohttp
    url = f"{GOPRO_HTTP}/gopro/camera/shutter/start"
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
    url = f"{GOPRO_HTTP}/gopro/camera/shutter/stop"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                ok = resp.status == 200
                logger.debug("  stop_recording: HTTP %d", resp.status)
                return ok
    except Exception as e:
        logger.error("  stop_recording error: %s", e)
        return False


async def wait_finalized(timeout_s: float = 15.0) -> bool:
    """Wait until MISSION reports neither encoding nor busy."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        state = await get_camera_state()
        status = state.get("status", {}) if state else {}
        if not int(status.get("10", 0)) and not int(status.get("8", 0)):
            return True
        await asyncio.sleep(0.25)
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

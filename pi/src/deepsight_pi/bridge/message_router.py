"""Message router — routes messages between Host, Pico, and STM32 links."""

from __future__ import annotations

import asyncio
import logging
import math
import time

from deepsight_pi.bridge.host_link import HostLink
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.bridge.stm32_link import Stm32Link
from deepsight_pi.gopro.base import GoProController
from deepsight_pi.capture.base import CaptureDevice
from deepsight_shared.protocol import (
    Message, make_heartbeat, sys_ack, tel_gopro_status, tel_pi_status,
    tel_imu, tel_depth, tel_env, tel_leak, tel_winch_state,
)

logger = logging.getLogger("pi.bridge.router")


class MessageRouter:
    def __init__(self, host_link: HostLink, pico_link: PicoLink,
                 stm32_link: Stm32Link, gopro: GoProController,
                 capture: CaptureDevice):
        self._host = host_link
        self._pico = pico_link
        self._stm32 = stm32_link
        self._gopro = gopro
        self._capture = capture
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._route_host_to_downstream())
        asyncio.create_task(self._generate_telemetry())
        logger.info("MessageRouter started")

    async def _route_host_to_downstream(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self._host.recv_queue.get(), timeout=0.1)
                await self._handle_message(msg)
            except asyncio.TimeoutError:
                pass

    async def _handle_message(self, msg: Message):
        logger.debug("Routing: %s → %s", msg.node_id, msg.type)

        # Route based on message type
        if msg.type.startswith("cmd.servo") or msg.type.startswith("cmd.lighting"):
            await self._pico.send(msg)
        elif msg.type.startswith("cmd.winch"):
            await self._stm32.send(msg)
        elif msg.type.startswith("cmd.gopro"):
            await self._handle_gopro_cmd(msg)
        elif msg.type == "sys.heartbeat":
            pass  # Just acknowledge
        elif msg.type == "sys.safety":
            # Forward safety commands to all MCUs
            await self._pico.send(msg)
            await self._stm32.send(msg)
        else:
            logger.debug("Unrouted message: %s", msg.type)

    async def _handle_gopro_cmd(self, msg: Message):
        if msg.type == "cmd.gopro.record":
            start = msg.payload.get("start", False)
            if start:
                await self._gopro.start_recording()
            else:
                await self._gopro.stop_recording()
        elif msg.type == "cmd.gopro.mode":
            mode = msg.payload.get("mode", "video")
            group_map = {"video": 0, "photo": 1, "timelapse": 2}
            group_id = group_map.get(mode, 0)
            await self._gopro.load_preset_group(group_id)

    async def _generate_telemetry(self):
        """Periodically generate and send all telemetry to Host."""
        t0 = time.monotonic()
        while self._running:
            await asyncio.sleep(0.2)  # 5 Hz
            t = time.monotonic() - t0

            # ── Pico-originated telemetry (mock) ──

            # IMU — gentle sine-wave motion
            msg = tel_imu("pico",
                yaw=math.sin(t * 0.3) * 8.0,
                pitch=math.sin(t * 0.5 + 1.2) * 5.0,
                roll=math.sin(t * 0.4 + 2.5) * 3.0,
                ax=math.sin(t * 0.2) * 0.1,
                ay=math.cos(t * 0.25) * 0.1,
                az=9.81 + math.sin(t * 0.15) * 0.05,
            )
            await self._host.send(msg)

            # Depth — slow oscillation around 5 m
            depth_m = 5.0 + math.sin(t * 0.08) * 3.0
            msg = tel_depth("pico",
                depth_m=round(depth_m, 2),
                pressure_mbar=round(1013.25 + depth_m * 100.0, 1),
                temperature_c=round(22.0 + math.sin(t * 0.05) * 1.5, 1),
            )
            await self._host.send(msg)

            # Environment
            msg = tel_env("pico",
                temp_c=round(22.0 + math.sin(t * 0.03) * 2.0, 1),
                humidity=round(65.0 + math.sin(t * 0.04) * 5.0, 1),
                pressure_hpa=round(1013.0 + math.sin(t * 0.02) * 3.0, 1),
            )
            await self._host.send(msg)

            # ── STM32-originated telemetry (mock) ──

            # Winch state — slow descent simulation
            pos_mm = 2500 + math.sin(t * 0.06) * 1500
            speed = math.cos(t * 0.06) * 80
            msg = tel_winch_state("stm32",
                position_mm=round(pos_mm, 1),
                speed_mm_s=round(speed, 1),
                limit_top=pos_mm < 50,
                limit_bottom=pos_mm > 4900,
                e_stop=False,
                current_a=round(1.5 + abs(speed) * 0.02, 2),
            )
            await self._host.send(msg)

            # ── Pi-originated telemetry ──

            # GoPro status
            status = await self._gopro.get_status()
            msg = tel_gopro_status(
                "pi", status.recording, status.battery_pct,
                status.storage_gb_free, status.mode,
            )
            await self._host.send(msg)

            # Pi system status
            msg = tel_pi_status("pi",
                cpu_temp=round(45.0 + math.sin(t * 0.1) * 8.0, 1),
                cpu_pct=round(15.0 + math.sin(t * 0.15) * 10.0, 1),
                mem_pct=round(30.0 + math.sin(t * 0.12) * 5.0, 1),
                uptime_s=t,
            )
            await self._host.send(msg)

            # Pi heartbeat
            msg = make_heartbeat("pi")
            await self._host.send(msg)

    async def stop(self):
        self._running = False

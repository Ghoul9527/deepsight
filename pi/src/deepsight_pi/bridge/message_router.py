"""Message router — routes messages between Host, Pico, and STM32 links."""

from __future__ import annotations

import asyncio
import logging
import time

from deepsight_pi.bridge.host_link import HostLink
from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_pi.bridge.stm32_link import Stm32Link
from deepsight_shared.protocol import (
    Message, make_heartbeat, new_message, sys_pong, sys_startup_status,
    tel_depth, tel_env, tel_imu, tel_leak, tel_pi_status,
)

logger = logging.getLogger("pi.bridge.router")


class MessageRouter:
    def __init__(self, host_link: HostLink, pico_link: PicoLink,
                 stm32_link: Stm32Link):
        self._host = host_link
        self._pico = pico_link
        self._stm32 = stm32_link
        self._running = False
        # Coalesced servo commands: only the latest angle per servo is kept
        self._servo_buf: dict[int, Message] = {}
        self._lighting_buf: Message | None = None
        self._send_interval = 0.025  # 40 Hz flush rate

    async def start(self):
        self._running = True
        asyncio.create_task(self._route_host_to_downstream())
        asyncio.create_task(self._flush_downstream())
        asyncio.create_task(self._generate_telemetry())
        asyncio.create_task(self._poll_pico())
        logger.info("MessageRouter started")

    async def _route_host_to_downstream(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self._host.recv_queue.get(), timeout=0.1)
                await self._handle_message(msg)
            except asyncio.TimeoutError:
                pass

    async def _flush_downstream(self):
        """Send coalesced servo/lighting commands at fixed rate."""
        while self._running:
            await asyncio.sleep(self._send_interval)
            count = 0
            sent_ids = []
            for sid, msg in list(self._servo_buf.items()):
                p = msg.payload
                logger.debug("[PI tx seq=%s] servo %s -> %.1f",
                             p.get("seq", "?"), p.get("servo_id", "?"),
                             p.get("angle", 0))
                await self._pico.send(msg)
                sent_ids.append(sid)
                count += 1
                if count >= 4:
                    break
            for sid in sent_ids:
                self._servo_buf.pop(sid, None)
            # Flush lighting
            if self._lighting_buf is not None:
                await self._pico.send(self._lighting_buf)
                self._lighting_buf = None

    async def _handle_message(self, msg: Message):
        logger.debug("Routing: %s → %s", msg.node_id, msg.type)

        if msg.type.startswith("cmd.servo"):
            # Coalesce: keep only the latest command per servo
            p = msg.payload
            sid = p.get("servo_id", 0)
            logger.debug("[PI rx seq=%s] servo %s -> %.1f  payload_keys=%s",
                         p.get("seq", "?"), sid, p.get("angle", 0), list(p.keys()))
            self._servo_buf[sid] = msg
        elif msg.type.startswith("cmd.lighting"):
            self._lighting_buf = msg
        elif msg.type.startswith("cmd.winch"):
            await self._stm32.send(msg)
        elif msg.type == "sys.ping":
            seq = msg.payload.get("seq", 0)
            await self._host.send(sys_pong("pi", seq))
        elif msg.type == "cmd.sys.startup_check":
            await self.startup_check()
        elif msg.type == "sys.heartbeat":
            await self._pico.send(msg)
        elif msg.type == "sys.safety":
            await self._pico.send(msg)
            await self._stm32.send(msg)
        else:
            logger.debug("Unrouted message: %s", msg.type)

    async def _generate_telemetry(self):
        """Forward real telemetry from Pico/STM32 and Pi system stats to Host."""
        prev_idle, prev_total = 0, 0
        while self._running:
            await asyncio.sleep(0.2)  # 5 Hz

            # ── Drain Pico recv queue ──
            pico_alive = False
            while not self._pico.recv_queue.empty():
                try:
                    msg = self._pico.recv_queue.get_nowait()
                    if msg.type == "t":
                        await self._translate_compact(msg)
                    else:
                        await self._host.send(msg)
                    pico_alive = True
                except asyncio.QueueEmpty:
                    break
            if pico_alive:
                await self._host.send(make_heartbeat("pico"))

            # ── Drain STM32 recv queue ──
            stm32_alive = False
            while not self._stm32.recv_queue.empty():
                try:
                    msg = self._stm32.recv_queue.get_nowait()
                    await self._host.send(msg)
                    stm32_alive = True
                except asyncio.QueueEmpty:
                    break
            if stm32_alive:
                await self._host.send(make_heartbeat("stm32"))

            # ── Pi system telemetry ──
            cpu_temp = _read_cpu_temp()
            mem_pct = _read_mem_pct()
            cpu_pct, prev_idle, prev_total = _read_cpu_pct(prev_idle, prev_total)

            msg = tel_pi_status("pi",
                cpu_temp=cpu_temp,
                cpu_pct=cpu_pct,
                mem_pct=mem_pct,
                uptime_s=_read_uptime(),
            )
            await self._host.send(msg)

            msg = make_heartbeat("pi")
            await self._host.send(msg)

    async def _poll_pico(self):
        """Poll Pico for telemetry at 1 Hz. Pico responds immediately,
        avoiding the 1s blocking write that occurs with periodic output."""
        await asyncio.sleep(2.0)  # wait for Pico boot
        while self._running:
            try:
                msg = new_message("pi", "tel.poll")
                await self._pico.send(msg)
            except Exception as e:
                logger.debug("Poll Pico error: %s", e)
            await asyncio.sleep(1.0)

    async def _translate_compact(self, msg: Message):
        """Split compact type 't' into individual tel.imu/depth/env/leak."""
        p = msg.payload
        node = msg.node_id
        logger.debug("[PI poll_resp] s0=%s s1=%s rs=%s hz=%s st=%s",
                     p.get("s0", "?"), p.get("s1", "?"),
                     p.get("rs", "?"), p.get("hz", "?"), p.get("st", "?"))

        await self._host.send(tel_imu(
            node,
            yaw=float(p.get("y", 0)),
            pitch=float(p.get("p", 0)),
            roll=float(p.get("r", 0)),
            ax=float(p.get("ax", 0)),
            ay=float(p.get("ay", 0)),
            az=float(p.get("az", 0)),
        ))
        await self._host.send(tel_depth(
            node,
            depth_m=float(p.get("d", 0)),
            pressure_mbar=float(p.get("pr", 0)),
            temperature_c=float(p.get("wt", 0)),
        ))
        await self._host.send(tel_env(
            node,
            temp_c=float(p.get("et", 0)),
            humidity=float(p.get("eh", 0)),
            pressure_hpa=float(p.get("ep", 0)),
        ))
        for ch in range(4):
            leaks = p.get("le", [False, False, False, False])
            wet = bool(leaks[ch]) if ch < len(leaks) else False
            await self._host.send(tel_leak(node, ch, wet))

    async def startup_check(self) -> dict[str, dict]:
        """Run self-checks and report to Host."""
        checks: dict[str, dict] = {
            "host_link": {"ok": True, "detail": "UDP link active"},
        }

        msg = sys_startup_status("pi", checks)
        await self._host.send(msg)

        logger.info("Startup check: %s",
                     {k: "OK" if v["ok"] else "FAIL" for k, v in checks.items()})
        return checks

    async def stop(self):
        self._running = False


# ── Pi system stat helpers ──

def _read_uptime() -> float:
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def _read_cpu_temp() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return float(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return 0.0


def _read_mem_pct() -> float:
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        total = available = 0
        for line in lines:
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1])
        if total > 0:
            return round((1 - available / total) * 100, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _read_cpu_pct(prev_idle: int, prev_total: int) -> tuple[float, int, int]:
    """Return (cpu_pct, idle, total). First call seeds the diff baseline."""
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        parts = line.split()
        if parts[0] != "cpu":
            return 0.0, prev_idle, prev_total
        vals = [int(x) for x in parts[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
        total = sum(vals)
        if prev_total == 0:
            return 0.0, idle, total
        idle_d = idle - prev_idle
        total_d = total - prev_total
        if total_d > 0:
            return round((1 - idle_d / total_d) * 100, 1), idle, total
    except (OSError, ValueError, IndexError):
        pass
    return 0.0, prev_idle, prev_total

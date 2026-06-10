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
                 stm32_link: Stm32Link, servo_config: dict | None = None,
                 stabilizer_config: dict | None = None,
                 fin_config: dict | None = None):
        self._host = host_link
        self._pico = pico_link
        self._stm32 = stm32_link
        self._running = False
        # Coalesced servo commands: only the latest angle per servo is kept
        self._servo_buf: dict[int, Message] = {}
        self._lighting_buf: Message | None = None
        self._send_interval = 0.02   # 50 Hz flush rate

        # Local servo controller (Pi drives PCA9685 directly)
        self._servo = None
        if servo_config and servo_config.get("pca9685"):
            from deepsight_pi.servo_controller import ServoController
            self._servo = ServoController(servo_config)
            logger.info("Servo controller: local PCA9685 mode")

        # Roll stabilizer (IMU → roll servo auto-correction)
        self._stabilizer = None
        if stabilizer_config and stabilizer_config.get("roll", {}).get("enabled"):
            from deepsight_pi.roll_stabilizer import RollStabilizer
            self._stabilizer = RollStabilizer(self._servo, stabilizer_config["roll"])
            logger.info("Roll stabilizer: enabled")

        # Fin-yaw coupling (yaw + vertical speed → fin deflection)
        self._fin = None
        if fin_config and fin_config.get("enabled") and self._servo:
            from deepsight_pi.fin_controller import FinController
            self._fin = FinController(self._servo, fin_config)
            logger.info("Fin coupling: enabled")

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

            if self._servo is not None:
                self._servo.check_safety()

            count = 0
            sent_ids = []
            for sid, msg in list(self._servo_buf.items()):
                # Skip roll servo when stabilizer is active
                if sid == 2 and self._stabilizer is not None and self._stabilizer.is_active():
                    sent_ids.append(sid)
                    logger.debug("[PI tx] servo 2 skipped (stabilizer active)")
                    continue
                # Skip fin servos when coupling is active
                if sid in (3, 4) and self._fin is not None and self._fin.is_active():
                    sent_ids.append(sid)
                    continue
                p = msg.payload
                angle = p.get("angle", 90.0)
                if self._servo is not None:
                    self._servo.set_angle(sid, angle)
                else:
                    await self._pico.send(msg)
                logger.debug("[PI tx seq=%s] servo %s -> %.1f",
                             p.get("seq", "?"), p.get("servo_id", "?"), angle)
                sent_ids.append(sid)
                count += 1
                if count >= 4:
                    break
            for sid in sent_ids:
                self._servo_buf.pop(sid, None)
            # Flush lighting
            if self._lighting_buf is not None:
                p = self._lighting_buf.payload
                brightness = p.get("brightness", 0.0)
                if self._servo is not None:
                    self._servo.set_brightness(0, brightness)
                else:
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
            if sid == 2 and self._stabilizer is not None:
                self._stabilizer.notify_manual()
            if sid == 0 and self._fin is not None:
                self._fin.update_yaw(p.get("angle", 90.0))
                self._fin.step()
            if sid in (3, 4) and self._fin is not None:
                self._fin.notify_manual(p.get("angle", 90.0))
        elif msg.type == "cmd.fin.auto":
            if self._fin is not None:
                self._fin.enable_auto()
        elif msg.type == "cmd.fin.manual":
            if self._fin is not None:
                self._fin.disable_auto()
        elif msg.type == "cmd.sim.depth":
            if self._fin is not None:
                p = msg.payload
                self._fin.update_depth(p.get("depth_m", 0.0), sim=True,
                                       speed_ms=p.get("speed_ms", 0.0))
                self._fin.step()
        elif msg.type.startswith("cmd.lighting") or msg.type == "cmd.light":
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
        elif msg.type.startswith("ota."):
            await self._pico.send(msg)
        else:
            logger.debug("Unrouted message: %s", msg.type)

    async def _generate_telemetry(self):
        """Forward real telemetry from Pico/STM32 and Pi system stats to Host."""
        prev_idle, prev_total = 0, 0
        while self._running:
            await asyncio.sleep(0.05)  # 20 Hz

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
        """Poll Pico for telemetry at 20 Hz. Pico responds immediately,
        avoiding the 1s blocking write that occurs with periodic output."""
        await asyncio.sleep(2.0)  # wait for Pico boot
        while self._running:
            try:
                msg = new_message("pi", "tel.poll")
                await self._pico.send(msg)
            except Exception as e:
                logger.debug("Poll Pico error: %s", e)
            await asyncio.sleep(0.05)

    async def _translate_compact(self, msg: Message):
        """Split compact type 't' into individual tel.imu/depth/env/leak."""
        p = msg.payload
        node = msg.node_id
        logger.debug("[PI poll_resp] hz=%s st=%s",
                     p.get("hz", "?"), p.get("st", "?"))

        roll = float(p.get("r", 0))
        await self._host.send(tel_imu(
            node,
            yaw=float(p.get("y", 0)),
            pitch=float(p.get("p", 0)),
            roll=roll,
            ax=float(p.get("ax", 0)),
            ay=float(p.get("ay", 0)),
            az=float(p.get("az", 0)),
        ))
        if self._stabilizer is not None:
            self._stabilizer.update_imu(roll)
            self._stabilizer.step()
        depth_m = float(p.get("d", 0))
        await self._host.send(tel_depth(
            node,
            depth_m=depth_m,
            pressure_mbar=float(p.get("pr", 0)),
            temperature_c=float(p.get("wt", 0)),
        ))
        if self._fin is not None:
            self._fin.update_depth(depth_m)
            self._fin.step()
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

"""DeepSight Host Application — main QApplication and system orchestration."""

from __future__ import annotations

import asyncio
import logging
import queue
import sys
import threading
import time

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from deepsight_host.config import HostConfig
from deepsight_host.ui.main_window import MainWindow
from deepsight_host.network.udp_link import UDPLink
from deepsight_host.network.ws_link import WsLink
from deepsight_host.network.node_registry import NodeRegistry
from deepsight_host.network.message_bus import MessageBus
from deepsight_host.tracking.registry import get_tracker
from deepsight_host.video.no_video_source import NoVideoSource
from deepsight_host.video.stream_receiver import StreamReceiver
from deepsight_host.control.framer import Framer
from deepsight_host.control.servo_mapper import ServoMapper
from deepsight_host.control.pid import PIDController
from deepsight_host.control.controller import GameController
from deepsight_host.logging.structured_logger import setup_logging
from deepsight_host.logging.telemetry_recorder import TelemetryRecorder
from deepsight_host.diagnostics.startup_check import StartupCheck
from deepsight_host.gopro import GoProClient

from deepsight_shared.protocol import (
    make_heartbeat, cmd_servo_set, sys_safety, sys_ping,
    cmd_startup_check, Message,
)

logger = logging.getLogger("host.app")

TRACKING_COLORS = [(0, 255, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255),
                   (255, 128, 0), (128, 255, 0), (0, 128, 255)]


class HostApp:
    def __init__(self):
        self.config = HostConfig()
        setup_logging(log_dir=self.config.log_dir)
        self._running = False

        # Qt
        self._qt_app = QApplication(sys.argv)
        self._window = MainWindow()
        self._window.set_config(self.config)

        # Async event loop (runs in background thread for network I/O)
        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(
            target=self._run_async_loop, daemon=True)

        # Network
        self._udp = UDPLink(
            self.config.udp_port,
            self.config.pi_address,
            self.config.pi_udp_port,
        )
        self._ws = WsLink(
            self.config.ws_port,
            f"ws://{self.config.pi_address}:{self.config.pi_ws_port}/ws",
        )
        self._registry = NodeRegistry()
        self._bus = MessageBus()

        # Thread-safe queue for incoming telemetry (async → Qt main thread)
        self._incoming_queue: queue.Queue[Message] = queue.Queue()

        # Video source: real stream from Pi, or black "No Signal" placeholder
        self._no_signal_source = NoVideoSource(
            self.config.frame_width,
            self.config.frame_height,
            self.config.fps,
        )
        if self.config.stream_url:
            logger.info("Using video stream: %s", self.config.stream_url)
            self._video_source = StreamReceiver(self.config.stream_url)
        else:
            self._video_source = self._no_signal_source

        # Tracking
        self._tracker = get_tracker(
            self.config.tracking_mode,
            confidence_threshold=self.config.confidence_threshold,
            iou_threshold=self.config.iou_threshold,
        )

        # Control pipeline
        self._framer = Framer(
            servo_mapper=ServoMapper(),
            pid_pan=PIDController(),
            pid_tilt=PIDController(),
        )

        # Game controller input
        self._controller = GameController()

        # GoPro HTTP client (talks to Pi reverse proxy)
        self._gopro = GoProClient(
            f"http://{self.config.pi_address}:8080")

        # Session recording
        self._recorder = TelemetryRecorder()

        # Startup self-check
        self._startup_check = StartupCheck()
        self._first_frame_seen = False

        # Preset switch guard — cancel stale restarts on rapid switching
        self._restart_gen = 0

        # Performance tracking
        self._frame_count = 0
        self._fps_ema = 0.0
        self._last_fps_update = time.monotonic()
        self._pi_stream_latency_ms: float = 0.0  # PCR-based GoPro→Pi latency

        # Timers
        self._frame_timer = QTimer()
        self._heartbeat_timer = QTimer()
        self._registry_timer = QTimer()
        self._telemetry_timer = QTimer()

        self._connect_signals()
        self._update_tracking_status()

    def _run_async_loop(self):
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def _schedule_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    def _connect_signals(self):
        self._frame_timer.timeout.connect(self._process_frame)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._registry_timer.timeout.connect(self._check_nodes)
        self._telemetry_timer.timeout.connect(self._process_telemetry)

        cp = self._window.control_panel
        cp.pan_changed.connect(lambda v: self._send_servo(0, float(v)))
        cp.tilt_changed.connect(lambda v: self._send_servo(1, float(v)))
        cp.e_stop.connect(self._emergency_stop)

        self._window.tracking_view.mode_changed.connect(self._switch_tracking_mode)
        self._window.tracking_view.reset_button.clicked.connect(self._reset_tracker)

        self._registry.on_state_change(self._on_node_state_change)

        # Game controller signals → control panel
        self._controller.pan_changed.connect(
            lambda v: self._window.control_panel.pan_changed.emit(v))
        self._controller.tilt_changed.connect(
            lambda v: self._window.control_panel.tilt_changed.emit(v))
        self._controller.e_stop.connect(self._emergency_stop)
        self._controller.tracking_toggle.connect(
            lambda: self._switch_tracking_mode(
                "precise" if self.config.tracking_mode == "fast" else "fast"
            ))

        # GoPro commands → direct HTTP through Pi proxy
        self._window.gopro_command.connect(self._on_gopro_command)
        self._window.gopro_probe.connect(self._on_gopro_probe)
        self._window.gopro_get_presets.connect(self._on_get_presets)
        self._window.gopro_load_preset.connect(self._on_load_preset)

        # Startup self-check wiring
        self._startup_check.set_send_udp(
            lambda: self._schedule_async(
                self._udp.send(sys_ping("host", 0))))
        self._startup_check.set_send_startup_check(
            lambda: self._schedule_async(
                self._udp.send(cmd_startup_check("host"))))
        self._startup_check.check_result.connect(self._on_check_result)
        self._startup_check.all_done.connect(self._on_check_all_done)

    def run(self):
        logger.info("Starting DeepSight Host...")
        self._running = True

        # Start async event loop thread
        self._async_thread.start()
        self._schedule_async(self._network_loop())

        # Start Qt timers (ms)
        self._frame_timer.start(1000 // self.config.fps)  # ~33ms for 30fps
        self._heartbeat_timer.start(500)
        self._registry_timer.start(1000)
        self._telemetry_timer.start(50)  # drain incoming queue at 20 Hz

        self._window.showFullScreen()
        self._controller.start()
        self._recorder.start()
        self._update_tracking_status()

        # Start startup self-check (delayed, let network settle)
        QTimer.singleShot(1000, self._startup_check.start)
        model_ok = not getattr(self._tracker, 'is_mock', True)
        stream_ok = bool(self.config.stream_url)
        parts = [
            "Tracking: %s" % self.config.tracking_mode.upper(),
            "Model: %s" % ("LOADED" if model_ok else "UNAVAILABLE"),
            "Stream: %s" % ("LIVE" if stream_ok else "NONE"),
        ]
        self._window.set_status_message(" | ".join(parts))

        return self._qt_app.exec()

    def _update_tracking_status(self):
        is_mock = getattr(self._tracker, 'is_mock', True)
        mode = self.config.tracking_mode.upper()
        status = f"{mode} - Model Unavailable" if is_mock else f"{mode} - Model Active"
        self._window.tracking_view.set_status(status)

    async def _network_loop(self):
        await self._udp.start()
        # Start UDP socket → recv_queue pump
        asyncio.ensure_future(self._udp.recv_loop())
        asyncio.ensure_future(self._ws.start())
        # Drain recv queues into thread-safe incoming queue
        asyncio.ensure_future(self._udp_recv_loop())
        asyncio.ensure_future(self._ws_recv_loop())

        # Start GoPro HTTP client (talks through Pi proxy)
        await self._gopro.open()

        # Start video stream receiver if using real stream (not mock)
        if isinstance(self._video_source, StreamReceiver):
            await self._video_source.start()

        # Poll Pi for PCR-based stream latency + GoPro status
        asyncio.ensure_future(self._poll_pi_stream_latency())
        asyncio.ensure_future(self._poll_gopro_status())

    async def _udp_recv_loop(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self._udp.recv_queue.get(), timeout=0.1)
                self._incoming_queue.put(msg)
            except asyncio.TimeoutError:
                pass

    async def _ws_recv_loop(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self._ws.recv_queue.get(), timeout=0.1)
                self._incoming_queue.put(msg)
            except asyncio.TimeoutError:
                pass

    async def _poll_pi_stream_latency(self):
        """Poll Pi /stream/status for PCR-based GoPro→Pi latency."""
        import json
        from urllib.request import urlopen
        loop = asyncio.get_event_loop()
        url = f"http://{self.config.pi_address}:{self.config.pi_ws_port}/stream/status"
        while self._running:
            try:
                resp = await loop.run_in_executor(
                    None, lambda: urlopen(url, timeout=2))
                data = json.loads(resp.read())
                self._pi_stream_latency_ms = float(data.get("pcr_latency_ms", 0))
            except Exception:
                pass
            await asyncio.sleep(2)  # 0.5 Hz poll is plenty

    async def _poll_gopro_status(self):
        """Poll GoPro camera state through Pi proxy (0.5 Hz).

        Emits gopro_status_updated with a dict containing:
          - online: bool
          - recording: bool
          - battery_pct: int
          - sd_remaining_bytes: int
          - model_name: str
          - busy: bool
        """
        while self._running:
            try:
                status = await self._gopro.get_status()
                data = {
                    "online": True,
                    "recording": status.recording,
                    "battery_pct": int(status.battery_pct),
                    "sd_remaining_bytes": int(status.storage_gb_free * 1e9),
                    "model_name": status.model_name,
                    "busy": status.busy,
                }
                self._window.gopro_status_updated.emit(data)
            except Exception:
                self._window.gopro_status_updated.emit({"online": False})
            await asyncio.sleep(2)

    def _process_frame(self):
        frame = self._video_source.read()
        if frame is None:
            # Only show placeholder when stream is actually dead (>3s no frame)
            if (isinstance(self._video_source, StreamReceiver)
                    and self._video_source.stale()):
                frame = self._no_signal_source.read()
                self._window.video_preview.update_frame(frame, 0.0)
            # If stream is not stale, keep showing the last good frame (skip)
            return

        if not self._first_frame_seen:
            self._first_frame_seen = True
            self._startup_check.on_frame_received()

        self._frame_count += 1
        t0 = time.monotonic()

        # Tracking
        result = self._tracker.process_frame(frame)
        track_latency = (time.monotonic() - t0) * 1000.0

        # Draw overlay on frame
        self._draw_overlay(frame, result)

        # End-to-end latency estimate (ms)
        #   GoPro→Pi:    210ms FAQ baseline + PCR delta
        #   Pi→Host:     <1ms Ethernet
        #   Host→screen: frame_age_ms (ffmpeg decode + Qt display gap)
        ee_latency = 210.0 + self._pi_stream_latency_ms + self._video_source.frame_age_ms()

        # Control: compute servo angles
        if result is not None:
            angles = self._framer.process(result)
            # Record tracking result
            self._recorder.record_tracking(
                track_id=result.track_id,
                confidence=result.confidence,
                center_x=result.center_x,
                center_y=result.center_y,
                bbox=result.bbox,
                lost=result.lost,
            )
        else:
            angles = self._framer.current_angles
            self._recorder.record_tracking(
                track_id=-1, confidence=0.0,
                center_x=0.5, center_y=0.5, lost=True,
            )

        # Update video display (with end-to-end latency)
        self._window.video_preview.update_frame(frame, self._fps_ema, ee_latency)

        # FPS calculation (EMA)
        now = time.monotonic()
        if now - self._last_fps_update > 1.0:
            instant_fps = self._frame_count / max(now - self._last_fps_update, 0.001)
            self._fps_ema = self._fps_ema * 0.7 + instant_fps * 0.3
            self._frame_count = 0
            self._last_fps_update = now

        # Update dashboard & tracking metrics
        if result and result.visible:
            self._window.tracking_view.set_metrics(
                fps=self._fps_ema,
                latency_ms=track_latency,
                target_id=result.track_id,
                confidence=result.confidence,
                pan=angles.pan,
                tilt=angles.tilt,
            )
            self._window.dashboard.update_tracking(
                result.center_x, result.center_y,
                result.confidence, result.track_id,
            )
        elif result and result.lost:
            self._window.tracking_view.set_metrics(
                fps=self._fps_ema,
                latency_ms=track_latency,
                target_id=-1,
                confidence=0.0,
                pan=angles.pan,
                tilt=angles.tilt,
            )

        # Update servo sliders
        self._window.control_panel.set_servo_angles(angles.pan, angles.tilt)

        # Send servo commands over UDP
        self._schedule_async(self._udp.send(cmd_servo_set("host", 0, angles.pan)))
        self._schedule_async(self._udp.send(cmd_servo_set("host", 1, angles.tilt)))

    def _draw_overlay(self, frame: np.ndarray, result):
        h, w = frame.shape[:2]
        cv2 = _cv2()

        # Crosshair at center
        if cv2:
            cx, cy = w // 2, h // 2
            cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (100, 100, 100), 1)
            cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (100, 100, 100), 1)

        if result is None or not result.visible:
            if cv2:
                if result is not None and result.lost:
                    cv2.putText(frame, "TARGET LOST", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    cv2.putText(frame, "TRACKING UNAVAILABLE", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
            return

        # Bounding box
        bx1 = int(result.bbox[0] * w)
        by1 = int(result.bbox[1] * h)
        bx2 = int(result.bbox[2] * w)
        by2 = int(result.bbox[3] * h)
        color = TRACKING_COLORS[result.track_id % len(TRACKING_COLORS)]

        if cv2:
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)
            label = f"ID:{result.track_id} {result.confidence:.2f}"
            cv2.putText(frame, label, (bx1, max(by1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Center point
            cpx = int(result.center_x * w)
            cpy = int(result.center_y * h)
            cv2.circle(frame, (cpx, cpy), 4, color, -1)

    def _send_heartbeat(self):
        self._registry.heartbeat("host")
        self._schedule_async(self._udp.send(make_heartbeat("host")))

    def _check_nodes(self):
        self._registry.check_all()
        for node_id, info in self._registry.get_all().items():
            elapsed = time.monotonic() - info.last_heartbeat
            self._window.node_status.update_node(
                node_id, info.state, elapsed, f"State: {info.state.value}")

    def _process_telemetry(self):
        """Drain incoming message queue and dispatch to UI (runs on Qt main thread)."""
        while True:
            try:
                msg = self._incoming_queue.get_nowait()
            except queue.Empty:
                break

            p = msg.payload
            msg_type = msg.type

            if msg_type == "tel.imu":
                self._window.dashboard.update_imu(
                    float(p.get("yaw", 0)), float(p.get("pitch", 0)),
                    float(p.get("roll", 0)))
            elif msg_type == "tel.depth":
                self._window.dashboard.update_depth(
                    float(p.get("depth_m", 0)), float(p.get("pressure_mbar", 0)),
                    float(p.get("temperature_c", 0)))
                self._window.depth_chart.record_depth(float(p.get("depth_m", 0)))
            elif msg_type == "tel.env":
                self._window.dashboard.update_value("env_temp", float(p.get("temperature_c", 0)))
                self._window.dashboard.update_value("humidity", float(p.get("humidity_pct", 0)))
                self._window.dashboard.update_value("env_pressure", float(p.get("pressure_hpa", 0)))
            elif msg_type == "tel.leak":
                ch = int(p.get("channel", 0))
                wet = bool(p.get("wet", False))
                self._window.dashboard.update_value(f"leak_ch{ch}", "WET" if wet else "DRY")
            elif msg_type == "tel.winch_state":
                self._window.dashboard.update_winch(
                    float(p.get("position_mm", 0)), float(p.get("speed_mm_s", 0)),
                    bool(p.get("limit_top", False)), bool(p.get("limit_bottom", False)))
            elif msg_type == "tel.pi_status":
                self._window.dashboard.update_value("pi_cpu_temp", float(p.get("cpu_temp_c", 0)))
                self._window.dashboard.update_value("pi_cpu", float(p.get("cpu_pct", 0)))
                self._window.dashboard.update_value("pi_mem", float(p.get("memory_pct", 0)))
            elif msg_type == "sys.pong":
                self._startup_check.on_pong()
            elif msg_type == "sys.startup_status":
                checks = p.get("checks", p) if isinstance(p, dict) else {}
                self._startup_check.on_startup_status(checks)
            elif msg_type == "sys.heartbeat":
                node_id = msg.node_id
                self._registry.heartbeat(node_id)

    def _on_gopro_command(self, action: str, setting: str, value: str):
        """Handle GoPro control commands from UI via direct HTTP to Pi proxy."""
        if action == "setting":
            self._schedule_async(self._gopro_set_setting(setting, value))
        elif action == "preset_group":
            group_map = {"video": 0, "photo": 1, "timelapse": 2}
            gid = group_map.get(value, 0)
            self._schedule_async(self._gopro.load_preset_group(gid))
        elif action == "get_settings":
            self._schedule_async(self._fetch_gopro_settings())
        elif action == "record":
            if value == "1":
                self._schedule_async(self._gopro.start_recording())
            else:
                self._schedule_async(self._gopro.stop_recording())

    async def _gopro_set_setting(self, setting: str, value: str):
        ok = await self._gopro.set_setting(setting, value)
        self._window.gopro_setting_result.emit(setting, value, ok, None)

    async def _fetch_gopro_settings(self):
        data = await self._gopro.get_all_settings()
        if data:
            self._window.gopro_settings_loaded.emit(data)

    def _on_gopro_probe(self, setting: str, probe_option: str):
        """Probe available options for a setting without permanently changing it."""
        self._schedule_async(self._gopro_probe_setting(setting, probe_option))

    async def _gopro_probe_setting(self, setting: str, probe_option: str):
        result = await self._gopro.probe_setting(setting)
        self._window.gopro_probe_result.emit(
            result["setting"], result["current_option"],
            result["available"], result["probe_changed"])

    def _on_get_presets(self):
        """Request preset list from camera via HTTP."""
        self._schedule_async(self._fetch_presets())

    async def _fetch_presets(self):
        data = await self._gopro.get_preset_status()
        if data:
            presets, active = GoProClient.normalize_presets(data)
            self._window.gopro_presets_loaded.emit(presets, active)

    def _on_load_preset(self, preset_id: int):
        """Load a specific preset on the camera and restart video pipeline."""
        logger.info("Loading preset: %d", preset_id)
        self._restart_gen += 1
        self._schedule_async(self._load_preset_and_restart(preset_id, self._restart_gen))

    async def _load_preset_and_restart(self, preset_id: int, gen: int):
        ok = await self._gopro.load_preset(preset_id)
        if not ok:
            return
        # Abort if a newer preset was requested while loading
        if gen != self._restart_gen:
            return
        data = await self._gopro.get_preset_status()
        if data:
            presets, _ = GoProClient.normalize_presets(data)
            for p in presets:
                if p.get("id") == preset_id:
                    from deepsight_host.gopro.settings_decode import preset_aspect_ratio
                    aspect = preset_aspect_ratio(p.get("setting_array", []))
                    self._window.gopro_preset_switched.emit(preset_id, aspect)
                    # Wait for camera hardware to finish mode switch
                    await asyncio.sleep(2.0)
                    if gen != self._restart_gen:
                        return
                    # Restart GoPro viewfinder stream (camera stops it on preset change)
                    logger.info("Restarting GoPro viewfinder stream")
                    await self._gopro.start_viewfinder()
                    await asyncio.sleep(3.0)
                    if gen != self._restart_gen:
                        return
                    # Restart Host video receiver to pick up new resolution
                    if isinstance(self._video_source, StreamReceiver):
                        logger.info("Restarting video pipeline for new resolution")
                        await self._video_source.restart()
                    break

    def _send_servo(self, servo_id: int, angle: float):
        self._schedule_async(self._udp.send(cmd_servo_set("host", servo_id, angle)))

    def _emergency_stop(self):
        logger.warning("EMERGENCY STOP activated")
        self._schedule_async(self._udp.send(sys_safety("host", "emergency")))
        self._window.set_safety_state("emergency", "red")
        self._window.set_status_message("EMERGENCY STOP — all motors halted")

    def _switch_tracking_mode(self, mode: str):
        logger.info("Switching tracking mode: %s", mode)
        self._tracker = get_tracker(mode,
                                     confidence_threshold=self.config.confidence_threshold,
                                     iou_threshold=self.config.iou_threshold)
        self.config.tracking_mode = mode
        self._update_tracking_status()

    def _reset_tracker(self):
        self._tracker.reset()
        self._framer.reset()
        self._window.tracking_view.set_status("Tracker reset")

    def _on_node_state_change(self, node_id: str, old, new):
        logger.warning("Node %s: %s -> %s", node_id, old, new)
        self._window.set_status_message(f"Node {node_id}: {old} -> {new}")

    def _on_check_result(self, name: str, status: str, detail: str):
        """Update status bar with individual check result."""
        summary = self._startup_check.summary()
        self._window.set_status_message(summary)
        logger.info("Startup check [%s]: %s — %s", name, status, detail)

    def _on_check_all_done(self, ok: bool):
        """Called when all startup checks complete."""
        state = "OK" if ok else "DEGRADED"
        summary = self._startup_check.summary()
        self._window.set_status_message(f"Startup: {summary}")
        if not ok:
            logger.warning("Startup check FAILED — %s", summary)


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        return None

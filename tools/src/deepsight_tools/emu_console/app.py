"""EmuConsole — Signal Emulation Console for DeepSight development/testing.

MITM proxy between Host and Pi, with per-signal injection/interception.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QStatusBar,
)

from deepsight_tools.emu_console.proxy import UdpProxy
from deepsight_tools.emu_console.video_server import VideoServer, PORT as VIDEO_PORT
from deepsight_tools.emu_console.interceptor import CommandInterceptor
from deepsight_tools.emu_console.ui.signal_panel import SignalPanel
from deepsight_tools.emu_console.ui.control_panel import InterceptorPanel
from deepsight_tools.emu_console.ui.video_panel import VideoPanel

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("emu")


class EmuConsoleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EmuConsole — Signal Emulation Console")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("""
            QMainWindow { background: #0e0e22; }
            QTabWidget::pane { border: 1px solid #2a2a4a; background: #0e0e22; }
            QTabBar::tab { background: #1a1a33; color: #8888aa; padding: 6px 16px;
                           font-size: 11px; border: 1px solid #2a2a4a; }
            QTabBar::tab:selected { background: #2a2a55; color: #aaaadd; }
            QStatusBar { background: #12122a; color: #666688; font-size: 10px; }
        """)

        # Components (created in async init)
        self._proxy: UdpProxy | None = None
        self._video: VideoServer | None = None
        self._interceptor = CommandInterceptor()

        # Async event loop in background thread (started once, runs forever)
        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._async_thread.start()

        self._running = False
        self._injection_task: asyncio.Task | None = None
        self._pending_video_mode: str = "off"  # mode set before Start

        self._setup_ui()
        self._wire_signals()

    # ── UI ──

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("EmuConsole")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #8888cc;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2a5a2a; color: #aaffaa; font-size: 12px; "
            "padding: 4px 20px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background: #3a6a3a; }"
        )
        self._start_btn.clicked.connect(self._toggle)
        title_row.addWidget(self._start_btn)
        root.addLayout(title_row)

        self._tabs = QTabWidget()
        self._signal_panel = SignalPanel()
        self._tabs.addTab(self._signal_panel, "Signals (Upstream)")
        self._control_panel = InterceptorPanel()
        self._tabs.addTab(self._control_panel, "Commands (Downstream)")
        self._video_panel = VideoPanel()
        self._tabs.addTab(self._video_panel, "Video")
        root.addWidget(self._tabs, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Stopped — configure and click Start")

    def _wire_signals(self):
        self._signal_panel.hijack_changed.connect(self._on_upstream_hijack)
        self._control_panel.hijack_changed.connect(self._on_downstream_hijack)
        self._video_panel.mode_changed.connect(self._on_video_mode)
        self._video_panel.pi_addr_changed.connect(self._on_video_pi_addr)
        self._video_panel.file_changed.connect(self._on_video_file)
        self._video_panel.apply_clicked.connect(self._apply_video)
        self._interceptor.set_on_log(self._control_panel.add_entry)

    # ── Hijack handlers (called from Qt thread) ──

    def _on_upstream_hijack(self, signal_type: str, enabled: bool):
        """Qt→async: update proxy upstream hijack state."""
        if self._proxy:
            # set_upstream_hijack modifies a set (GIL-safe, no async needed)
            self._proxy.set_upstream_hijack(signal_type, enabled)

    def _on_downstream_hijack(self, prefix: str, enabled: bool):
        self._interceptor.set_hijack(prefix, enabled)

    # ── Video handlers ──

    def _on_video_mode(self, mode: str):
        self._pending_video_mode = mode
        if self._video:
            self._video.set_mode(mode)

    def _on_video_pi_addr(self, host: str, port: int):
        if self._video:
            self._video.set_pi_address(host, port)

    def _on_video_file(self, path: str):
        if self._video:
            self._video.set_file(path)

    def _apply_video(self):
        if self._running and self._video:
            self._schedule_async(self._restart_video())

    # ── Start / Stop ──

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        logger.info("Starting EmuConsole...")
        self._running = True
        self._schedule_async(self._async_init())
        self._start_btn.setText("Stop")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #5a2a2a; color: #ffaaaa; font-size: 12px; "
            "padding: 4px 20px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background: #6a3a3a; }"
        )
        self._status_bar.showMessage("Running — proxying UDP :5100, video :8554")

    def _stop(self):
        logger.info("Stopping EmuConsole...")
        self._running = False
        self._schedule_async(self._async_shutdown())
        self._start_btn.setText("Start")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2a5a2a; color: #aaffaa; font-size: 12px; "
            "padding: 4px 20px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background: #3a6a3a; }"
        )
        self._status_bar.showMessage("Stopped")

    # ── Async management ──

    def _run_async_loop(self):
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def _schedule_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    async def _async_init(self):
        self._proxy = UdpProxy(
            listen_port=5100,
            pi_addr="192.168.1.100",
            pi_port=5100,
            host_addr="127.0.0.1",
            host_port=5005,
        )
        self._proxy.set_interceptor(self._interceptor.process_command)

        # Apply initial hijack state from UI
        for signal_type in self._signal_panel.get_signal_types():
            self._proxy.set_upstream_hijack(signal_type, False)

        await self._proxy.start()

        self._video = VideoServer(VIDEO_PORT)
        self._video.set_mode(self._pending_video_mode)
        await self._video.start()

        self._injection_task = asyncio.create_task(self._injection_loop())

    async def _async_shutdown(self):
        if self._injection_task:
            self._injection_task.cancel()
            self._injection_task = None
        if self._proxy:
            await self._proxy.stop()
            self._proxy = None
        if self._video:
            await self._video.stop()
            self._video = None

    async def _restart_video(self):
        if self._video:
            await self._video.stop()
            await self._video.start()

    # ── Injection loop ──

    async def _injection_loop(self):
        dt = 0.05  # 20 Hz
        while self._running and self._proxy:
            self._signal_panel.step_all(dt)

            hijacked_types = self._proxy.upstream_hijack_set
            for signal_type in self._signal_panel.get_signal_types():
                if signal_type in hijacked_types:
                    inj = self._signal_panel.get_injector(signal_type)
                    if inj:
                        msgs = inj.generate()
                        if not isinstance(msgs, list):
                            msgs = [msgs]
                        for msg in msgs:
                            await self._proxy.inject(msg)

            await asyncio.sleep(dt)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EmuConsole")
    window = EmuConsoleWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

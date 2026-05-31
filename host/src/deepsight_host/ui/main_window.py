"""Main application window for DeepSight Host."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStatusBar,
    QLabel,
    QPushButton,
    QApplication,
    QMenuBar,
    QMenu,
)

from deepsight_host.ui.styles import DARK_THEME
from deepsight_host.ui.dashboard import DashboardWidget
from deepsight_host.ui.video_preview import VideoPreviewWidget
from deepsight_host.ui.component_status import ComponentStatusWidget
from deepsight_host.ui.gimbal_deflection import GimbalDeflectionWidget
from deepsight_host.ui.motion_state import MotionStateWidget
from deepsight_host.ui.tracking_view import TrackingViewWidget
from deepsight_host.ui.depth_chart import DepthChartWidget
from deepsight_shared.constants import SafetyState
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui")


class MainWindow(QMainWindow):
    gopro_command = Signal(str, str, str)  # action, setting, value
    gopro_probe = Signal(str, str)  # setting_id, probe_option
    gopro_get_presets = Signal()  # request preset list from camera
    gopro_load_preset = Signal(int)  # load a specific preset by id

    # GoPro HTTP results
    gopro_presets_loaded = Signal(list, int)  # presets, active_id
    gopro_settings_loaded = Signal(dict)  # all camera settings
    gopro_setting_result = Signal(str, str, bool, object)  # setting, value, ok, available
    gopro_probe_result = Signal(str, str, object, bool)  # setting, current, available, changed
    gopro_status_updated = Signal(dict)  # raw camera state for component_status
    gopro_preset_switched = Signal(int, object)  # preset_id, aspect_ratio (w,h) or None

    # Standalone E-Stop signal
    e_stop = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSight — ROV Filming System")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(DARK_THEME)

        self._i18n = I18n.instance()
        self._sizes_set = False
        self._setup_ui()
        self._connect_gopro_signals()
        self._connect_i18n()

    def _setup_ui(self):
        self._setup_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Top bar ──
        top = QHBoxLayout()
        top.setSpacing(8)

        title = QLabel("DeepSight")
        title.setStyleSheet("font-weight: bold; font-size: 15px; color: #8888cc;")
        top.addWidget(title)
        top.addStretch()

        self._current_safety = "nominal"
        self._current_safety_color = "green"
        self._safety_label = QLabel(tr("safety.nominal"))
        self._safety_label.setObjectName("status_green")
        self._safety_header_label = QLabel(tr("app.safety") + ":")
        self._safety_header_label.setStyleSheet("color: #8888cc; font-size: 11px;")
        top.addWidget(self._safety_header_label)
        top.addWidget(self._safety_label)

        top.addSpacing(12)

        self._lock_label = QLabel(tr("safety.locked"))
        self._lock_label.setObjectName("status_red")
        top.addWidget(self._lock_label)

        self._lang_btn = QPushButton(tr("lang.switch"))
        self._lang_btn.setFixedWidth(48)
        self._lang_btn.setFixedHeight(24)
        self._lang_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 6px; }"
        )
        self._lang_btn.clicked.connect(self._i18n.toggle)
        top.addWidget(self._lang_btn)

        root.addLayout(top)

        # ── Main area: two stacked horizontal splitters ──
        self._main_vsplit = QSplitter(Qt.Vertical)

        # -- Top row: video (left) | status widgets (right) --
        top_hsplit = QSplitter(Qt.Horizontal)

        self._video = VideoPreviewWidget()
        top_hsplit.addWidget(self._video)

        right_top = QWidget()
        right_top_layout = QVBoxLayout(right_top)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(4)

        self._tracking_view = TrackingViewWidget()
        right_top_layout.addWidget(self._tracking_view)

        self._gimbal_deflection = GimbalDeflectionWidget()
        right_top_layout.addWidget(self._gimbal_deflection)

        self._motion_state = MotionStateWidget()
        right_top_layout.addWidget(self._motion_state)

        # Standalone E-Stop button
        self._e_stop_btn = QPushButton(tr("safety.e_stop"))
        self._e_stop_btn.setStyleSheet(
            "QPushButton { background-color: #cc2222; color: white; font-weight: bold; "
            "font-size: 13px; border: 2px solid #ff4444; border-radius: 6px; "
            "padding: 8px 16px; min-height: 36px; }"
            "QPushButton:hover { background-color: #dd3333; }"
            "QPushButton:pressed { background-color: #aa1111; }"
        )
        self._e_stop_btn.clicked.connect(self.e_stop.emit)
        right_top_layout.addWidget(self._e_stop_btn)

        right_top_layout.addStretch()

        top_hsplit.addWidget(right_top)
        top_hsplit.setStretchFactor(0, 7)
        top_hsplit.setStretchFactor(1, 3)

        self._main_vsplit.addWidget(top_hsplit)

        # -- Bottom row: components + dashboard (left) | chart (right) --
        bottom_hsplit = QSplitter(Qt.Horizontal)

        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(4, 4, 4, 4)
        status_layout.setSpacing(8)

        self._component_status = ComponentStatusWidget()
        status_layout.addWidget(self._component_status, 1)

        self._dashboard = DashboardWidget()
        status_layout.addWidget(self._dashboard, 2)

        bottom_hsplit.addWidget(status_widget)

        self._depth_chart = DepthChartWidget()

        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addStretch()
        chart_layout.addWidget(self._depth_chart)
        chart_layout.addStretch()

        bottom_hsplit.addWidget(chart_container)
        bottom_hsplit.setStretchFactor(0, 1)
        bottom_hsplit.setStretchFactor(1, 0)

        self._main_vsplit.addWidget(bottom_hsplit)

        self._main_vsplit.setHandleWidth(12)
        top_hsplit.setHandleWidth(12)
        bottom_hsplit.setHandleWidth(12)

        root.addWidget(self._main_vsplit)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(tr("app.ready"))

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # ── Settings menu ──
        self._settings_menu = menu_bar.addMenu(tr("menu.settings"))
        settings_action = QAction(tr("menu.settings_action"), self)
        settings_action.triggered.connect(self._open_settings)
        self._settings_menu.addAction(settings_action)

        self._settings_menu.addSeparator()

        presets_action = QAction(tr("menu.gopro_presets"), self)
        presets_action.triggered.connect(self._open_gopro_presets)
        self._settings_menu.addAction(presets_action)
        self._presets_action = presets_action

        gopro_action = QAction(tr("menu.gopro_control"), self)
        gopro_action.triggered.connect(self._open_gopro_control)
        self._settings_menu.addAction(gopro_action)
        gopro_action.setVisible(False)
        self._gopro_action = gopro_action
        self._settings_action = settings_action

        # ── Album menu ──
        self._album_menu = menu_bar.addMenu(tr("menu.album"))
        media_action = QAction(tr("menu.album_media"), self)
        media_action.triggered.connect(self._open_media_browser)
        self._album_menu.addAction(media_action)
        self._media_action = media_action

        # ── About menu ──
        self._about_menu = menu_bar.addMenu(tr("menu.about"))

    def _open_settings(self):
        from deepsight_host.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.config, self)
        dlg.exec()

    def _open_gopro_control(self):
        from deepsight_host.ui.gopro_control_dialog import GoProControlDialog
        if not hasattr(self, '_gopro_dlg') or self._gopro_dlg is None:
            self._gopro_dlg = GoProControlDialog(self)
            self._gopro_dlg.command.connect(self.gopro_command.emit)
            self._gopro_dlg.probe_requested.connect(self.gopro_probe.emit)
            self._gopro_dlg.finished.connect(self._on_gopro_dlg_closed)
        self._gopro_dlg.show()
        self._gopro_dlg.raise_()
        self._gopro_dlg.activateWindow()

    def _open_gopro_presets(self):
        from deepsight_host.ui.gopro_presets_dialog import PresetsDialog
        if not hasattr(self, '_presets_dlg') or self._presets_dlg is None:
            self._presets_dlg = PresetsDialog(self)
            self._presets_dlg.load_preset.connect(self.gopro_load_preset.emit)
            self._presets_dlg.refresh_requested.connect(self.gopro_get_presets.emit)
            self._presets_dlg.finished.connect(self._on_presets_dlg_closed)
        self._presets_dlg.show()
        self._presets_dlg.raise_()
        self._presets_dlg.activateWindow()
        self.gopro_get_presets.emit()

    def _on_gopro_dlg_closed(self):
        self._gopro_dlg = None

    def _on_presets_dlg_closed(self):
        self._presets_dlg = None

    def setup_media_services(self, gopro_client, schedule_async, download_dir: str):
        self._gopro_client = gopro_client
        self._schedule_async = schedule_async
        self._download_dir = download_dir

    def _open_media_browser(self):
        from deepsight_host.ui.media_browser import MediaBrowserDialog
        if not hasattr(self, '_media_dlg') or self._media_dlg is None:
            if not hasattr(self, '_gopro_client'):
                return
            self._media_dlg = MediaBrowserDialog(
                self._gopro_client, self._schedule_async, self._download_dir, self)
            self._media_dlg.finished.connect(self._on_media_dlg_closed)
        self._media_dlg.show()
        self._media_dlg.raise_()
        self._media_dlg.activateWindow()

    def _on_media_dlg_closed(self):
        self._media_dlg = None

    @property
    def gopro_dialog(self):
        return getattr(self, '_gopro_dlg', None)

    @property
    def presets_dialog(self):
        return getattr(self, '_presets_dlg', None)

    def set_presets_result(self, presets: list[dict], active_preset_id: int):
        dlg = self.presets_dialog
        if dlg is not None:
            dlg.set_presets(presets, active_preset_id)

    def set_gopro_status(self, data: dict):
        """Update component status widget with GoPro state."""
        if not data.get("online"):
            self.component_status.update_component(
                "gopro", None, 0, tr("gopro.offline"))
            self._video.set_recording(False)
            self._video.set_battery(0)
            return

        bat = data.get("battery_pct", 0)
        recording = data.get("recording", False)
        self._video.set_recording(recording)
        self._video.set_battery(bat)
        rec = "●" if recording else "○"
        sd_bytes = data.get("sd_remaining_bytes", 0)
        sd_gb = sd_bytes / 1e9 if sd_bytes > 0 else 0

        if sd_gb >= 1:
            sd_str = f"{sd_gb:.0f}GB"
        elif sd_gb > 0:
            sd_str = f"{sd_gb * 1000:.0f}MB"
        else:
            sd_str = "--"

        self.component_status.update_component("gopro", SafetyState.NOMINAL, 0,
            f"REC {rec}  {bat}%  SD {sd_str}")

    def _connect_gopro_signals(self):
        self.gopro_presets_loaded.connect(self.set_presets_result)
        self.gopro_settings_loaded.connect(self._on_gopro_settings)
        self.gopro_setting_result.connect(self._on_gopro_setting_done)
        self.gopro_probe_result.connect(self._on_gopro_probe_done)
        self.gopro_status_updated.connect(self.set_gopro_status)
        self.gopro_preset_switched.connect(self._on_preset_switched)

    def _on_preset_switched(self, preset_id: int, aspect: tuple | None):
        if aspect is not None:
            self._video.set_target_aspect(aspect)

    def _on_gopro_settings(self, data: dict):
        dlg = self.gopro_dialog
        if dlg is not None:
            dlg.set_current_values(data)

    def _on_gopro_setting_done(self, setting: str, value: str, ok: bool, available):
        dlg = self.gopro_dialog
        if dlg is not None:
            dlg.set_setting_result(setting, value, ok, available)

    def _on_gopro_probe_done(self, setting: str, current: str, available, changed: bool):
        dlg = self.gopro_dialog
        if dlg is not None:
            dlg.set_probe_result(setting, current, available, changed)

    def set_config(self, config):
        self.config = config

    def showEvent(self, event):
        super().showEvent(event)
        if not self._sizes_set:
            self._sizes_set = True
            QTimer.singleShot(100, self._apply_initial_split)

    def _apply_initial_split(self):
        total = self._main_vsplit.height()
        if total > 0:
            self._main_vsplit.setSizes([total * 4 // 5, total * 1 // 5])

    def _connect_i18n(self):
        self._i18n.language_changed.connect(self._on_lang_changed)

    def _on_lang_changed(self, lang: str):
        self.setWindowTitle(tr("app.title"))
        self._lang_btn.setText(tr("lang.switch"))
        self._status_bar.showMessage(tr("app.ready"))
        self._safety_header_label.setText(tr("app.safety") + ":")
        self._safety_label.setText(tr(f"safety.{self._current_safety}"))
        self._lock_label.setText(tr(f"safety.{'locked' if self._current_safety == 'locked' else 'unlocked'}"))
        self._e_stop_btn.setText(tr("safety.e_stop"))
        self._settings_menu.setTitle(tr("menu.settings"))
        self._album_menu.setTitle(tr("menu.album"))
        self._about_menu.setTitle(tr("menu.about"))
        self._settings_action.setText(tr("menu.settings_action"))
        self._presets_action.setText(tr("menu.gopro_presets"))
        self._gopro_action.setText(tr("menu.gopro_control"))
        self._media_action.setText(tr("menu.album_media"))

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            old = event.oldState()
            new = self.windowState()
            old_fs = bool(old & Qt.WindowFullScreen)
            new_fs = bool(new & Qt.WindowFullScreen)
            if old_fs != new_fs and new_fs:
                QTimer.singleShot(600, self._after_fullscreen_transition)
                QTimer.singleShot(1200, self._after_fullscreen_transition)
        super().changeEvent(event)

    def _after_fullscreen_transition(self):
        self._video.force_repaint()
        self.centralWidget().update()
        self.centralWidget().repaint()
        self.update()
        self.repaint()
        QApplication.processEvents()
        self._apply_initial_split()

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    # -- Property accessors --

    @property
    def video_preview(self) -> VideoPreviewWidget:
        return self._video

    @property
    def dashboard(self) -> DashboardWidget:
        return self._dashboard

    @property
    def component_status(self) -> ComponentStatusWidget:
        return self._component_status

    @property
    def gimbal_deflection(self) -> GimbalDeflectionWidget:
        return self._gimbal_deflection

    @property
    def motion_state(self) -> MotionStateWidget:
        return self._motion_state

    @property
    def tracking_view(self) -> TrackingViewWidget:
        return self._tracking_view

    @property
    def depth_chart(self) -> DepthChartWidget:
        return self._depth_chart

    def set_gamepad_connected(self, connected: bool, info: str = ""):
        self._component_status.update_gamepad(connected, info)

    def set_safety_state(self, state: str, color: str):
        self._current_safety = state
        self._current_safety_color = color
        i18n_key = f"safety.{state}"
        known = ("safety.nominal", "safety.degraded", "safety.caution",
                 "safety.safe", "safety.emergency", "safety.locked", "safety.unlocked")
        label = tr(i18n_key) if i18n_key in known else state.upper()
        self._safety_label.setText(label)

        obj_name = {
            "green": "status_green",
            "yellow": "status_yellow",
            "red": "status_red",
        }.get(color, "status_green")
        self._safety_label.setObjectName(obj_name)
        self._safety_label.style().unpolish(self._safety_label)
        self._safety_label.style().polish(self._safety_label)

    def set_lock_state(self, locked: bool):
        if locked:
            self._lock_label.setText(tr("safety.locked"))
            self._lock_label.setObjectName("status_red")
        else:
            self._lock_label.setText(tr("safety.unlocked"))
            self._lock_label.setObjectName("status_green")
        self._lock_label.style().unpolish(self._lock_label)
        self._lock_label.style().polish(self._lock_label)
        self._video.set_lock_overlay(locked)

    def set_status_message(self, msg: str):
        self._status_bar.showMessage(msg)

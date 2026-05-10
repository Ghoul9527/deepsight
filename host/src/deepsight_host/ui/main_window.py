"""Main application window for DeepSight Host."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QKeyEvent
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
)

from deepsight_host.ui.styles import DARK_THEME
from deepsight_host.ui.dashboard import DashboardWidget
from deepsight_host.ui.video_preview import VideoPreviewWidget
from deepsight_host.ui.node_status import NodeStatusWidget
from deepsight_host.ui.control_panel import ControlPanelWidget
from deepsight_host.ui.tracking_view import TrackingViewWidget
from deepsight_host.ui.depth_chart import DepthChartWidget
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSight — ROV Filming System")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(DARK_THEME)

        self._i18n = I18n.instance()
        self._sizes_set = False
        self._setup_ui()
        self._connect_i18n()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Top bar: compact ──
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

        # -- Top row: video (left) | controls (right) --
        top_hsplit = QSplitter(Qt.Horizontal)

        self._video = VideoPreviewWidget()
        top_hsplit.addWidget(self._video)

        right_top = QWidget()
        right_top_layout = QVBoxLayout(right_top)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(4)

        self._tracking_view = TrackingViewWidget()
        right_top_layout.addWidget(self._tracking_view)

        self._control_panel = ControlPanelWidget()
        right_top_layout.addWidget(self._control_panel)

        top_hsplit.addWidget(right_top)
        top_hsplit.setStretchFactor(0, 7)
        top_hsplit.setStretchFactor(1, 3)

        self._main_vsplit.addWidget(top_hsplit)

        # -- Bottom row: status (left) | chart (right) --
        bottom_hsplit = QSplitter(Qt.Horizontal)

        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(4, 4, 4, 4)
        status_layout.setSpacing(8)

        self._node_status = NodeStatusWidget()
        status_layout.addWidget(self._node_status, 1)

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

        # Let native splitter handle show (QSplitter { background: transparent } in theme)
        self._main_vsplit.setHandleWidth(12)
        top_hsplit.setHandleWidth(12)
        bottom_hsplit.setHandleWidth(12)

        root.addWidget(self._main_vsplit)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(tr("app.ready"))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._sizes_set:
            self._sizes_set = True
            QTimer.singleShot(100, self._apply_initial_split)

    def _apply_initial_split(self):
        """Set 4:1 top:bottom split after layout is computed."""
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
    def node_status(self) -> NodeStatusWidget:
        return self._node_status

    @property
    def control_panel(self) -> ControlPanelWidget:
        return self._control_panel

    @property
    def tracking_view(self) -> TrackingViewWidget:
        return self._tracking_view

    @property
    def depth_chart(self) -> DepthChartWidget:
        return self._depth_chart

    def set_safety_state(self, state: str, color: str):
        self._current_safety = state
        self._current_safety_color = color
        i18n_key = f"safety.{state}"
        label = tr(i18n_key) if i18n_key in ("safety.nominal", "safety.degraded",
                                              "safety.caution", "safety.safe",
                                              "safety.emergency") else state.upper()
        self._safety_label.setText(label)

        obj_name = {
            "green": "status_green",
            "yellow": "status_yellow",
            "red": "status_red",
        }.get(color, "status_green")
        self._safety_label.setObjectName(obj_name)
        self._safety_label.style().unpolish(self._safety_label)
        self._safety_label.style().polish(self._safety_label)

    def set_status_message(self, msg: str):
        self._status_bar.showMessage(msg)

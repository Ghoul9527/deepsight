"""Camera Presets dialog — lists presets from GoPro, highlights active, click to switch."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSizePolicy,
)

from deepsight_host.ui.i18n import tr
from deepsight_host.ui.styles import DARK_THEME

logger = logging.getLogger("host.ui.presets")

# Preset icon names mapped to descriptive labels
_ICON_NAMES: dict[int, str] = {
    0: "Activity", 1: "Standard", 2: "Cinematic",
    3: "Ultra Slo-Mo", 4: "Basic", 5: "5.3K",
    6: "4K", 7: "1080p", 8: "HDR", 9: "Log",
    10: "Video", 11: "Slo-Mo", 12: "Photo",
}


class PresetsDialog(QDialog):
    """Modal dialog showing presets for a given group (video/photo/timelapse).

    Signals:
        load_preset(int) — emitted when the user clicks a preset to activate it.
        refresh_requested() — emitted to re-fetch presets from the camera.
    """

    load_preset = Signal(int)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("presets.title"))
        self.setMinimumSize(480, 400)
        self.setMaximumSize(560, 600)
        self.setStyleSheet(DARK_THEME)
        self._preset_ids: dict[int, int] = {}  # list row → preset id
        self._active_row: int = -1

        self._setup_ui()
        self._connect_i18n()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        header = QHBoxLayout()
        self._title_label = QLabel(tr("presets.video_group"))
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #8888cc;")
        header.addWidget(self._title_label)
        header.addStretch()

        self._refresh_btn = QPushButton(tr("presets.refresh"))
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self._refresh_btn)

        root.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #333355; max-height: 1px;")
        root.addWidget(sep)

        # Status label
        self._status_label = QLabel(tr("presets.switch_hint"))
        self._status_label.setStyleSheet("color: #7777aa; font-size: 11px;")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        # Preset list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: #1a1a2e;
                border: 1px solid #333355;
                border-radius: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #222244;
            }
            QListWidget::item:hover {
                background: #2a2a4e;
            }
            QListWidget::item:selected {
                background: #333366;
            }
        """)
        self._list.itemClicked.connect(self._on_preset_clicked)
        root.addWidget(self._list, 1)

        # Bottom buttons
        bottom = QHBoxLayout()
        bottom.addStretch()
        self._close_btn = QPushButton(tr("presets.close"))
        self._close_btn.setFixedHeight(32)
        self._close_btn.clicked.connect(self.accept)
        bottom.addWidget(self._close_btn)
        root.addLayout(bottom)

    def set_presets(self, presets: list[dict], active_preset_id: int):
        """Populate the list with presets and highlight the active one."""
        self._list.clear()
        self._preset_ids.clear()
        self._active_row = -1

        if not presets:
            item = QListWidgetItem(tr("presets.loading"))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self._list.addItem(item)
            return

        for i, p in enumerate(presets):
            pid = p.get("id", -1)
            title = p.get("title", "") or _ICON_NAMES.get(
                p.get("title_id", -1), f"Preset {pid}")
            summary = p.get("summary", "")
            is_active = pid == active_preset_id

            label = f"  {title}"
            if summary:
                label += f"\n     {summary}"
            if is_active:
                label += f"  —  {tr('presets.active')}"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, pid)
            if is_active:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.green)
                self._active_row = i
            self._list.addItem(item)
            self._preset_ids[i] = pid

        self._status_label.setText(tr("presets.switch_hint"))

    def set_loading(self):
        """Show a loading state."""
        self._list.clear()
        self._preset_ids.clear()
        self._active_row = -1
        item = QListWidgetItem(tr("presets.loading"))
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self._list.addItem(item)

    def _on_preset_clicked(self, item: QListWidgetItem):
        pid = item.data(Qt.UserRole)
        if pid is None:
            return
        self._status_label.setText(tr("presets.switching"))
        self.load_preset.emit(int(pid))

    def _connect_i18n(self):
        from deepsight_host.ui.i18n import I18n
        I18n.instance().language_changed.connect(self._on_lang_changed)

    def _on_lang_changed(self, lang: str):
        self.setWindowTitle(tr("presets.title"))
        self._refresh_btn.setText(tr("presets.refresh"))
        self._close_btn.setText(tr("presets.close"))
        self._status_label.setText(tr("presets.switch_hint"))

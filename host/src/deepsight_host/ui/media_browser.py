"""Media Browser — browse GoPro SD card videos, download and delete."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QProgressBar, QMessageBox,
    QFileDialog,
)

from deepsight_host.ui.styles import DARK_THEME
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.media")

THUMB_W, THUMB_H = 168, 94


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1e9:
        return f"{size_bytes / 1e9:.2f} GB"
    if size_bytes >= 1e6:
        return f"{size_bytes / 1e6:.1f} MB"
    return f"{size_bytes / 1e3:.0f} KB"


def _format_date(timestamp: int) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return "--"


class _MediaRow(QWidget):
    """Single row: thumbnail | filename + metadata | checkbox | progress bar."""

    def __init__(self, file_info: dict, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(
            "background-color: #2a2a3a; border: 1px solid #333355; color: #555;")
        self.thumb.setText("...")
        layout.addWidget(self.thumb)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)

        self.name_label = QLabel(self.file_info["filename"])
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        meta_layout.addWidget(self.name_label)

        size_str = _format_size(self.file_info.get("size", 0))
        date_str = _format_date(self.file_info.get("created", 0))
        info = QLabel(f"{size_str}  |  {date_str}")
        info.setStyleSheet("color: #777; font-size: 11px;")
        meta_layout.addWidget(info)

        layout.addLayout(meta_layout, 1)

        self.checkbox = QCheckBox()
        self.checkbox.setFixedSize(24, 24)
        layout.addWidget(self.checkbox)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(120)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)


class MediaBrowserDialog(QDialog):
    """Non-modal dialog to browse, download and delete GoPro SD card videos."""

    # No-arg signals — cross-thread safe. Data passed via instance vars.
    _refresh_done = Signal()
    _thumb_done = Signal()
    _dl_progress = Signal()
    _dl_done = Signal()
    _del_done = Signal()

    def __init__(self, gopro_client, schedule_async, download_dir: str, parent=None):
        super().__init__(parent)
        self._gopro = gopro_client
        self._schedule_async = schedule_async
        self._download_dir = download_dir

        self._files: list[dict] = []
        self._rows: list[_MediaRow] = []
        self._pending_thumbs: list[str] = []
        self._thumb_timer = QTimer(self)
        self._thumb_timer.timeout.connect(self._load_next_thumbs)
        self._thumb_timer.setInterval(300)

        self._download_queue: list[str] = []
        self._download_active = 0
        self._delete_queue: list[dict] = []

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_refresh_timeout)

        # Cross-thread data staging
        self._st_files: object = None
        self._st_thumb_fn: str = ""
        self._st_thumb_data: object = None
        self._st_dl_fn: str = ""
        self._st_dl_pct: int = 0
        self._st_dl_total: int = 100
        self._st_dl_ok: bool = False
        self._st_del_fn: str = ""
        self._st_del_ok: bool = False

        self.setWindowTitle(tr("media.title"))
        self.setMinimumSize(680, 500)
        self.setStyleSheet(DARK_THEME)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._setup_ui()
        self._connect_signals()

        self._i18n = I18n.instance()
        self._i18n.language_changed.connect(self._on_lang_changed)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        self._refresh_btn = QPushButton(tr("media.refresh"))
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)

        self._select_all_btn = QPushButton(tr("media.select_all"))
        self._select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        toolbar.addWidget(self._select_all_btn)

        self._deselect_btn = QPushButton(tr("media.deselect_all"))
        self._deselect_btn.clicked.connect(lambda: self._set_all_checked(False))
        toolbar.addWidget(self._deselect_btn)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ── Scroll area ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(2)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_content)
        root.addWidget(self._scroll, 1)

        # ── Summary bar ──
        self._summary_label = QLabel(tr("media.no_files"))
        self._summary_label.setStyleSheet("color: #777; font-size: 11px;")
        root.addWidget(self._summary_label)

        # ── Overall progress (hidden) ──
        self._overall_progress = QProgressBar()
        self._overall_progress.setRange(0, 100)
        self._overall_progress.setValue(0)
        self._overall_progress.hide()
        root.addWidget(self._overall_progress)

        # ── Action bar ──
        actions = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #8888cc; font-size: 11px;")
        actions.addWidget(self._status_label)
        actions.addStretch()

        self._download_btn = QPushButton(tr("media.download"))
        self._download_btn.clicked.connect(self._on_download)
        self._download_btn.setEnabled(False)
        actions.addWidget(self._download_btn)

        self._delete_btn = QPushButton(tr("media.delete"))
        self._delete_btn.setStyleSheet(
            "QPushButton { color: #ff6666; } QPushButton:hover { color: #ff4444; }")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        actions.addWidget(self._delete_btn)

        self._close_btn = QPushButton(tr("media.close"))
        self._close_btn.clicked.connect(self.hide)
        actions.addWidget(self._close_btn)

        root.addLayout(actions)

    def _connect_signals(self):
        self._refresh_done.connect(self._on_media_list_inner, Qt.QueuedConnection)
        self._thumb_done.connect(self._on_thumb_inner, Qt.QueuedConnection)
        self._dl_progress.connect(self._on_dl_progress_inner, Qt.QueuedConnection)
        self._dl_done.connect(self._on_dl_done_inner, Qt.QueuedConnection)
        self._del_done.connect(self._on_del_done_inner, Qt.QueuedConnection)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._files:
            self._on_refresh()

    def _on_refresh(self):
        logger.info("Media refresh requested")
        self._status_label.setText(tr("media.loading"))
        self._refresh_btn.setEnabled(False)
        self._download_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._watchdog.start(15000)
        self._schedule_async(self._do_list_media())

    def _on_refresh_timeout(self):
        logger.warning("Media list timed out after 15s")
        if self._status_label.text() == tr("media.loading"):
            self._status_label.setText(tr("media.offline"))
            self._summary_label.setText(tr("media.offline"))
            self._refresh_btn.setEnabled(True)

    async def _do_list_media(self):
        try:
            logger.info("Media list: fetching from GoPro...")
            files = await self._gopro.list_media()
            logger.info("Media list: got %s files", len(files) if files else "None")
        except Exception:
            logger.exception("Media list failed")
            files = None
        self._st_files = files
        self._refresh_done.emit()

    def _on_media_list_inner(self):
        try:
            self._on_media_list_impl()
        except Exception:
            logger.exception("_on_media_list_inner crashed")

    def _on_media_list_impl(self):
        files = self._st_files
        self._st_files = None
        self._watchdog.stop()
        logger.info("Media list result: %s", "None" if files is None else f"{len(files)} files")
        self._refresh_btn.setEnabled(True)
        self._thumb_timer.stop()
        self._pending_thumbs.clear()

        # Fully clear and rebuild scroll content
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        if files is None:
            self._status_label.setText(tr("media.offline"))
            self._summary_label.setText(tr("media.offline"))
            self._download_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        self._files = files

        if not files:
            self._status_label.setText(tr("media.no_files"))
            self._summary_label.setText(tr("media.no_files"))
            self._download_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        files.sort(key=lambda f: f.get("created", 0), reverse=True)

        for f in files:
            row = _MediaRow(f)
            row.checkbox.toggled.connect(self._update_summary)
            self._rows.append(row)
            self._scroll_layout.addWidget(row)

        self._scroll_layout.addStretch()

        self._update_summary()
        self._status_label.setText("")

        self._pending_thumbs = [f["filename"] for f in files]
        logger.info("Starting thumb timer with %d files", len(self._pending_thumbs))
        self._thumb_timer.start()

    def _load_next_thumbs(self):
        logger.info("Thumb tick: %d pending", len(self._pending_thumbs))
        if not self._pending_thumbs:
            self._thumb_timer.stop()
            return

        for _ in range(2):
            if not self._pending_thumbs:
                break
            filename = self._pending_thumbs.pop(0)
            fi = next((f for f in self._files if f["filename"] == filename), None)
            if fi:
                logger.info("Thumb fetch scheduled: %s", filename)
                self._schedule_async(self._do_get_thumbnail(fi["directory"], filename))

    async def _do_get_thumbnail(self, directory: str, filename: str):
        try:
            data = await self._gopro.get_thumbnail(directory, filename)
            logger.info("Thumb fetched: %s → %s bytes", filename, len(data) if data else "None")
        except Exception:
            logger.exception("Thumbnail failed: %s", filename)
            data = None
        self._st_thumb_fn = filename
        self._st_thumb_data = data
        self._thumb_done.emit()

    def _on_thumb_inner(self):
        filename = self._st_thumb_fn
        data = self._st_thumb_data
        self._st_thumb_fn = ""
        self._st_thumb_data = None
        logger.info("Thumb result: %s → %s", filename, "set" if data else "None/skip")
        if data is None:
            return
        for row in self._rows:
            if row.file_info["filename"] == filename:
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(THUMB_W, THUMB_H,
                                           Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation)
                    row.thumb.setPixmap(pixmap)
                    row.thumb.setText("")
                break

    def _set_all_checked(self, checked: bool):
        for row in self._rows:
            row.checkbox.setChecked(checked)

    def _update_summary(self):
        total = len(self._rows)
        selected = sum(1 for r in self._rows if r.checkbox.isChecked())
        total_size = sum(
            r.file_info.get("size", 0) for r in self._rows if r.checkbox.isChecked())

        self._summary_label.setText(
            tr("media.selected_count", n=f"{selected}", total=f"{total}") + "  |  " +
            tr("media.total_size", size=_format_size(total_size)))

        has_selection = selected > 0
        self._download_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _on_download(self):
        selected = [r for r in self._rows if r.checkbox.isChecked()]
        logger.info("Download clicked: %d selected", len(selected))
        if not selected:
            return

        folder = QFileDialog.getExistingDirectory(
            self, tr("media.download"), self._download_dir)
        if not folder:
            return
        self._download_dir = folder

        self._download_queue = [r.file_info["filename"] for r in selected]
        self._download_active = 0
        self._overall_progress.setRange(0, len(self._download_queue))
        self._overall_progress.setValue(0)
        self._overall_progress.show()
        self._download_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)

        self._start_next_downloads()

    def _start_next_downloads(self):
        while self._download_active < 2 and self._download_queue:
            filename = self._download_queue.pop(0)
            self._download_active += 1
            fi = next((f for f in self._files if f["filename"] == filename), None)
            if fi:
                dest = os.path.join(self._download_dir, filename)
                self._status_label.setText(tr("media.downloading") + f" {filename}")
                self._schedule_async(self._do_download(fi["directory"], filename, dest))

    async def _do_download(self, directory: str, filename: str, dest_path: str):
        def progress_cb(done, total):
            pct = int(done / total * 100) if total > 0 else 0
            self._st_dl_fn = filename
            self._st_dl_pct = pct
            self._st_dl_total = 100
            self._dl_progress.emit()

        ok = await self._gopro.download_file(directory, filename, dest_path, progress_cb)
        self._st_dl_fn = filename
        self._st_dl_ok = ok
        self._dl_done.emit()

    def _on_dl_progress_inner(self):
        filename = self._st_dl_fn
        pct = self._st_dl_pct
        total = self._st_dl_total
        for row in self._rows:
            if row.file_info["filename"] == filename:
                row.progress.show()
                row.progress.setRange(0, total)
                row.progress.setValue(pct)
                break

    def _on_dl_done_inner(self):
        filename = self._st_dl_fn
        ok = self._st_dl_ok
        self._download_active -= 1

        for row in self._rows:
            if row.file_info["filename"] == filename:
                row.progress.hide()
                break

        if ok:
            self._status_label.setText(tr("media.download_ok", name=filename))
        else:
            self._status_label.setText(tr("media.download_fail", name=filename))

        done = self._overall_progress.maximum() - len(self._download_queue) - self._download_active
        self._overall_progress.setValue(done)

        if self._download_queue or self._download_active > 0:
            self._start_next_downloads()
        else:
            self._overall_progress.hide()
            self._download_btn.setEnabled(True)
            self._delete_btn.setEnabled(True)
            self._refresh_btn.setEnabled(True)
            self._status_label.setText("")

    def _on_delete(self):
        selected = [r for r in self._rows if r.checkbox.isChecked()]
        logger.info("Delete clicked: %d selected", len(selected))
        if not selected:
            return

        n = len(selected)
        reply = QMessageBox.question(
            self, tr("media.delete"),
            tr("media.delete_confirm", n=f"{n}"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        self._delete_queue = [r.file_info for r in selected]
        self._delete_btn.setEnabled(False)
        self._download_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._overall_progress.setRange(0, len(self._delete_queue))
        self._overall_progress.setValue(0)
        self._overall_progress.show()

        self._process_next_delete()

    def _process_next_delete(self):
        if not self._delete_queue:
            self._overall_progress.hide()
            self._delete_btn.setEnabled(True)
            self._download_btn.setEnabled(True)
            self._refresh_btn.setEnabled(True)
            self._status_label.setText("")
            self._on_refresh()
            return

        fi = self._delete_queue.pop(0)
        self._status_label.setText(tr("media.deleting") + f" {fi['filename']}")
        done = self._overall_progress.maximum() - len(self._delete_queue)
        self._overall_progress.setValue(done)
        self._schedule_async(self._do_delete(fi["directory"], fi["filename"]))

    async def _do_delete(self, directory: str, filename: str):
        ok = await self._gopro.delete_file(directory, filename)
        self._st_del_fn = filename
        self._st_del_ok = ok
        self._del_done.emit()

    def _on_del_done_inner(self):
        filename = self._st_del_fn
        ok = self._st_del_ok
        if ok:
            self._status_label.setText(tr("media.delete_ok", name=filename))
        else:
            self._status_label.setText(tr("media.delete_fail", name=filename))
        self._process_next_delete()

    def _on_lang_changed(self, lang: str):
        self.setWindowTitle(tr("media.title"))
        self._refresh_btn.setText(tr("media.refresh"))
        self._select_all_btn.setText(tr("media.select_all"))
        self._deselect_btn.setText(tr("media.deselect_all"))
        self._download_btn.setText(tr("media.download"))
        self._delete_btn.setText(tr("media.delete"))
        self._close_btn.setText(tr("media.close"))
        self._update_summary()

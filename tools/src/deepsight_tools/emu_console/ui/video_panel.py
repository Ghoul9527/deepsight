"""Video source selector panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox,
    QLabel, QPushButton, QLineEdit, QFileDialog,
)


class VideoPanel(QWidget):
    """Video source selector with mode dropdown and config fields."""

    mode_changed = Signal(str)          # off | passthrough | camera | file
    pi_addr_changed = Signal(str, int)  # host, port
    file_changed = Signal(str)          # path
    apply_clicked = Signal()

    MODES = [
        ("off", "Off (No Video)"),
        ("passthrough", "Pi Passthrough"),
        ("camera", "Built-in Camera"),
        ("file", "Video File Loop"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Mode selector ──
        mode_group = QGroupBox("Video Source")
        mode_group.setStyleSheet(
            "QGroupBox { color: #aaaadd; font-size: 11px; font-weight: bold; }"
        )
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(4)

        self._mode_combo = QComboBox()
        for mode_key, mode_label in self.MODES:
            self._mode_combo.addItem(mode_label, mode_key)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_combo.setStyleSheet("font-size: 11px;")
        mode_layout.addWidget(self._mode_combo)

        # ── Pi address (passthrough) ──
        self._pi_row = QHBoxLayout()
        self._pi_row.setSpacing(4)
        self._pi_label = QLabel("Pi:")
        self._pi_label.setStyleSheet("font-size: 10px; color: #8888aa;")
        self._pi_row.addWidget(self._pi_label)
        self._pi_host = QLineEdit("192.168.1.100")
        self._pi_host.setStyleSheet("font-size: 10px; max-width: 120px;")
        self._pi_row.addWidget(self._pi_host)
        self._pi_port = QLineEdit("8554")
        self._pi_port.setStyleSheet("font-size: 10px; max-width: 50px;")
        self._pi_row.addWidget(self._pi_port)
        mode_layout.addLayout(self._pi_row)

        # ── File picker ──
        self._file_row = QHBoxLayout()
        self._file_row.setSpacing(4)
        self._file_label = QLabel("File:")
        self._file_label.setStyleSheet("font-size: 10px; color: #8888aa;")
        self._file_row.addWidget(self._file_label)
        self._file_path = QLineEdit()
        self._file_path.setStyleSheet("font-size: 10px;")
        self._file_path.setPlaceholderText("Choose a video file...")
        self._file_row.addWidget(self._file_path)
        browse_btn = QPushButton("...")
        browse_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        browse_btn.clicked.connect(self._browse_file)
        self._file_row.addWidget(browse_btn)
        mode_layout.addLayout(self._file_row)

        layout.addWidget(mode_group)

        # ── Apply ──
        apply_btn = QPushButton("Apply Video Settings")
        apply_btn.clicked.connect(self._emit_apply)
        apply_btn.setStyleSheet(
            "QPushButton { background: #2a2a55; color: #aaaadd; font-size: 11px; "
            "padding: 4px 12px; border-radius: 3px; }"
            "QPushButton:hover { background: #3a3a66; }"
        )
        layout.addWidget(apply_btn)

        # ── Status ──
        self._status = QLabel("Video: Off")
        self._status.setStyleSheet("font-size: 10px; color: #666688;")
        layout.addWidget(self._status)

        layout.addStretch()

        # Init visibility
        self._on_mode_changed(0)

    def _on_mode_changed(self, index: int):
        mode = self._mode_combo.itemData(index)
        self._pi_label.setVisible(mode == "passthrough")
        self._pi_host.setVisible(mode == "passthrough")
        self._pi_port.setVisible(mode == "passthrough")
        self._file_label.setVisible(mode == "file")
        self._file_path.setVisible(mode == "file")

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)"
        )
        if path:
            self._file_path.setText(path)

    def _emit_apply(self):
        mode = self._mode_combo.currentData()
        self.mode_changed.emit(mode)
        if mode == "passthrough":
            try:
                port = int(self._pi_port.text())
            except ValueError:
                port = 8554
            self.pi_addr_changed.emit(self._pi_host.text(), port)
        elif mode == "file":
            self.file_changed.emit(self._file_path.text())
        self.apply_clicked.emit()

    def set_status(self, text: str):
        self._status.setText(text)

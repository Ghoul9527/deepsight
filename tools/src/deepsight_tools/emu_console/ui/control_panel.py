"""Command interceptor panel — displays captured Host→device commands."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QLabel, QPushButton, QTextEdit, QScrollArea,
)

from deepsight_tools.emu_console.interceptor import CommandEntry


class InterceptorPanel(QScrollArea):
    """Panel showing a live log of intercepted Host→device commands
    and hijack toggles for downstream command types.
    """

    hijack_changed = Signal(str, bool)  # msg_type_prefix, enabled

    COMMAND_GROUPS = {
        "cmd.servo": "Servo",
        "cmd.lighting": "Lighting",
        "cmd.winch": "Winch",
        "cmd.gopro": "GoPro",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Hijack toggles ──
        hijack_group = QGroupBox("Intercept Commands")
        hijack_group.setStyleSheet(
            "QGroupBox { color: #aaaadd; font-size: 11px; font-weight: bold; }"
        )
        hijack_layout = QVBoxLayout(hijack_group)
        hijack_layout.setSpacing(2)

        self._checks: dict[str, QCheckBox] = {}
        for prefix, label in self.COMMAND_GROUPS.items():
            chk = QCheckBox(label)
            chk.setStyleSheet("font-size: 10px; color: #8888aa;")
            chk.toggled.connect(lambda v, p=prefix: self.hijack_changed.emit(p, v))
            hijack_layout.addWidget(chk)
            self._checks[prefix] = chk

        layout.addWidget(hijack_group)

        # ── Command log ──
        log_group = QGroupBox("Command Log")
        log_group.setStyleSheet(
            "QGroupBox { color: #aaaadd; font-size: 11px; font-weight: bold; }"
        )
        log_layout = QVBoxLayout(log_group)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet(
            "QTextEdit { background: #0a0a1a; color: #aaffaa; font-size: 10px; "
            "font-family: Menlo, monospace; border: 1px solid #2a2a4a; }"
        )
        self._log_view.setMaximumHeight(300)
        log_layout.addWidget(self._log_view)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._log_view.clear)
        clear_btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        log_layout.addWidget(clear_btn, alignment=Qt.AlignRight)

        layout.addWidget(log_group)
        layout.addStretch()

        self.setWidget(container)

    def add_entry(self, entry: CommandEntry):
        """Append a command entry to the log view."""
        import time as _time
        ts = _time.strftime("%H:%M:%S", _time.localtime(entry.timestamp))
        fwd = "→" if entry.forwarded else "✗"
        pld = ", ".join(f"{k}={v}" for k, v in entry.payload.items())
        line = f"[{ts}] {fwd} {entry.msg_type}({pld})\n"
        self._log_view.append(line.rstrip())

    def set_hijacked(self, prefix: str, enabled: bool):
        if prefix in self._checks:
            self._checks[prefix].blockSignals(True)
            self._checks[prefix].setChecked(enabled)
            self._checks[prefix].blockSignals(False)

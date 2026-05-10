"""Compact node status widget — horizontal connection indicators."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from deepsight_shared.constants import SafetyState
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.nodes")


class NodeStatusIndicator(QFrame):
    def __init__(self, node_key: str, parent=None):
        super().__init__(parent)
        self._node_key = node_key
        self._state = SafetyState.NOMINAL
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(
            "NodeStatusIndicator { background-color: #12122a; border: 1px solid #2a2a4a; border-radius: 4px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        self._name_label = QLabel(tr(f"node.{self._node_key}"))
        self._name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self._name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._name_label)

        self._state_label = QLabel("OK")
        self._state_label.setObjectName("status_green")
        self._state_label.setAlignment(Qt.AlignCenter)
        self._state_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._state_label)

        self._hb_label = QLabel("--s")
        self._hb_label.setObjectName("heading")
        self._hb_label.setAlignment(Qt.AlignCenter)
        self._hb_label.setStyleSheet("font-size: 9px;")
        layout.addWidget(self._hb_label)

        I18n.instance().language_changed.connect(self._retranslate)

    def _retranslate(self, _lang: str = ""):
        self._name_label.setText(tr(f"node.{self._node_key}"))

    def update_state(self, state: SafetyState, heartbeat_ago: float = 0.0,
                     info: str = ""):
        self._state = state
        state_map = {
            SafetyState.NOMINAL: ("status_green", tr("node.state_healthy")),
            SafetyState.DEGRADED: ("status_yellow", tr("node.state_degraded")),
            SafetyState.CAUTION: ("status_yellow", tr("node.state_degraded")),
            SafetyState.SAFE: ("status_red", tr("node.state_lost")),
            SafetyState.EMERGENCY: ("status_red", tr("node.state_lost")),
        }
        obj_name, text = state_map.get(state, ("status_red", "???"))
        self._state_label.setText(text)
        self._state_label.setObjectName(obj_name)
        self._state_label.style().unpolish(self._state_label)
        self._state_label.style().polish(self._state_label)
        self._hb_label.setText(f"{heartbeat_ago:.0f}s")

    @property
    def node_key(self) -> str:
        return self._node_key


class NodeStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._indicators: dict[str, NodeStatusIndicator] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._title_label = QLabel(tr("tab.nodes"))
        self._title_label.setStyleSheet("font-weight: bold; font-size: 10px; color: #8888cc;")
        layout.addWidget(self._title_label)

        row = QHBoxLayout()
        row.setSpacing(4)
        for node_key in ["pi", "pico", "stm32"]:
            indicator = NodeStatusIndicator(node_key)
            self._indicators[node_key] = indicator
            row.addWidget(indicator)
        layout.addLayout(row)

        I18n.instance().language_changed.connect(self._retranslate)

    def _retranslate(self, _lang: str = ""):
        self._title_label.setText(tr("tab.nodes"))

    def update_node(self, node_id: str, state: SafetyState,
                    heartbeat_ago: float = 0.0, info: str = ""):
        if node_id in self._indicators:
            self._indicators[node_id].update_state(state, heartbeat_ago, info)

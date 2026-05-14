"""GoPro Camera Control dialog — HERO13 settings from OpenGoPro HTTP API.

Settings organized by mode (Video / Photo / Time Lapse / Other).
Non-modal — every change sends immediately.  Combo boxes probe the camera
for context-sensitive available options on first click.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QComboBox,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QWidget,
    QSpinBox,
    QTabWidget,
)
from PySide6.QtCore import Signal, Qt

from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.gopro")

# ═══════════════════════════════════════════════════════════════════════════════
# Mode → setting IDs (based on official OpenGoPro HERO13 API)
# ═══════════════════════════════════════════════════════════════════════════════

_MODE_VIDEO = "video"
_MODE_PHOTO = "photo"
_MODE_TIMELAPSE = "timelapse"
_MODE_OTHER = "other"

_MODE_TABS: list[tuple[str, str, list[int]]] = [
    # (mode_key, i18n_key, [setting_ids])
    (_MODE_VIDEO, "gopro.tab_video", [
        2,    # Video Resolution
        3,    # Frames Per Second
        108,  # Video Aspect Ratio
        121,  # Video Lens
        232,  # Video Framing
        135,  # Hypersmooth
        150,  # Video Horizon Leveling
        173,  # Video Performance Mode
        182,  # Video Bit Rate
        183,  # Bit Depth
        184,  # Profiles
        180,  # System Video Mode
        186,  # Video Easy Mode
        156,  # Video Duration
    ]),
    (_MODE_PHOTO, "gopro.tab_photo", [
        122,  # Photo Lens
        192,  # Multi Shot Aspect Ratio
        233,  # Multi Shot Framing
        234,  # Frame Rate
        125,  # Photo Output
        151,  # Photo Horizon Leveling
        171,  # Photo Single Interval
        172,  # Photo Interval Duration
        177,  # Enable Night Photo
        191,  # Easy Night Photo
        227,  # Photo Mode
    ]),
    (_MODE_TIMELAPSE, "gopro.tab_timelapse", [
        128,  # Media Format
        187,  # Lapse Mode
        5,    # Video Timelapse Rate
        30,   # Photo Timelapse Rate
        32,   # Nightlapse Rate
        123,  # Time Lapse Digital Lenses
        157,  # Multi Shot Duration
        179,  # Star Trails Length
        193,  # Framing
    ]),
    (_MODE_OTHER, "gopro.tab_other", [
        175,  # Control Mode
        176,  # Easy Mode Speed
        43,   # Webcam Digital Lenses
        194,  # Camera Mode
        189,  # Max Lens Mod
        190,  # Max Lens Mod Enable
        162,  # Max Lens
        167,  # HindSight
        168,  # Scheduled Capture
        134,  # Anti-Flicker
        59,   # Auto Power Down
        237,  # Auto Power On USB
        236,  # Automatic Wi-Fi Access Point
        178,  # Wireless Band
        83,   # GPS
        88,   # LCD Brightness
        91,   # LED
        216,  # Beep Volume
        219,  # Setup Screen Saver
        223,  # Setup Language
    ]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Settings data — official OpenGoPro API names + SDK enum option labels
# ═══════════════════════════════════════════════════════════════════════════════

_SETTINGS_DATA: dict[int, dict] = {
    # ── Video ──
    2: {
        "label": "Video Resolution",
        "options": [
            ("1", "4K"),
            ("4", "2.7K"),
            ("6", "2.7K 4:3"),
            ("7", "1440"),
            ("9", "1080"),
            ("12", "720"),
            ("18", "4K 4:3"),
            ("21", "5.6K"),
            ("24", "5K"),
            ("25", "5K 4:3"),
            ("26", "5.3K 8:7"),
            ("27", "5.3K 4:3"),
            ("28", "4K 8:7"),
            ("31", "8K"),
            ("35", "5.3K 21:9"),
            ("36", "4K 21:9"),
            ("37", "4K 1:1"),
            ("38", "900"),
            ("39", "4K Sphere"),
            ("100", "5.3K"),
            ("107", "5.3K 8:7"),
            ("108", "4K 8:7"),
            ("109", "4K 9:16"),
            ("110", "1080 9:16"),
            ("111", "2.7K 4:3"),
            ("112", "4K 4:3"),
            ("113", "5.3K 4:3"),
        ],
    },
    3: {
        "label": "Frames Per Second",
        "options": [
            ("0", "240"),
            ("1", "120"),
            ("2", "100"),
            ("3", "90"),
            ("5", "60"),
            ("6", "50"),
            ("8", "30"),
            ("9", "25"),
            ("10", "24"),
            ("13", "200"),
            ("15", "400"),
            ("16", "360"),
            ("17", "300"),
        ],
    },
    108: {
        "label": "Video Aspect Ratio",
        "options": [
            ("0", "4:3"),
            ("1", "16:9"),
            ("3", "8:7"),
            ("4", "9:16"),
            ("5", "21:9"),
            ("6", "1:1"),
        ],
    },
    121: {
        "label": "Video Lens",
        "options": [
            ("0", "Wide"),
            ("2", "Narrow"),
            ("3", "SuperView"),
            ("4", "Linear"),
            ("7", "Max SuperView"),
            ("8", "Linear + Horizon Leveling"),
            ("9", "HyperView"),
            ("10", "Linear + Horizon Lock"),
            ("11", "Max HyperView"),
            ("12", "Ultra SuperView"),
            ("13", "Ultra Wide"),
            ("14", "Ultra Linear"),
            ("104", "Ultra HyperView"),
        ],
    },
    232: {
        "label": "Video Framing",
        "options": [
            ("0", "4:3"),
            ("1", "16:9"),
            ("3", "8:7"),
            ("4", "9:16"),
            ("5", "21:9"),
            ("6", "1:1"),
        ],
    },
    135: {
        "label": "Hypersmooth",
        "options": [
            ("0", "Off"),
            ("1", "Low"),
            ("2", "High"),
            ("3", "Boost"),
            ("4", "Auto Boost"),
            ("100", "Standard"),
        ],
    },
    150: {
        "label": "Video Horizon Leveling",
        "options": [
            ("0", "Off"),
            ("2", "Locked"),
        ],
    },
    173: {
        "label": "Video Performance Mode",
        "options": [
            ("0", "Maximum Video Performance"),
            ("1", "Extended Battery"),
            ("2", "Tripod / Stationary Video"),
        ],
    },
    182: {
        "label": "Video Bit Rate",
        "options": [
            ("0", "Standard"),
            ("1", "High"),
            ("2", "Max"),
        ],
    },
    183: {
        "label": "Bit Depth",
        "options": [
            ("0", "8-Bit"),
            ("2", "10-Bit"),
        ],
    },
    184: {
        "label": "Profiles",
        "options": [
            ("0", "Standard"),
            ("1", "HDR"),
            ("2", "Log"),
            ("101", "HLG HDR"),
        ],
    },
    180: {
        "label": "System Video Mode",
        "options": [
            ("0", "Highest Quality"),
            ("101", "Extended Battery"),
            ("102", "Longest Battery"),
            ("111", "Standard Quality"),
            ("112", "Basic Quality"),
        ],
    },
    186: {
        "label": "Video Easy Mode",
        "options": [
            ("0", "Highest Quality"),
            ("1", "Standard Quality"),
            ("2", "Basic Quality"),
            ("3", "Standard Video"),
            ("4", "HDR Video"),
        ],
    },
    156: {
        "label": "Video Duration",
        "options": [
            ("1", "15 Seconds"),
            ("2", "30 Seconds"),
            ("3", "1 Minute"),
            ("4", "5 Minutes"),
            ("5", "15 Minutes"),
            ("6", "30 Minutes"),
            ("7", "1 Hour"),
            ("8", "2 Hours"),
            ("9", "3 Hours"),
            ("10", "5 Seconds"),
            ("100", "No Limit"),
        ],
    },

    # ── Photo ──
    122: {
        "label": "Photo Lens",
        "options": [
            ("0", "Wide 12MP"),
            ("10", "Linear 12MP"),
            ("15", "9MP Wide"),
            ("19", "Narrow"),
            ("27", "Wide 23MP"),
            ("28", "Linear 23MP"),
            ("31", "Wide 27MP"),
            ("32", "Linear 27MP"),
            ("37", "9MP Linear"),
            ("38", "13MP Linear"),
            ("39", "13MP Wide"),
            ("40", "13MP Ultra Wide"),
            ("41", "Ultra Wide 12MP"),
            ("44", "13MP Ultra Linear"),
            ("100", "Max SuperView"),
            ("101", "Wide"),
            ("102", "Linear"),
        ],
    },
    192: {
        "label": "Multi Shot Aspect Ratio",
        "options": [
            ("0", "4:3"),
            ("1", "16:9"),
            ("3", "8:7"),
            ("4", "9:16"),
        ],
    },
    233: {
        "label": "Multi Shot Framing",
        "options": [
            ("0", "4:3"),
            ("1", "16:9"),
            ("3", "8:7"),
            ("4", "9:16"),
        ],
    },
    234: {
        "label": "Frame Rate",
        "options": [
            ("0", "240"),
            ("1", "120"),
            ("2", "100"),
            ("3", "90"),
            ("5", "60"),
            ("6", "50"),
            ("8", "30"),
            ("9", "25"),
            ("10", "24"),
            ("13", "200"),
            ("15", "400"),
            ("16", "360"),
            ("17", "300"),
        ],
    },
    125: {
        "label": "Photo Output",
        "options": [
            ("0", "Standard"),
            ("1", "Raw"),
            ("2", "HDR"),
            ("3", "SuperPhoto"),
        ],
    },
    151: {
        "label": "Photo Horizon Leveling",
        "options": [
            ("0", "Off"),
            ("2", "Locked"),
        ],
    },
    171: {
        "label": "Photo Single Interval",
        "options": [
            ("0", "Off"),
            ("2", "0.5s"),
            ("3", "1s"),
            ("4", "2s"),
            ("5", "5s"),
            ("6", "10s"),
            ("7", "30s"),
            ("8", "60s"),
            ("9", "120s"),
            ("10", "3s"),
        ],
    },
    172: {
        "label": "Photo Interval Duration",
        "options": [
            ("0", "Off"),
            ("1", "15 Seconds"),
            ("2", "30 Seconds"),
            ("3", "1 Minute"),
            ("4", "5 Minutes"),
            ("5", "15 Minutes"),
            ("6", "30 Minutes"),
            ("7", "1 Hour"),
            ("8", "2 Hours"),
            ("9", "3 Hours"),
        ],
    },
    177: {
        "label": "Enable Night Photo",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    191: {
        "label": "Easy Night Photo",
        "options": [
            ("0", "Super Photo"),
            ("1", "Night Photo"),
            ("2", "Burst"),
        ],
    },
    227: {
        "label": "Photo Mode",
        "options": [
            ("0", "SuperPhoto"),
            ("1", "Night Photo"),
            ("2", "Burst"),
        ],
    },

    # ── Time Lapse ──
    128: {
        "label": "Media Format",
        "options": [
            ("13", "Time Lapse Video"),
            ("20", "Time Lapse Photo"),
            ("21", "Night Lapse Photo"),
            ("26", "Night Lapse Video"),
        ],
    },
    187: {
        "label": "Lapse Mode",
        "options": [
            ("0", "TimeWarp"),
            ("1", "Star Trails"),
            ("2", "Light Painting"),
            ("3", "Vehicle Lights"),
            ("4", "Max TimeWarp"),
            ("5", "Max Star Trails"),
            ("6", "Max Light Painting"),
            ("7", "Max Vehicle Lights"),
            ("8", "Time Lapse Video"),
            ("9", "Night Lapse Video"),
        ],
    },
    5: {
        "label": "Video Timelapse Rate",
        "options": [
            ("0", "0.5 Seconds"),
            ("1", "1 Second"),
            ("2", "2 Seconds"),
            ("3", "5 Seconds"),
            ("4", "10 Seconds"),
            ("5", "30 Seconds"),
            ("6", "60 Seconds"),
            ("7", "2 Minutes"),
            ("8", "5 Minutes"),
            ("9", "30 Minutes"),
            ("10", "60 Minutes"),
            ("11", "3 Seconds"),
        ],
    },
    30: {
        "label": "Photo Timelapse Rate",
        "options": [
            ("11", "3 Seconds"),
            ("100", "60 Minutes"),
            ("101", "30 Minutes"),
            ("102", "5 Minutes"),
            ("103", "2 Minutes"),
            ("104", "60 Seconds"),
            ("105", "30 Seconds"),
            ("106", "10 Seconds"),
            ("107", "5 Seconds"),
            ("108", "2 Seconds"),
            ("109", "1 Second"),
            ("110", "0.5 Seconds"),
        ],
    },
    32: {
        "label": "Nightlapse Rate",
        "options": [
            ("4", "4 Seconds"),
            ("5", "5 Seconds"),
            ("10", "10 Seconds"),
            ("15", "15 Seconds"),
            ("20", "20 Seconds"),
            ("30", "30 Seconds"),
            ("100", "60 Seconds"),
            ("120", "2 Minutes"),
            ("300", "5 Minutes"),
            ("1800", "30 Minutes"),
            ("3600", "60 Minutes"),
            ("3601", "Auto"),
        ],
    },
    123: {
        "label": "Time Lapse Digital Lenses",
        "options": [
            ("19", "Narrow"),
            ("31", "Wide 27MP"),
            ("32", "Linear 27MP"),
            ("100", "Max SuperView"),
            ("101", "Wide"),
            ("102", "Linear"),
        ],
    },
    157: {
        "label": "Multi Shot Duration",
        "options": [
            ("0", "Off"),
            ("1", "15 Seconds"),
            ("2", "30 Seconds"),
            ("3", "1 Minute"),
            ("4", "5 Minutes"),
            ("5", "15 Minutes"),
            ("6", "30 Minutes"),
            ("7", "1 Hour"),
            ("8", "2 Hours"),
            ("9", "3 Hours"),
            ("100", "No Limit"),
        ],
    },
    179: {
        "label": "Star Trails Length",
        "options": [
            ("1", "Short"),
            ("2", "Long"),
            ("3", "Max"),
        ],
    },
    193: {
        "label": "Framing",
        "options": [
            ("0", "Widescreen"),
            ("1", "Vertical"),
            ("2", "Full Frame"),
            ("100", "Traditional 4:3"),
            ("101", "Widescreen 16:9"),
            ("103", "Full Frame 8:7"),
            ("104", "Vertical 9:16"),
            ("105", "Ultra Widescreen 21:9"),
            ("106", "Full Frame 1:1"),
        ],
    },

    # ── Other / System ──
    175: {
        "label": "Control Mode",
        "options": [
            ("0", "Easy"),
            ("1", "Pro"),
        ],
    },
    176: {
        "label": "Easy Mode Speed",
        "options": [
            ("100", "8x Ultra Slo-Mo"),
            ("101", "4x Super Slo-Mo"),
            ("102", "2x Slo-Mo"),
            ("103", "1x Speed / Low Light"),
            ("116", "2x Slo-Mo 4K"),
            ("138", "1x Speed 1:1 30fps 4K"),
            ("139", "1x Speed 1:1 25fps 4K"),
            ("140", "2x Slo-Mo 1:1 4K 60fps"),
            ("141", "2x Slo-Mo 1:1 4K 50fps"),
            ("142", "1x Speed 21:9 30fps 5.3K"),
            ("152", "1x Speed 30fps 4:3 5.3K"),
        ],
    },
    43: {
        "label": "Webcam Digital Lenses",
        "options": [
            ("0", "Wide"),
            ("2", "Narrow"),
            ("3", "SuperView"),
            ("4", "Linear"),
        ],
    },
    194: {
        "label": "Camera Mode",
        "options": [
            ("0", "Single Lens"),
            ("1", "360"),
        ],
    },
    189: {
        "label": "Max Lens Mod",
        "options": [
            ("0", "None"),
            ("1", "Max Lens 1.0"),
            ("2", "Max Lens 2.0"),
            ("3", "Max Lens 2.5"),
            ("4", "Macro"),
            ("5", "Anamorphic"),
            ("6", "ND 4"),
            ("7", "ND 8"),
            ("8", "ND 16"),
            ("9", "ND 32"),
            ("10", "Standard Lens"),
            ("100", "Auto Detect"),
        ],
    },
    190: {
        "label": "Max Lens Mod Enable",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    162: {
        "label": "Max Lens",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    167: {
        "label": "HindSight",
        "options": [
            ("2", "15 Seconds"),
            ("3", "30 Seconds"),
            ("4", "Off"),
        ],
    },
    168: {
        "label": "Scheduled Capture",
        "options": [],  # Bitmask setting — handled specially
        "_type": "bitmask",
    },
    134: {
        "label": "Anti-Flicker",
        "options": [
            ("0", "60Hz (NTSC)"),
            ("1", "50Hz (PAL)"),
            ("2", "60Hz"),
            ("3", "50Hz"),
        ],
    },
    59: {
        "label": "Auto Power Down",
        "options": [
            ("0", "Never"),
            ("1", "1 Min"),
            ("4", "5 Min"),
            ("6", "15 Min"),
            ("7", "30 Min"),
            ("11", "8 Seconds"),
            ("12", "30 Seconds"),
        ],
    },
    237: {
        "label": "Auto Power On USB",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    236: {
        "label": "Automatic Wi-Fi Access Point",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    178: {
        "label": "Wireless Band",
        "options": [
            ("0", "2.4GHz"),
            ("1", "5GHz"),
        ],
    },
    83: {
        "label": "GPS",
        "options": [
            ("0", "Off"),
            ("1", "On"),
        ],
    },
    88: {
        "label": "LCD Brightness",
        "options": [],  # Continuous
        "_type": "continuous",
        "_min": 10, "_max": 100, "_suffix": "%",
    },
    91: {
        "label": "LED",
        "options": [
            ("0", "Off"),
            ("2", "On"),
            ("3", "All On"),
            ("4", "All Off"),
            ("5", "Front Off Only"),
            ("100", "Back Only"),
        ],
    },
    216: {
        "label": "Beep Volume",
        "options": [
            ("70", "Low"),
            ("85", "Medium"),
            ("100", "High"),
        ],
    },
    219: {
        "label": "Setup Screen Saver",
        "options": [
            ("0", "Never"),
            ("1", "1 Min"),
            ("2", "2 Min"),
            ("3", "3 Min"),
            ("4", "5 Min"),
        ],
    },
    223: {
        "label": "Setup Language",
        "options": [
            ("0", "English (US)"),
            ("1", "English (UK)"),
            ("2", "English (AUS)"),
            ("3", "German"),
            ("4", "French"),
            ("5", "Italian"),
            ("6", "Spanish"),
            ("7", "Spanish (NA)"),
            ("8", "Chinese"),
            ("9", "Japanese"),
            ("10", "Korean"),
            ("11", "Portuguese"),
            ("12", "Russian"),
            ("13", "English (IND)"),
            ("14", "Swedish"),
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Probe heuristic — pick an option from a different family to trigger error-3
# ═══════════════════════════════════════════════════════════════════════════════

def _pick_probe_option(sid: int, current_val: str) -> str:
    """Return a probe option ID that is unlikely to be available in the
    current mode, triggering error-3 to reveal available_options."""
    rules: dict[int, list[tuple[str, str]]] = {
        2: [("5.3K", "1"), ("4K", "35"), ("2.7K", "1"),
            ("1080", "1"), ("900", "1")],
        3: [("60", "0"), ("30", "0"), ("24", "0"), ("120", "5"), ("240", "10")],
        108: [("16:9", "5"), ("8:7", "5"), ("4:3", "5"), ("9:16", "5"),
              ("21:9", "1"), ("1:1", "1")],
        121: [("Wide", "2"), ("SuperView", "2"), ("Linear", "2"),
              ("Narrow", "0"), ("Ultra Wide", "4")],
        232: [("16:9", "5"), ("8:7", "5"), ("4:3", "5"), ("9:16", "5"),
              ("21:9", "1"), ("1:1", "1")],
    }
    for prefix, probe_id in rules.get(sid, []):
        if prefix in current_val:
            return probe_id
    return "1"


# ═══════════════════════════════════════════════════════════════════════════════
# ProbeComboBox — emits aboutToPopup before the dropdown opens
# ═══════════════════════════════════════════════════════════════════════════════

class ProbeComboBox(QComboBox):
    """QComboBox that emits ``aboutToPopup`` before the dropdown opens."""

    aboutToPopup = Signal()

    def showPopup(self):
        self.aboutToPopup.emit()
        super().showPopup()


# ═══════════════════════════════════════════════════════════════════════════════
# GoProControlDialog
# ═══════════════════════════════════════════════════════════════════════════════

class GoProControlDialog(QDialog):
    """HERO13 camera settings dialog — tabbed by mode, dynamically probed.

    Non-modal. Every change sends immediately via ``command`` signal.
    Combo boxes dynamically probe available options on first click.
    """

    command = Signal(str, str, str)  # action, setting_id, value
    probe_requested = Signal(str, str)  # setting_id, probe_option_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init = True
        self._i18n = I18n.instance()
        self._i18n.language_changed.connect(self._on_lang_changed)

        self.setWindowTitle(tr("gopro.title"))
        self.setMinimumSize(680, 800)
        self.setModal(False)

        self._current_labels: dict[int, QLabel] = {}
        self._setting_label_widgets: dict[int, QLabel] = {}
        self._widgets: dict[int, object] = {}
        self._probe_cache: dict[int, list[tuple[str, str]]] = {}
        self._probing: set[int] = set()
        self._tabs: dict[str, tuple[QScrollArea, QFormLayout]] = {}

        self._setup_ui()
        self._init = False

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Mode selector ──
        mode_row = QHBoxLayout()
        mode_lbl = QLabel(tr("settings.gopro_mode") + ":")
        mode_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cccccc;")
        mode_row.addWidget(mode_lbl)

        self._gopro_mode = QComboBox()
        self._gopro_mode.setMinimumWidth(200)
        self._gopro_mode.addItems(["video", "photo", "timelapse"])
        self._gopro_mode.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._gopro_mode)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # ── Tab widget ──
        self._tab_widget = QTabWidget()

        self._mode_tab_indices: dict[str, int] = {}
        for i, (mode_key, i18n_key, sids) in enumerate(_MODE_TABS):
            tab = self._make_mode_tab(mode_key, i18n_key, sids)
            idx = self._tab_widget.addTab(tab, tr(i18n_key))
            self._mode_tab_indices[mode_key] = idx

        # Start with only Video + System tabs visible
        self._show_mode_tabs("video")

        root.addWidget(self._tab_widget, 1)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
        btn_row.addWidget(self._status_lbl)
        btn_row.addStretch()
        self._close_btn = QPushButton(tr("gopro.close"))
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        root.addLayout(btn_row)

    def _make_mode_tab(self, mode_key: str, i18n_key: str, sids: list[int]) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        form = QFormLayout(content)
        form.setSpacing(6)
        form.setContentsMargins(8, 12, 8, 8)

        for sid in sids:
            info = _SETTINGS_DATA.get(sid)
            if info is None:
                continue
            row = self._make_setting_row(sid, info)
            form.addRow(row)

        scroll.setWidget(content)
        self._tabs[mode_key] = (scroll, form)
        return scroll

    def _make_setting_row(self, sid: int, info: dict) -> QWidget:
        """Build a row: [label | combo/spinbox | current-value]."""
        row = QWidget()
        hbox = QHBoxLayout(row)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)

        label = QLabel(self._setting_label(sid, info["label"]))
        label.setMinimumWidth(220)
        label.setStyleSheet("font-size: 12px; color: #cccccc;")
        hbox.addWidget(label)
        self._setting_label_widgets[sid] = label

        stype = info.get("_type", "combo")

        if stype == "continuous":
            widget = QSpinBox()
            widget.setMinimum(info.get("_min", 0))
            widget.setMaximum(info.get("_max", 100))
            if "_suffix" in info:
                widget.setSuffix(info["_suffix"])
            widget.setMinimumWidth(260)
            widget.valueChanged.connect(
                lambda v, s=sid: self._on_spin_changed(s, str(v)))
        elif stype == "bitmask":
            widget = ProbeComboBox()
            widget.addItem("—", "")
            widget.setMinimumWidth(260)
            # Bitmask not currently implemented via combo
        else:
            widget = ProbeComboBox()
            for val, opt_label in info["options"]:
                widget.addItem(opt_label, val)
            widget.setMinimumWidth(260)
            widget.currentIndexChanged.connect(
                lambda _idx, s=sid, c=widget: self._on_combo_changed(s, c))
            widget.aboutToPopup.connect(
                lambda s=sid: self._on_probe_popup(s))

        hbox.addWidget(widget)
        self._widgets[sid] = widget

        cur_lbl = QLabel("")
        cur_lbl.setMinimumWidth(180)
        cur_lbl.setStyleSheet("color: #8888cc; font-size: 11px;")
        hbox.addWidget(cur_lbl)
        self._current_labels[sid] = cur_lbl

        hbox.addStretch()
        return row

    # ── Mode / tab switching ─────────────────────────────────────────────

    def _on_mode_changed(self, mode: str):
        if self._init:
            return
        self._send("preset_group", mode)
        self._show_mode_tabs(mode)

    def _show_mode_tabs(self, mode: str):
        """Show only the selected mode tab + System tab; hide the rest."""
        mode_keys = {"video", "photo", "timelapse"}
        for mk, idx in self._mode_tab_indices.items():
            if mk == mode:
                self._tab_widget.setTabVisible(idx, True)
                self._tab_widget.setCurrentIndex(idx)
            elif mk in mode_keys:
                self._tab_widget.setTabVisible(idx, False)
            # System tab (other) always visible

    # ── Label helpers ────────────────────────────────────────────────────

    def _setting_label(self, sid: int, fallback: str) -> str:
        """Get translated label for a setting ID. Falls back to API name."""
        key = f"gopro.setting.{sid}"
        translated = tr(key)
        if translated != key:
            return translated
        return fallback

    # ── Signal handlers ──────────────────────────────────────────────────

    def _on_spin_changed(self, sid: int, value: str):
        if self._init:
            return
        self._send(str(sid), value)

    def _on_combo_changed(self, sid: int, combo: QComboBox):
        if self._init:
            return
        value = combo.currentData()
        if value is not None:
            self._send(str(sid), str(value))

    def _on_probe_popup(self, sid: int):
        if sid in self._probing:
            return
        if sid in self._probe_cache:
            return

        combo = self._widgets.get(sid)
        if combo is None:
            return
        current_val = str(combo.currentData() or "")

        self._probing.add(sid)
        combo.addItem("⟳ Loading...", "__loading__")
        combo.setCurrentIndex(combo.count() - 1)

        probe_opt = _pick_probe_option(sid, current_val)
        self.probe_requested.emit(str(sid), probe_opt)

    def set_probe_result(self, setting: str, current_option: str,
                         available: list | None,
                         probe_changed: bool = False):
        """Called when tel.gopro.probe_result arrives from Pi."""
        try:
            sid = int(setting)
        except (ValueError, TypeError):
            return

        self._probing.discard(sid)
        combo = self._widgets.get(sid)
        if combo is None:
            return

        loading_idx = combo.findData("__loading__")
        if loading_idx >= 0:
            combo.removeItem(loading_idx)

        if not available and probe_changed:
            info = _SETTINGS_DATA.get(sid, {})
            available = [{"id": v, "name": l} for v, l in info.get("options", [])]

        if not available:
            return

        combo.blockSignals(True)
        combo.clear()
        for opt in available:
            label = opt.get("name", str(opt.get("id", "")))
            val = str(opt.get("id", ""))
            combo.addItem(label, val)

        idx = combo.findData(str(current_option))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        self._probe_cache[sid] = [
            (str(o["id"]), o["name"]) for o in available
        ]

        if current_option:
            display = current_option
            for opt in available:
                if str(opt.get("id")) == str(current_option):
                    display = opt.get("name", current_option)
                    break
            lbl = self._current_labels.get(sid)
            if lbl:
                lbl.setText(f"→ {display}")

    # ── Send / receive ───────────────────────────────────────────────────

    def _send(self, setting: str, value: str):
        if self._init:
            return
        self.command.emit("setting", setting, value)
        if setting == "get_settings":
            self._status_lbl.setText(tr("gopro.refreshing"))
            return
        if setting == "preset_group":
            mode_labels = {"video": tr("gopro.mode_video"),
                           "photo": tr("gopro.mode_photo"),
                           "timelapse": tr("gopro.mode_timelapse")}
            mode_name = mode_labels.get(value, value)
            self._status_lbl.setText(
                tr("gopro.sent_mode").format(mode=mode_name))
            return

        sid = int(setting)
        info = _SETTINGS_DATA.get(sid, {})
        setting_name = self._setting_label(sid, info.get("label", setting))
        value_name = str(value)
        for opt_val, opt_label in info.get("options", []):
            if opt_val == value:
                value_name = opt_label
                break
        self._status_lbl.setText(
            tr("gopro.setting").format(name=setting_name, val=value_name))

    def set_setting_result(self, setting: str, value: str, success: bool,
                           available: list | None = None):
        """Called when tel.gopro_setting_ack arrives from Pi."""
        try:
            sid = int(setting)
        except (ValueError, TypeError):
            sid = None

        if sid is not None:
            info = _SETTINGS_DATA.get(sid, {})
            setting_name = self._setting_label(sid, info.get("label", setting))
            value_name = str(value)
            for opt_val, opt_label in info.get("options", []):
                if opt_val == value:
                    value_name = opt_label
                    break
        else:
            setting_name = setting
            value_name = str(value)

        if success:
            self._status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
            self._status_lbl.setText(
                tr("gopro.set_ok").format(name=setting_name, val=value_name))
            if sid is not None:
                lbl = self._current_labels.get(sid)
                if lbl:
                    lbl.setText(f"→ {value_name}")
                self._probe_cache.clear()
        else:
            self._status_lbl.setStyleSheet("color: #cc6666; font-size: 11px;")
            self._status_lbl.setText(
                tr("gopro.set_fail").format(name=setting_name, val=value_name))

    def set_current_values(self, values: dict):
        """Called when tel_gopro_settings response arrives from Pi."""
        for sid_str, cur_val in values.items():
            try:
                sid = int(sid_str)
            except (ValueError, TypeError):
                continue

            info = _SETTINGS_DATA.get(sid)
            display = str(cur_val)
            if info:
                for opt_val, opt_label in info.get("options", []):
                    if str(opt_val) == str(cur_val):
                        display = opt_label
                        break

            lbl = self._current_labels.get(sid)
            if lbl:
                lbl.setText(f"→ {display}")

            combo = self._widgets.get(sid)
            if combo is not None and sid not in self._probe_cache:
                combo.blockSignals(True)
                combo.clear()
                combo.addItem(display, str(cur_val))
                combo.blockSignals(False)

            logger.debug("Setting %d = %s (%s)", sid, cur_val, display)

        self._status_lbl.setText(tr("gopro.refreshed"))
        logger.info("Updated %d current setting values", len(values))

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    # ── i18n ─────────────────────────────────────────────────────────────

    def _on_lang_changed(self, lang: str):
        self.setWindowTitle(tr("gopro.title"))
        self._close_btn.setText(tr("gopro.close"))
        for sid, lbl in self._setting_label_widgets.items():
            info = _SETTINGS_DATA.get(sid, {})
            fallback = info.get("label", f"Setting {sid}")
            lbl.setText(self._setting_label(sid, fallback))
        # Retranslate tab titles
        for i, (mode_key, i18n_key, _sids) in enumerate(_MODE_TABS):
            self._tab_widget.setTabText(i, tr(i18n_key))

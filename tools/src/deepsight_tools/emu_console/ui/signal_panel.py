"""Signal injection panel — per-sensor hijack toggles with parameter sliders."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QLabel, QSlider, QDoubleSpinBox, QComboBox, QScrollArea, QFrame,
)

from deepsight_tools.emu_console.injectors import (
    IMUInjector, DepthInjector, EnvInjector, LeakInjector,
    WinchInjector, GoProInjector, PiStatusInjector,
)


class _SectionHeader(QFrame):
    """Collapsible section header with hijack checkbox."""

    hijack_toggled = Signal(str, bool)  # signal_type, enabled

    def __init__(self, title: str, signal_type: str, parent=None):
        super().__init__(parent)
        self._signal_type = signal_type
        self.setStyleSheet("_SectionHeader { background: #1a1a33; border-radius: 3px; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        self._check = QCheckBox(title)
        self._check.setStyleSheet("font-weight: bold; font-size: 12px; color: #aaaadd;")
        self._check.toggled.connect(lambda v: self.hijack_toggled.emit(signal_type, v))
        layout.addWidget(self._check)
        layout.addStretch()

    def set_hijacked(self, enabled: bool):
        self._check.blockSignals(True)
        self._check.setChecked(enabled)
        self._check.blockSignals(False)


class SignalPanel(QScrollArea):
    """Scrollable panel with per-sensor hijack toggles and parameter controls.

    Connects directly to injector instances and emits hijack config changes.
    """

    hijack_changed = Signal(str, bool)  # signal_type, enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: #0e0e22; }")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._injectors: dict[str, object] = {}
        self._sections: dict[str, _SectionHeader] = {}
        self._content_frames: dict[str, QFrame] = {}

        self._build_imu()
        self._build_depth()
        self._build_env()
        self._build_leak()
        self._build_winch()
        self._build_gopro()
        self._build_pi_status()

        self._layout.addStretch()
        self.setWidget(container)

    def _add_section(self, signal_type: str, title: str) -> tuple[_SectionHeader, QVBoxLayout]:
        header = _SectionHeader(title, signal_type)
        header.hijack_toggled.connect(self.hijack_changed.emit)
        self._sections[signal_type] = header
        self._layout.addWidget(header)

        content = QFrame()
        content.setStyleSheet("QFrame { background: #12122a; border-radius: 3px; padding: 4px; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 4, 8, 4)
        content_layout.setSpacing(3)
        self._content_frames[signal_type] = content
        self._layout.addWidget(content)

        return header, content_layout

    def _add_slider(self, layout: QVBoxLayout, label: str, min_v: float, max_v: float,
                    default: float, decimals: int = 1, unit: str = "",
                    callback=None) -> tuple[QSlider, QDoubleSpinBox]:
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 10px; color: #8888aa; min-width: 50px;")
        row.addWidget(lbl)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 1000)
        slider.setValue(int((default - min_v) / (max_v - min_v) * 1000))
        row.addWidget(slider, 1)

        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setDecimals(decimals)
        spin.setValue(default)
        spin.setSuffix(unit)
        spin.setStyleSheet("font-size: 10px; max-width: 75px;")
        spin.setSingleStep((max_v - min_v) / 200)
        row.addWidget(spin)

        # Two-way binding
        slider.valueChanged.connect(
            lambda v: spin.setValue(min_v + (v / 1000.0) * (max_v - min_v)))
        spin.valueChanged.connect(
            lambda v: slider.setValue(int((v - min_v) / (max_v - min_v) * 1000)))

        if callback:
            spin.valueChanged.connect(callback)

        layout.addLayout(row)
        return slider, spin

    # ── IMU ──

    def _build_imu(self):
        inj = IMUInjector()
        self._injectors["tel.imu"] = inj
        header, layout = self._add_section("tel.imu", "IMU (imu)")

        wave_check = QCheckBox("Auto wave motion")
        wave_check.setChecked(True)
        wave_check.setStyleSheet("font-size: 10px; color: #8888aa;")
        wave_check.toggled.connect(inj.set_wave)
        layout.addWidget(wave_check)

        self._add_slider(layout, "Yaw", -30, 30, 0, unit="°", callback=inj.set_yaw)
        self._add_slider(layout, "Pitch", -30, 30, 0, unit="°", callback=inj.set_pitch)
        self._add_slider(layout, "Roll", -30, 30, 0, unit="°", callback=inj.set_roll)

    # ── Depth ──

    def _build_depth(self):
        inj = DepthInjector()
        self._injectors["tel.depth"] = inj
        _, layout = self._add_section("tel.depth", "Depth (depth)")

        self._add_slider(layout, "Depth", 0, 100, 5.0, unit=" m", callback=inj.set_depth)
        self._add_slider(layout, "Temp", 0, 40, 22.0, unit="°C", callback=inj.set_temp)

    # ── Env ──

    def _build_env(self):
        inj = EnvInjector()
        self._injectors["tel.env"] = inj
        _, layout = self._add_section("tel.env", "Environment (env)")

        self._add_slider(layout, "Temp", -10, 50, 22.0, unit="°C", callback=inj.set_temp)
        self._add_slider(layout, "Humidity", 0, 100, 65.0, unit="%", callback=inj.set_humidity)
        self._add_slider(layout, "Pressure", 800, 1200, 1013.0, unit=" hPa", callback=inj.set_pressure)

    # ── Leak ──

    def _build_leak(self):
        inj = LeakInjector()
        self._injectors["tel.leak"] = inj
        _, layout = self._add_section("tel.leak", "Leak Sensor (leak)")

        for ch, name in inj.CHANNELS.items():
            chk = QCheckBox(f"Ch{ch} {name} (wet)")
            chk.setStyleSheet("font-size: 10px; color: #8888aa;")
            chk.toggled.connect(lambda v, c=ch: inj.set_channel(c, v))
            layout.addWidget(chk)

    # ── Winch ──

    def _build_winch(self):
        inj = WinchInjector()
        self._injectors["tel.winch_state"] = inj
        _, layout = self._add_section("tel.winch_state", "Winch (winch_state)")

        self._add_slider(layout, "Position", 0, 5000, 2500, unit=" mm", callback=inj.set_position)
        self._add_slider(layout, "Speed", -200, 200, 0, unit=" mm/s", callback=inj.set_speed)

    # ── GoPro ──

    def _build_gopro(self):
        inj = GoProInjector()
        self._injectors["tel.gopro_status"] = inj
        _, layout = self._add_section("tel.gopro_status", "GoPro Status (gopro_status)")

        rec_check = QCheckBox("Recording")
        rec_check.setStyleSheet("font-size: 10px; color: #8888aa;")
        rec_check.toggled.connect(inj.set_recording)
        layout.addWidget(rec_check)

        mode_combo = QComboBox()
        mode_combo.addItems(inj.MODES)
        mode_combo.currentTextChanged.connect(inj.set_mode)
        mode_combo.setStyleSheet("font-size: 10px;")
        layout.addWidget(mode_combo)

        self._add_slider(layout, "Battery", 0, 100, 85, unit="%", callback=inj.set_battery)
        self._add_slider(layout, "Storage", 0, 512, 120, unit=" GB", callback=inj.set_storage)

    # ── Pi Status ──

    def _build_pi_status(self):
        inj = PiStatusInjector()
        self._injectors["tel.pi_status"] = inj
        _, layout = self._add_section("tel.pi_status", "Pi Status (pi_status)")

        self._add_slider(layout, "CPU Temp", 20, 90, 45.0, unit="°C", callback=inj.set_cpu_temp)
        self._add_slider(layout, "CPU", 0, 100, 15.0, unit="%", callback=inj.set_cpu)
        self._add_slider(layout, "RAM", 0, 100, 30.0, unit="%", callback=inj.set_mem)

    # ── Public API ──

    def get_injector(self, signal_type: str):
        return self._injectors.get(signal_type)

    def get_signal_types(self) -> list[str]:
        return list(self._injectors.keys())

    def set_hijacked(self, signal_type: str, enabled: bool):
        if signal_type in self._sections:
            self._sections[signal_type].set_hijacked(enabled)

    def step_all(self, dt: float):
        """Step time-based injectors (IMU wave, winch movement)."""
        for inj in self._injectors.values():
            if hasattr(inj, 'step'):
                inj.step(dt)

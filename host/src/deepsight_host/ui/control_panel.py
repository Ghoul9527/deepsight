"""Manual control panel — servo sliders, winch, e-stop, GoPro status."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QSlider,
    QPushButton,
    QGridLayout,
)

from deepsight_host.control.servo_mapper import ServoAngles
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.control")


class ControlPanelWidget(QWidget):
    pan_changed = Signal(float)
    tilt_changed = Signal(float)
    winch_stop = Signal()
    e_stop = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._i18n = I18n.instance()
        self._i18n_key_labels: list[tuple[QLabel, str]] = []
        self._setup_ui()
        self._i18n.language_changed.connect(self._retranslate)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # ── Servo controls ──
        servo_group = QGroupBox(tr("control.servo_manual"))
        servo_layout = QGridLayout(servo_group)
        servo_layout.setSpacing(4)

        pan_lbl = QLabel(tr("control.pan"))
        servo_layout.addWidget(pan_lbl, 0, 0)
        self._pan_slider = QSlider(Qt.Horizontal)
        self._pan_slider.setRange(0, 180)
        self._pan_slider.setValue(90)
        self._pan_label = QLabel("90.0°")
        self._pan_label.setObjectName("value")
        servo_layout.addWidget(self._pan_slider, 0, 1)
        servo_layout.addWidget(self._pan_label, 0, 2)

        tilt_lbl = QLabel(tr("control.tilt"))
        servo_layout.addWidget(tilt_lbl, 1, 0)
        self._tilt_slider = QSlider(Qt.Horizontal)
        self._tilt_slider.setRange(0, 180)
        self._tilt_slider.setValue(90)
        self._tilt_label = QLabel("90.0°")
        self._tilt_label.setObjectName("value")
        servo_layout.addWidget(self._tilt_slider, 1, 1)
        servo_layout.addWidget(self._tilt_label, 1, 2)

        root.addWidget(servo_group)
        self._servo_header = servo_group
        self._pan_title_label = pan_lbl
        self._tilt_title_label = tilt_lbl

        # ── Winch controls ──
        winch_group = QGroupBox(tr("control.winch"))
        winch_layout = QVBoxLayout(winch_group)

        self._winch_slider = QSlider(Qt.Horizontal)
        self._winch_slider.setRange(-100, 100)
        self._winch_slider.setValue(0)
        self._winch_slider.sliderReleased.connect(lambda: self._winch_slider.setValue(0))
        winch_layout.addWidget(self._winch_slider)

        winch_btn_layout = QHBoxLayout()
        up_btn = QPushButton(tr("control.winch_up"))
        up_btn.pressed.connect(lambda: self._winch_slider.setValue(50))
        up_btn.released.connect(lambda: self._winch_slider.setValue(0))
        winch_btn_layout.addWidget(up_btn)

        stop_btn = QPushButton(tr("control.winch_stop"))
        stop_btn.clicked.connect(lambda: (self._winch_slider.setValue(0), self.winch_stop.emit()))
        winch_btn_layout.addWidget(stop_btn)

        down_btn = QPushButton(tr("control.winch_down"))
        down_btn.pressed.connect(lambda: self._winch_slider.setValue(-50))
        down_btn.released.connect(lambda: self._winch_slider.setValue(0))
        winch_btn_layout.addWidget(down_btn)
        winch_layout.addLayout(winch_btn_layout)

        root.addWidget(winch_group)
        self._winch_header = winch_group
        self._winch_btns = [up_btn, stop_btn, down_btn]

        # ── Emergency stop ──
        e_stop_btn = QPushButton(tr("control.e_stop"))
        e_stop_btn.setObjectName("danger")
        e_stop_btn.setMinimumHeight(44)
        e_stop_btn.clicked.connect(self.e_stop.emit)
        root.addWidget(e_stop_btn)
        self._estop_btn = e_stop_btn

        # ── GoPro status ──
        gopro_group = QGroupBox("GoPro")
        gopro_layout = QHBoxLayout(gopro_group)
        self._rec_btn = QPushButton("● REC")
        self._rec_btn.setCheckable(True)
        gopro_layout.addWidget(self._rec_btn)
        self._gopro_status = QLabel("Ready")
        self._gopro_status.setObjectName("heading")
        gopro_layout.addWidget(self._gopro_status)
        root.addWidget(gopro_group)

        root.addStretch()

        # Connections
        self._pan_slider.valueChanged.connect(
            lambda v: self._update_pan(float(v)))
        self._tilt_slider.valueChanged.connect(
            lambda v: self._update_tilt(float(v)))

    def _retranslate(self, _lang: str = ""):
        self._servo_header.setTitle(tr("control.servo_manual"))
        self._winch_header.setTitle(tr("control.winch"))
        self._estop_btn.setText(tr("control.e_stop"))
        self._pan_title_label.setText(tr("control.pan"))
        self._tilt_title_label.setText(tr("control.tilt"))
        labels = {
            "control.winch_up": self._winch_btns[0],
            "control.winch_stop": self._winch_btns[1],
            "control.winch_down": self._winch_btns[2],
        }
        for key, btn in labels.items():
            btn.setText(tr(key))

    def _update_pan(self, value: float):
        self._pan_label.setText(f"{value:.1f}°")
        self.pan_changed.emit(value)

    def _update_tilt(self, value: float):
        self._tilt_label.setText(f"{value:.1f}°")
        self.tilt_changed.emit(value)

    def set_servo_angles(self, pan: float, tilt: float):
        self._pan_slider.blockSignals(True)
        self._tilt_slider.blockSignals(True)
        self._pan_slider.setValue(int(pan))
        self._tilt_slider.setValue(int(tilt))
        self._pan_label.setText(f"{pan:.1f}°")
        self._tilt_label.setText(f"{tilt:.1f}°")
        self._pan_slider.blockSignals(False)
        self._tilt_slider.blockSignals(False)

    def set_gopro_status(self, recording: bool, battery: float, storage: float):
        if recording:
            self._gopro_status.setText(
                f"REC | Batt:{battery:.0f}% | Free:{storage:.0f}GB"
            )
        else:
            self._gopro_status.setText(
                f"Ready | Batt:{battery:.0f}% | Free:{storage:.0f}GB"
            )

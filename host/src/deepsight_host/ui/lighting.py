"""Compact manual/automatic fill-light control."""
from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider, QLabel
from deepsight_host.ui.i18n import I18n, tr


class LightingWidget(QGroupBox):
    manual_changed = Signal(int)
    auto_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 10)
        top = QHBoxLayout()
        self.auto = QCheckBox()
        self.value = QLabel('0%')
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName('补光灯亮度 / Fill light PWM')
        self.slider.setStyleSheet('''
            QSlider::groove:horizontal { height: 14px; background: #303044; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #8a9bff; border-radius: 7px; }
            QSlider::handle:horizontal { background: #eeeeff; width: 20px; margin: -4px 0; border-radius: 9px; }
            QSlider::sub-page:horizontal:disabled { background: #555568; }
            QSlider::handle:horizontal:disabled { background: #888894; }
        ''')
        top.addWidget(self.auto)
        top.addWidget(self.slider, 1)
        top.addWidget(self.value)
        self.value.setMinimumWidth(36)
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(top)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet('color: #9999aa; font-size: 10px;')
        layout.addWidget(self.hint)
        self.auto.toggled.connect(self._toggle_auto)
        self.slider.valueChanged.connect(self._manual)
        I18n.instance().language_changed.connect(self._retranslate)
        self._retranslate()
        self.setMinimumHeight(self.minimumSizeHint().height())

    def _retranslate(self, *_):
        self.setTitle(tr('lighting.title'))
        self.auto.setText(tr('lighting.auto'))
        self.hint.setText(tr('lighting.hint').format(
            zero=getattr(self, '_image_at_zero', 20), full=getattr(self, '_image_at_full', 0)))

    def _toggle_auto(self, enabled):
        self.slider.setEnabled(not enabled)
        self.auto_changed.emit(enabled)

    def _manual(self, percent):
        self.value.setText(f'{percent}%')
        self.manual_changed.emit(percent)

    def set_percent(self, percent):
        with QSignalBlocker(self.slider):
            self.slider.setValue(round(percent))
        self.value.setText(f'{round(percent)}%')

    def set_mapping(self, image_at_zero, image_at_full):
        self._image_at_zero = image_at_zero
        self._image_at_full = image_at_full
        self._retranslate()

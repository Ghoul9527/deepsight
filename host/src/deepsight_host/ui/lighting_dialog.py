"""Persistent inverse brightness mapping settings."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox,
                               QLabel, QDialogButtonBox, QMessageBox)
from deepsight_host.ui.i18n import tr


class LightingDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(tr('lighting.title'))
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.zero = QDoubleSpinBox()
        self.full = QDoubleSpinBox()
        for box in (self.zero, self.full):
            box.setRange(0, 100)
            box.setDecimals(1)
            box.setSuffix('%')
        self.zero.setValue(config.light_image_at_zero)
        self.full.setValue(config.light_image_at_full)
        form.addRow(tr('lighting.zero_image'), self.zero)
        form.addRow(tr('lighting.full_image'), self.full)
        layout.addLayout(form)
        help_text = QLabel(tr('lighting.range_help'))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        zero, full = self.zero.value(), self.full.value()
        if zero <= full:
            QMessageBox.warning(self, tr('lighting.title'), tr('lighting.range_error'))
            return
        try:
            self.config.save_lighting_range(zero, full)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr('lighting.title'), tr('lighting.save_error') + str(exc))
            return
        self.accept()

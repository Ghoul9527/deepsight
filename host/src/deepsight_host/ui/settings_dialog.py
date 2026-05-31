"""Settings dialog for DeepSight Host configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from PySide6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QDialogButtonBox,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt

from deepsight_host.config import HostConfig
from deepsight_host.ui.i18n import I18n, tr

logger = logging.getLogger("host.ui.settings")

CONFIG_PATH = Path("configs/host_config.yaml")


class SettingsDialog(QDialog):
    """Multi-tab settings dialog for host configuration."""

    def __init__(self, config: HostConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._i18n = I18n.instance()
        self._i18n.language_changed.connect(self._on_lang_changed)

        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(480, 400)
        self.setModal(True)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()

        # ── Network tab ──
        self._network_tab = QWidget()
        net_layout = QFormLayout(self._network_tab)
        net_layout.setSpacing(10)

        self._pi_ip = QLineEdit()
        self._pi_ip.setPlaceholderText("192.168.20.51")
        net_layout.addRow(tr("settings.pi_ip"), self._pi_ip)

        self._udp_port = QSpinBox()
        self._udp_port.setRange(1024, 65535)
        net_layout.addRow(tr("settings.udp_port"), self._udp_port)

        self._ws_port = QSpinBox()
        self._ws_port.setRange(1024, 65535)
        net_layout.addRow(tr("settings.ws_port"), self._ws_port)

        self._video_port = QSpinBox()
        self._video_port.setRange(1024, 65535)
        net_layout.addRow(tr("settings.video_port"), self._video_port)

        restart_hint = QLabel(tr("settings.restart_hint"))
        restart_hint.setStyleSheet("color: #888888; font-size: 11px;")
        net_layout.addRow("", restart_hint)

        self._tabs.addTab(self._network_tab, tr("settings.tab_network"))

        # ── Tracking tab ──
        self._tracking_tab = QWidget()
        trk_layout = QFormLayout(self._tracking_tab)
        trk_layout.setSpacing(10)

        self._tracking_mode = QComboBox()
        self._tracking_mode.addItems(["fast", "precise"])
        trk_layout.addRow(tr("settings.tracking_mode"), self._tracking_mode)

        self._confidence_thresh = QDoubleSpinBox()
        self._confidence_thresh.setRange(0.0, 1.0)
        self._confidence_thresh.setSingleStep(0.05)
        self._confidence_thresh.setDecimals(2)
        trk_layout.addRow(tr("settings.confidence"), self._confidence_thresh)

        self._iou_thresh = QDoubleSpinBox()
        self._iou_thresh.setRange(0.0, 1.0)
        self._iou_thresh.setSingleStep(0.05)
        self._iou_thresh.setDecimals(2)
        trk_layout.addRow(tr("settings.iou"), self._iou_thresh)

        self._tabs.addTab(self._tracking_tab, tr("settings.tab_tracking"))

        # ── Control tab ──
        self._control_tab = QWidget()
        ctrl_layout = QFormLayout(self._control_tab)
        ctrl_layout.setSpacing(10)

        self._pid_p = QDoubleSpinBox()
        self._pid_p.setRange(0.0, 10.0)
        self._pid_p.setSingleStep(0.1)
        self._pid_p.setDecimals(2)
        ctrl_layout.addRow("PID P", self._pid_p)

        self._pid_i = QDoubleSpinBox()
        self._pid_i.setRange(0.0, 10.0)
        self._pid_i.setSingleStep(0.01)
        self._pid_i.setDecimals(3)
        ctrl_layout.addRow("PID I", self._pid_i)

        self._pid_d = QDoubleSpinBox()
        self._pid_d.setRange(0.0, 10.0)
        self._pid_d.setSingleStep(0.1)
        self._pid_d.setDecimals(2)
        ctrl_layout.addRow("PID D", self._pid_d)

        self._max_servo_speed = QDoubleSpinBox()
        self._max_servo_speed.setRange(1.0, 360.0)
        self._max_servo_speed.setSuffix(" deg/s")
        ctrl_layout.addRow(tr("settings.max_servo_speed"), self._max_servo_speed)

        self._dead_zone = QDoubleSpinBox()
        self._dead_zone.setRange(0.0, 0.5)
        self._dead_zone.setSingleStep(0.01)
        self._dead_zone.setDecimals(3)
        self._dead_zone.setToolTip(tr("settings.dead_zone_tip"))
        ctrl_layout.addRow(tr("settings.dead_zone"), self._dead_zone)

        self._neutral_angle = QDoubleSpinBox()
        self._neutral_angle.setRange(0.0, 180.0)
        self._neutral_angle.setSuffix(" deg")
        ctrl_layout.addRow(tr("settings.neutral_angle"), self._neutral_angle)

        self._tabs.addTab(self._control_tab, tr("settings.tab_control"))

        # ── Gimbal tab ──
        self._gimbal_tab = QWidget()
        gim_layout = QFormLayout(self._gimbal_tab)
        gim_layout.setSpacing(10)

        self._gimbal_yaw_max = QDoubleSpinBox()
        self._gimbal_yaw_max.setRange(1.0, 90.0)
        self._gimbal_yaw_max.setSingleStep(1.0)
        self._gimbal_yaw_max.setSuffix(" deg")
        gim_layout.addRow(tr("settings.gimbal_yaw_max"), self._gimbal_yaw_max)

        self._gimbal_pitch_max = QDoubleSpinBox()
        self._gimbal_pitch_max.setRange(1.0, 90.0)
        self._gimbal_pitch_max.setSingleStep(1.0)
        self._gimbal_pitch_max.setSuffix(" deg")
        gim_layout.addRow(tr("settings.gimbal_pitch_max"), self._gimbal_pitch_max)

        self._tabs.addTab(self._gimbal_tab, tr("settings.tab_gimbal"))

        # ── Plate tab ──
        self._plate_tab = QWidget()
        plate_layout = QFormLayout(self._plate_tab)
        plate_layout.setSpacing(10)

        self._plate_max = QDoubleSpinBox()
        self._plate_max.setRange(1.0, 90.0)
        self._plate_max.setSingleStep(1.0)
        self._plate_max.setSuffix(" deg")
        plate_layout.addRow(tr("settings.plate_max"), self._plate_max)

        self._tabs.addTab(self._plate_tab, tr("settings.tab_plate"))

        # ── Safety tab ──
        self._safety_tab = QWidget()
        saf_layout = QFormLayout(self._safety_tab)
        saf_layout.setSpacing(10)

        self._lost_hold = QDoubleSpinBox()
        self._lost_hold.setRange(0.0, 10.0)
        self._lost_hold.setSingleStep(0.1)
        self._lost_hold.setSuffix(" s")
        saf_layout.addRow(tr("settings.lost_hold"), self._lost_hold)

        self._lost_neutral = QDoubleSpinBox()
        self._lost_neutral.setRange(0.0, 30.0)
        self._lost_neutral.setSingleStep(0.5)
        self._lost_neutral.setSuffix(" s")
        saf_layout.addRow(tr("settings.lost_neutral"), self._lost_neutral)

        self._tabs.addTab(self._safety_tab, tr("settings.tab_safety"))

        # ── Logging tab ──
        self._logging_tab = QWidget()
        log_layout = QFormLayout(self._logging_tab)
        log_layout.setSpacing(10)

        self._log_level = QComboBox()
        self._log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_layout.addRow(tr("settings.log_level"), self._log_level)

        self._telemetry_record = QComboBox()
        self._telemetry_record.addItems([tr("settings.off"), tr("settings.on")])
        log_layout.addRow(tr("settings.telemetry_record"), self._telemetry_record)

        self._tabs.addTab(self._logging_tab, tr("settings.tab_logging"))

        layout.addWidget(self._tabs)

        # ── Buttons ──
        button_row = QHBoxLayout()

        self._reset_btn = QPushButton(tr("settings.reset_defaults"))
        self._reset_btn.clicked.connect(self._reset_defaults)
        button_row.addWidget(self._reset_btn)

        button_row.addStretch()

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._btn_box.accepted.connect(self._save_and_accept)
        self._btn_box.rejected.connect(self.reject)
        button_row.addWidget(self._btn_box)

        layout.addLayout(button_row)

    def _load_values(self):
        """Populate fields from current config."""
        c = self._config
        self._pi_ip.setText(c.pi_address)
        self._udp_port.setValue(c.pi_udp_port)
        self._ws_port.setValue(c.pi_ws_port)
        # Parse video port from stream_url
        video_port = 8554
        try:
            if ":" in c.stream_url:
                video_port = int(c.stream_url.rsplit(":", 1)[-1])
        except (ValueError, IndexError):
            pass
        self._video_port.setValue(video_port)

        self._tracking_mode.setCurrentText(c.tracking_mode)
        self._confidence_thresh.setValue(c.confidence_threshold)
        self._iou_thresh.setValue(c.iou_threshold)

        self._pid_p.setValue(c.pid_p)
        self._pid_i.setValue(c.pid_i)
        self._pid_d.setValue(c.pid_d)
        self._max_servo_speed.setValue(c.max_servo_speed)
        self._dead_zone.setValue(c.dead_zone)
        self._neutral_angle.setValue(c.servo_neutral_angle)

        self._gimbal_yaw_max.setValue(c.gimbal_yaw_max_angle)
        self._gimbal_pitch_max.setValue(c.gimbal_pitch_max_angle)
        self._plate_max.setValue(c.plate_max_angle)

        self._lost_hold.setValue(c.tracking_lost_hold_s)
        self._lost_neutral.setValue(c.tracking_lost_neutral_s)

        self._log_level.setCurrentText(c.log_level)
        self._telemetry_record.setCurrentIndex(1 if c.telemetry_record else 0)

    def _save_and_accept(self):
        """Write values back to config file and update runtime config."""
        c = self._config

        # Network
        old_pi = c.pi_address
        c.pi_address = self._pi_ip.text().strip() or "192.168.20.51"
        c.pi_udp_port = self._udp_port.value()
        c.pi_ws_port = self._ws_port.value()
        video_port = self._video_port.value()
        # Rebuild stream URL (UDP — Host listens, Pi forwards to us)
        c.stream_url = f"udp://0.0.0.0:{video_port}"

        # Tracking
        c.tracking_mode = self._tracking_mode.currentText()
        c.confidence_threshold = self._confidence_thresh.value()
        c.iou_threshold = self._iou_thresh.value()

        # Control
        c.pid_p = self._pid_p.value()
        c.pid_i = self._pid_i.value()
        c.pid_d = self._pid_d.value()
        c.max_servo_speed = self._max_servo_speed.value()
        c.dead_zone = self._dead_zone.value()
        c.servo_neutral_angle = self._neutral_angle.value()

        # Gimbal
        c.gimbal_yaw_max_angle = self._gimbal_yaw_max.value()
        c.gimbal_pitch_max_angle = self._gimbal_pitch_max.value()

        # Plate
        c.plate_max_angle = self._plate_max.value()

        # Safety
        c.tracking_lost_hold_s = self._lost_hold.value()
        c.tracking_lost_neutral_s = self._lost_neutral.value()

        # Logging
        c.log_level = self._log_level.currentText()
        c.telemetry_record = self._telemetry_record.currentIndex() == 1

        self._write_config_file()

        # Warn if network changed (requires restart)
        if c.pi_address != old_pi:
            QMessageBox.information(
                self,
                tr("settings.restart_title"),
                tr("settings.restart_message"),
            )

        self.accept()

    def _write_config_file(self):
        """Persist current settings to host_config.yaml."""
        c = self._config
        data = {
            "host": {
                "id": c.host_id,
                "udp_port": c.udp_port,
                "ws_port": c.ws_port,
            },
            "network": {
                "pi_address": c.pi_address,
                "pi_udp_port": c.pi_udp_port,
                "pi_ws_port": c.pi_ws_port,
            },
            "video": {
                "stream_url": c.stream_url,
            },
            "mock": {
                "enabled": c.mock_enabled,
                "video_source": c.mock_video_source,
                "tracking_target": c.mock_tracking_target,
                "frame_width": c.frame_width,
                "frame_height": c.frame_height,
                "fps": c.fps,
            },
            "tracking": {
                "mode": c.tracking_mode,
                "model_path": c.model_path,
                "confidence_threshold": c.confidence_threshold,
                "iou_threshold": c.iou_threshold,
            },
            "control": {
                "pid_p": c.pid_p,
                "pid_i": c.pid_i,
                "pid_d": c.pid_d,
                "max_servo_speed": c.max_servo_speed,
                "dead_zone": c.dead_zone,
            },
            "gimbal": {
                "yaw_max_angle": c.gimbal_yaw_max_angle,
                "pitch_max_angle": c.gimbal_pitch_max_angle,
            },
            "plate": {
                "max_angle": c.plate_max_angle,
            },
            "safety": {
                "tracking_lost_hold_s": c.tracking_lost_hold_s,
                "tracking_lost_neutral_s": c.tracking_lost_neutral_s,
                "servo_neutral_angle": c.servo_neutral_angle,
            },
            "logging": {
                "level": c.log_level,
                "dir": c.log_dir,
                "telemetry_record": c.telemetry_record,
            },
        }
        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info("Settings saved to %s", CONFIG_PATH)

    def _reset_defaults(self):
        """Reset all fields to default values."""
        self._pi_ip.setText("192.168.20.51")
        self._udp_port.setValue(5100)
        self._ws_port.setValue(5101)
        self._video_port.setValue(8554)
        self._tracking_mode.setCurrentText("fast")
        self._confidence_thresh.setValue(0.5)
        self._iou_thresh.setValue(0.45)
        self._pid_p.setValue(0.8)
        self._pid_i.setValue(0.05)
        self._pid_d.setValue(0.2)
        self._max_servo_speed.setValue(60.0)
        self._dead_zone.setValue(0.02)
        self._neutral_angle.setValue(90.0)
        self._gimbal_yaw_max.setValue(15.0)
        self._gimbal_pitch_max.setValue(15.0)
        self._plate_max.setValue(45.0)
        self._lost_hold.setValue(0.5)
        self._lost_neutral.setValue(2.0)
        self._log_level.setCurrentText("DEBUG")
        self._telemetry_record.setCurrentIndex(0)

    def _on_lang_changed(self, lang: str):
        self.setWindowTitle(tr("settings.title"))
        self._tabs.setTabText(0, tr("settings.tab_network"))
        self._tabs.setTabText(1, tr("settings.tab_tracking"))
        self._tabs.setTabText(2, tr("settings.tab_control"))
        self._tabs.setTabText(3, tr("settings.tab_gimbal"))
        self._tabs.setTabText(4, tr("settings.tab_plate"))
        self._tabs.setTabText(5, tr("settings.tab_safety"))
        self._tabs.setTabText(6, tr("settings.tab_logging"))
        self._btn_box.button(QDialogButtonBox.Ok).setText(tr("settings.ok"))
        self._btn_box.button(QDialogButtonBox.Cancel).setText(tr("settings.cancel"))
        self._reset_btn.setText(tr("settings.reset_defaults"))

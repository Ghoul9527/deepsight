import numpy as np
import pytest
from unittest.mock import Mock
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from deepsight_host.video.brightness import average_brightness_pct
from deepsight_host.ui.dashboard import DashboardWidget
from deepsight_host.ui.component_status import ComponentStatusWidget
from deepsight_host.app import HostApp
from deepsight_shared.constants import SafetyState

@pytest.mark.parametrize('pixel,expected', [([0,0,0],0),([255,255,255],100),([0,0,255],29.9),([0,255,0],58.7),([255,0,0],11.4)])
def test_image_brightness(pixel,expected):
    frame=np.full((8,10,3),pixel,dtype=np.uint8)
    assert average_brightness_pct(frame)==pytest.approx(expected)


def test_sensor_rows_and_independent_servo_indicator():
    app=QApplication.instance() or QApplication([])
    dashboard=DashboardWidget()
    assert set(dashboard._labels)=={'roll','depth','pressure','water_temp','frame_brightness','light_pwm','leak_ch0','leak_pi'}
    dashboard.update_value('frame_brightness',42.5)
    assert '42.5%' in dashboard._labels['frame_brightness'].text()
    dashboard.update_value('frame_brightness',None)
    assert dashboard._labels['frame_brightness'].text()=='---'
    components=ComponentStatusWidget()
    assert 'pca9685' in components._indicators
    components.update_component('pca9685',SafetyState.EMERGENCY,0,'I2C failed')
    components.update_component('pico',SafetyState.NOMINAL)
    assert components._indicators['pca9685']._state==SafetyState.EMERGENCY
    assert components._indicators['pico']._state==SafetyState.NOMINAL


def test_actuator_status_becomes_lost_without_pi_telemetry():
    app=SimpleNamespace(_registry=Mock(),_window=Mock(),_actuator_status=(0,True,''))
    app._registry.get_all.return_value={}
    HostApp._check_nodes(app)
    assert app._window.component_status.update_component.call_args.args[1]==SafetyState.SAFE


def test_preset_overlay_updates_and_clears():
    from deepsight_host.ui.video_preview import VideoPreviewWidget
    app = QApplication.instance() or QApplication([])
    widget = VideoPreviewWidget()
    widget.set_preset({"id": 1, "title": "Dive", "summary": "4K · 60 · Wide"})
    assert widget._preset_label.text() == "Dive\n4K · 60 · Wide"
    widget.set_preset({"id": 2, "title": "Night"})
    assert widget._preset_label.text() == "Night"
    widget.set_preset(None)
    assert widget._preset_label.isHidden()
    assert widget._preset_label.text() == ""

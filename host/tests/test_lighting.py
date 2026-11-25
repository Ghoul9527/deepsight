import time
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication
from deepsight_host.ui.lighting import LightingWidget
from deepsight_host.control.auto_light import next_light_percent
from deepsight_host.app import HostApp


@pytest.mark.parametrize('image,pwm,expected', [(0,0,100),(10,100,50),(20,50,0),(42,50,0),(5,99,75),(100,1,0)])
def test_auto_light_step(image,pwm,expected):
    assert next_light_percent(image,pwm)==expected


def test_auto_disables_manual_slider_and_programmatic_update_is_silent():
    app=QApplication.instance() or QApplication([])
    w=LightingWidget()
    manual=[]
    w.manual_changed.connect(manual.append)
    w.slider.setValue(25)
    assert manual==[25]
    w.auto.setChecked(True)
    assert not w.slider.isEnabled()
    w.set_percent(45)
    assert manual==[25] and w.value.text()=='45%'
    w.auto.setChecked(False)
    assert w.slider.isEnabled() and w.slider.value()==45


def fake_host():
    app=SimpleNamespace(_window=Mock(),_controller=Mock(),_light_auto=True,
        _light_requested_pct=20.,_light_actual_pct=20.,_light_image_pct=0.,
        _last_brightness_update=time.monotonic(),_light_last_auto=0.,
        _actuator_status=(time.monotonic(),True,''),_udp=Mock(),_schedule_async=Mock(),
        config=SimpleNamespace(light_image_at_zero=20.,light_image_at_full=0.))
    return app


def test_auto_pauses_on_stale_video_and_disconnected_driver():
    for reason in ['video','driver']:
        app=fake_host()
        if reason=='video':app._last_brightness_update-=10
        else:app._actuator_status=(0,True,'')
        HostApp._refresh_lighting(app)
        app._udp.send.assert_not_called()
        assert app._light_requested_pct==20


def test_auto_sends_bounded_command_then_rate_limits():
    app=fake_host()
    HostApp._refresh_lighting(app)
    assert app._light_requested_pct==100
    msg=app._udp.send.call_args.args[0]
    assert msg.type=='cmd.light' and msg.payload['brightness']==1.0
    HostApp._refresh_lighting(app)
    assert app._udp.send.call_count==1


def test_gamepad_exits_auto_and_uses_same_manual_control():
    app=SimpleNamespace(_window=Mock(),_on_light_manual=Mock())
    HostApp._on_light_level(app,7)
    app._window.lighting.auto.setChecked.assert_called_once_with(False)
    app._on_light_manual.assert_called_once_with(70)


def test_custom_mapping():
    assert next_light_percent(20, 0, 30, 10) == 50
    assert next_light_percent(40, 0, 30, 10) == 0
    assert next_light_percent(0, 0, 30, 10) == 100
    with pytest.raises(ValueError):
        next_light_percent(10, 0, 20, 20)


def test_mapping_persistence_preserves_other_config(tmp_path):
    import yaml
    from deepsight_host.config import HostConfig
    path = tmp_path/'host.yaml'
    original = {'lighting': {'unrelated': True}, 'gopro': {'model': 'Mission 1 Pro'},
                'tracking': {'inference_backend': 'coreml'},
                'logging': {'dir': str(tmp_path/'logs')}}
    path.write_text(yaml.safe_dump(original))
    config=HostConfig(path)
    assert (config.light_image_at_zero, config.light_image_at_full)==(20,0)
    config.save_lighting_range(30,5)
    loaded=HostConfig(path)
    assert (loaded.light_image_at_zero, loaded.light_image_at_full)==(30,5)
    data=yaml.safe_load(path.read_text())
    assert data['gopro']==original['gopro'] and data['tracking']==original['tracking']
    assert data['lighting']['unrelated']
    before=path.read_text()
    with pytest.raises(ValueError):config.save_lighting_range(5,30)
    assert path.read_text()==before


def test_auto_checkbox_is_left_of_slider():
    app=QApplication.instance() or QApplication([])
    w=LightingWidget();w.resize(400,130);w.show();app.processEvents()
    assert w.auto.geometry().right() < w.slider.geometry().left()
    assert abs(w.auto.geometry().center().y()-w.slider.geometry().center().y())<10
    w.close()


def test_dialog_saves_range(tmp_path):
    import yaml
    from deepsight_host.config import HostConfig
    from deepsight_host.ui.lighting_dialog import LightingDialog
    app=QApplication.instance() or QApplication([])
    path=tmp_path/'host.yaml'
    path.write_text(yaml.safe_dump({'logging': {'dir': str(tmp_path/'logs')}}))
    config=HostConfig(path)
    dialog=LightingDialog(config)
    dialog.zero.setValue(35);dialog.full.setValue(5);dialog.save()
    assert dialog.result()==1
    assert HostConfig(path).light_image_at_zero==35

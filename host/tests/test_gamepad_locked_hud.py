"""HUD input works while locked; movement and action buttons remain blocked."""
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication
from deepsight_host.control.controller import GameController

@pytest.mark.parametrize('backend', ['bridge', 'pygame'])
def test_locked_hud_edge_without_motion(backend):
    app = QApplication.instance() or QApplication([])
    controller = GameController()
    hud, recenter, winch = [], [], []
    controller.hud_toggle.connect(lambda: hud.append(True))
    controller.body_recenter.connect(lambda: recenter.append(True))
    controller.winch_speed_changed.connect(winch.append)
    buttons = [0]*13
    buttons[2] = buttons[8] = 1  # X plus a movement action
    if backend == 'bridge':
        controller._read_bridge = lambda: None
        controller._bridge_state = {'axes': [1.0]*6, 'buttons': buttons, 'hat': [0,0]}
        poll = controller._poll_bridge
    else:
        controller._joystick = Mock()
        controller._joystick.get_numbuttons.return_value = 13
        controller._joystick.get_button.side_effect = lambda index: buttons[index]
        poll = controller._poll_buttons
    poll()
    poll()  # held button should trigger only once
    assert hud == [True]
    assert recenter == []
    assert controller.locked
    assert all(value == 0 for value in winch)
    buttons[2] = 0
    poll()
    buttons[2] = 1
    poll()
    assert hud == [True, True]

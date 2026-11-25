"""Native helper lifecycle must not leave stale movement active."""
import time
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from deepsight_host.control.controller import GameController, LockState


def controller():
    app = QApplication.instance() or QApplication([])
    pad = GameController()
    pad._app_ref = app
    pad._use_bridge = True
    pad._bridge_proc = Mock()
    pad._bridge_proc.poll.return_value = None
    pad._bridge_last_seen = time.monotonic()
    return pad


def test_disconnect_stops_and_locks_and_reconnect_stays_locked():
    pad = controller()
    pad._connected, pad._locked = True, False
    pad._smooth_winch = 0.8
    pad._bridge_state = {'connected': False, 'axes': [1]*6}
    movement, locks, connections = [], [], []
    pad.winch_speed_changed.connect(movement.append)
    pad.lock_state_changed.connect(locks.append)
    pad.connection_changed.connect(connections.append)
    pad._poll()
    assert not pad.connected and pad.locked
    assert movement == [0.0] and locks == [LockState.LOCKED]
    pad._bridge_state = {'connected': True, 'axes': [0]*6, 'buttons': [0]*13}
    pad._poll()
    assert pad.connected and pad.locked
    assert connections == [False, True]


def test_hung_or_exited_helper_cannot_replay_last_movement():
    for exited in [False, True]:
        pad = controller()
        pad._connected, pad._locked = True, False
        pad._bridge_state = {'connected': True, 'axes': [1]*6, 'buttons': [0]*13}
        if exited:
            pad._bridge_proc.poll.return_value = 1
        else:
            pad._bridge_last_seen -= 2
        movement = []
        pad.winch_speed_changed.connect(movement.append)
        pad._poll()
        assert movement == [0.0]
        assert pad.locked and not pad.connected


def test_held_start_on_reconnection_does_not_unlock():
    pad = controller()
    buttons = [0]*13
    buttons[7] = 1
    pad._bridge_state = {'connected': True, 'axes': [0]*6, 'buttons': buttons}
    pad._poll()
    pad._poll()
    assert pad.connected and pad.locked
    buttons[7] = 0
    pad._poll()
    buttons[7] = 1
    pad._poll()
    assert not pad.locked

#include "safety.h"

void safety_init(SafetyModule *s) {
    s->last_command_time_s = 0.0f;
    s->auto_stop_active = false;
}

void safety_check(SafetyModule *s, WinchFSM *fsm, LimitState limits, EStopState estop, float now_s) {
    /* Hardware emergency stop — always active */
    if (estop != ESTOP_INACTIVE && AUTO_STOP_ON_ESTOP) {
        winch_fsm_emergency_stop(fsm);
        return;
    }

    /* Limit switches — stop if moving into a triggered limit */
    if (AUTO_STOP_ON_LIMIT) {
        if (limits.top_triggered && fsm->state == WINCH_MOVING_UP) {
            winch_fsm_stop(fsm);
        }
        if (limits.bottom_triggered && fsm->state == WINCH_MOVING_DOWN) {
            winch_fsm_stop(fsm);
        }
    }

    /* Command timeout — if no command received for >1s, stop */
    if (now_s - s->last_command_time_s > 1.0f) {
        if (!s->auto_stop_active) {
            s->auto_stop_active = true;
            winch_fsm_stop(fsm);
        }
    }
}

void safety_notify_command(SafetyModule *s, float now_s) {
    s->last_command_time_s = now_s;
    s->auto_stop_active = false;
}

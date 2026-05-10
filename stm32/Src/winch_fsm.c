#include "winch_fsm.h"
#include "board_config.h"
#include <math.h>

static float clamp_speed(float speed) {
    if (speed > WINCH_MAX_SPEED_MM_S) return WINCH_MAX_SPEED_MM_S;
    if (speed < -WINCH_MAX_SPEED_MM_S) return -WINCH_MAX_SPEED_MM_S;
    return speed;
}

void winch_fsm_init(WinchFSM *fsm) {
    fsm->state = WINCH_IDLE;
    fsm->position_mm = 2500.0f;  /* Mid-point */
    fsm->speed_mm_s = 0.0f;
    fsm->target_speed = 0.0f;
    fsm->encoder_ticks = 2500 * WINCH_ENCODER_TICKS_MM;
}

void winch_fsm_update(WinchFSM *fsm, float dt) {
    if (fsm->state == WINCH_ESTOP || fsm->state == WINCH_ERROR) {
        fsm->speed_mm_s = 0.0f;
        return;
    }

    if (fsm->state == WINCH_IDLE) {
        fsm->speed_mm_s = 0.0f;
        return;
    }

    /* Simple ramp to target speed */
    float error = fsm->target_speed - fsm->speed_mm_s;
    float ramp = error * dt * 5.0f;  /* 5 Hz ramp */
    fsm->speed_mm_s += ramp;

    /* Update position */
    fsm->position_mm += fsm->speed_mm_s * dt;
    if (fsm->position_mm < 0.0f) fsm->position_mm = 0.0f;
    if (fsm->position_mm > WINCH_MAX_TRAVEL_MM) fsm->position_mm = WINCH_MAX_TRAVEL_MM;

    /* Update encoder */
    fsm->encoder_ticks = (uint32_t)(fsm->position_mm * WINCH_ENCODER_TICKS_MM);
}

void winch_fsm_set_speed(WinchFSM *fsm, float speed) {
    if (fsm->state == WINCH_ESTOP) return;
    fsm->target_speed = clamp_speed(speed);
    if (fabs(speed) < 0.1f) {
        fsm->state = WINCH_IDLE;
    } else if (speed > 0) {
        fsm->state = WINCH_MOVING_UP;
    } else {
        fsm->state = WINCH_MOVING_DOWN;
    }
}

void winch_fsm_stop(WinchFSM *fsm) {
    fsm->target_speed = 0.0f;
    fsm->state = WINCH_STOPPING;
}

void winch_fsm_emergency_stop(WinchFSM *fsm) {
    fsm->target_speed = 0.0f;
    fsm->speed_mm_s = 0.0f;
    fsm->state = WINCH_ESTOP;
}

void winch_fsm_set_encoder(WinchFSM *fsm, uint32_t ticks) {
    fsm->encoder_ticks = ticks;
    fsm->position_mm = (float)ticks / WINCH_ENCODER_TICKS_MM;
}

const char* winch_state_name(WinchState state) {
    switch (state) {
        case WINCH_IDLE:       return "IDLE";
        case WINCH_MOVING_UP:  return "MOVING_UP";
        case WINCH_MOVING_DOWN: return "MOVING_DOWN";
        case WINCH_STOPPING:   return "STOPPING";
        case WINCH_ESTOP:      return "ESTOP";
        case WINCH_ERROR:      return "ERROR";
        default:               return "UNKNOWN";
    }
}

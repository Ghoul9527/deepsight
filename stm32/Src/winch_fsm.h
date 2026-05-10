#ifndef WINCH_FSM_H
#define WINCH_FSM_H

#include "board_config.h"

typedef enum {
    WINCH_IDLE,
    WINCH_MOVING_UP,
    WINCH_MOVING_DOWN,
    WINCH_STOPPING,
    WINCH_ESTOP,
    WINCH_ERROR
} WinchState;

typedef struct {
    WinchState state;
    float position_mm;
    float speed_mm_s;
    float target_speed;
    uint32_t encoder_ticks;
} WinchFSM;

void winch_fsm_init(WinchFSM *fsm);
void winch_fsm_update(WinchFSM *fsm, float dt);
void winch_fsm_set_speed(WinchFSM *fsm, float speed);
void winch_fsm_stop(WinchFSM *fsm);
void winch_fsm_emergency_stop(WinchFSM *fsm);
void winch_fsm_set_encoder(WinchFSM *fsm, uint32_t ticks);

const char* winch_state_name(WinchState state);

#endif /* WINCH_FSM_H */

#ifndef SAFETY_H
#define SAFETY_H

#include "board_config.h"
#include "winch_fsm.h"
#include "limit_switches.h"
#include "e_stop.h"

typedef struct {
    float last_command_time_s;
    bool auto_stop_active;
} SafetyModule;

void safety_init(SafetyModule *s);
void safety_check(SafetyModule *s, WinchFSM *fsm, LimitState limits, EStopState estop, float now_s);
void safety_notify_command(SafetyModule *s, float now_s);

#endif /* SAFETY_H */

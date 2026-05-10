#ifndef MOTOR_CTRL_H
#define MOTOR_CTRL_H

#include "board_config.h"

typedef struct {
    float current_speed_rpm;
    float current_a;
    bool enabled;
} MotorState;

void motor_init(void);
void motor_set_speed(float speed_pct);  /* -1.0 to 1.0 */
void motor_stop(void);
void motor_enable(void);
void motor_disable(void);
MotorState motor_get_state(void);

void motor_mock_update(float dt);  /* Mock mode only */

#endif /* MOTOR_CTRL_H */

#ifndef MOCK_MOTOR_H
#define MOCK_MOTOR_H

#include "board_config.h"

void mock_motor_init(void);
void mock_motor_set_speed(float speed_pct);
float mock_motor_get_speed(void);
float mock_motor_get_current(void);
void mock_motor_update(float dt);

#endif /* MOCK_MOTOR_H */

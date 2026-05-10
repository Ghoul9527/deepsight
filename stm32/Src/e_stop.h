#ifndef ESTOP_H
#define ESTOP_H

#include "board_config.h"

typedef enum {
    ESTOP_INACTIVE,
    ESTOP_ACTIVE_HARDWARE,  /* Physical button pressed */
    ESTOP_ACTIVE_COMMAND,   /* Commanded over serial */
} EStopState;

void estop_init(void);
EStopState estop_read(void);
void estop_trigger_command(void);
void estop_clear(void);
void estop_mock_set(bool active);

#endif /* ESTOP_H */

#ifndef LIMIT_SWITCHES_H
#define LIMIT_SWITCHES_H

#include "board_config.h"

typedef struct {
    bool top_triggered;
    bool bottom_triggered;
} LimitState;

void limit_switches_init(void);
LimitState limit_switches_read(void);
void limit_switches_mock_set(bool top, bool bottom);

#endif /* LIMIT_SWITCHES_H */

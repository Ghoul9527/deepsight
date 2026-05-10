#ifndef SERIAL_LINK_H
#define SERIAL_LINK_H

#include "board_config.h"

typedef struct {
    char buffer[512];
    uint16_t len;
} SerialLink;

void serial_init(void);
bool serial_available(void);
char serial_read_char(void);
void serial_read_line(SerialLink *link);
void serial_write(const char *data);
void serial_write_line(const char *data);

/* Mock mode: inject data for testing */
void serial_mock_inject(const char *line);

#endif /* SERIAL_LINK_H */

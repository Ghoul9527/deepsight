#ifndef COMMAND_PARSER_H
#define COMMAND_PARSER_H

#include "board_config.h"

typedef struct {
    char type[64];
    float speed;
    char direction[8];
    /* Winch command fields */
} ParsedCommand;

bool command_parse(const char *json_line, ParsedCommand *cmd);

#endif /* COMMAND_PARSER_H */

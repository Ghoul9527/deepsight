#include "command_parser.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

bool command_parse(const char *json_line, ParsedCommand *cmd) {
    if (!json_line || !cmd) return false;

    memset(cmd, 0, sizeof(*cmd));

    /* Simple JSON parser for known message types.
     * In production, use a proper JSON library like jsmn or cJSON.
     * For the skeleton, we parse the essential fields manually.
     */

    /* Check message type */
    const char *type_start = strstr(json_line, "\"type\"");
    if (!type_start) return false;

    type_start = strchr(type_start, ':');
    if (!type_start) return false;
    type_start++;  /* skip colon */
    while (*type_start == ' ' || *type_start == '"') type_start++;

    /* Copy type */
    int i = 0;
    while (*type_start && *type_start != '"' && *type_start != ',' && i < 63) {
        cmd->type[i++] = *type_start++;
    }
    cmd->type[i] = '\0';

    /* If winch set command, extract speed and direction */
    if (strcmp(cmd->type, "cmd.winch.set") == 0) {
        const char *speed_start = strstr(json_line, "\"speed\"");
        if (speed_start) {
            speed_start = strchr(speed_start, ':');
            if (speed_start) {
                speed_start++;
                while (*speed_start == ' ') speed_start++;
                cmd->speed = (float)atof(speed_start);
            }
        }
    }

    return true;
}

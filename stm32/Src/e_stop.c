#include "e_stop.h"

static bool g_mock_active = false;
static bool g_command_active = false;

void estop_init(void) {
#ifdef MOCK_MODE
    g_mock_active = false;
    g_command_active = false;
#else
    /* Configure GPIO input */
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = ESTOP_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = ESTOP_ACTIVE_LOW ? GPIO_PULLUP : GPIO_PULLDOWN;
    HAL_GPIO_Init(ESTOP_PORT, &gpio);
#endif
}

EStopState estop_read(void) {
#ifdef MOCK_MODE
    if (g_mock_active) return ESTOP_ACTIVE_HARDWARE;
    if (g_command_active) return ESTOP_ACTIVE_COMMAND;
    return ESTOP_INACTIVE;
#else
    GPIO_PinState pin = HAL_GPIO_ReadPin(ESTOP_PORT, ESTOP_PIN);
    bool triggered = ESTOP_ACTIVE_LOW ? (pin == GPIO_PIN_RESET) : (pin == GPIO_PIN_SET);
    if (triggered) return ESTOP_ACTIVE_HARDWARE;
    if (g_command_active) return ESTOP_ACTIVE_COMMAND;
    return ESTOP_INACTIVE;
#endif
}

void estop_trigger_command(void) {
    g_command_active = true;
}

void estop_clear(void) {
    g_command_active = false;
#ifdef MOCK_MODE
    g_mock_active = false;
#endif
}

void estop_mock_set(bool active) {
#ifdef MOCK_MODE
    g_mock_active = active;
#endif
}

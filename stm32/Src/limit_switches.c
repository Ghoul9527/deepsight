#include "limit_switches.h"

static bool g_mock_top = false;
static bool g_mock_bottom = false;

void limit_switches_init(void) {
#ifdef MOCK_MODE
    g_mock_top = false;
    g_mock_bottom = false;
#else
    /* Configure GPIO inputs with pull-ups (NC switches → GND when triggered) */
    __HAL_RCC_GPIOB_CLK_ENABLE();
    GPIO_InitTypeDef gpio = {0};
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    gpio.Pin = LIMIT_TOP_PIN | LIMIT_BOTTOM_PIN;
    HAL_GPIO_Init(LIMIT_TOP_PORT, &gpio);
#endif
}

LimitState limit_switches_read(void) {
    LimitState state;
#ifdef MOCK_MODE
    state.top_triggered = g_mock_top;
    state.bottom_triggered = g_mock_bottom;
#else
    state.top_triggered = (HAL_GPIO_ReadPin(LIMIT_TOP_PORT, LIMIT_TOP_PIN) == GPIO_PIN_RESET);
    state.bottom_triggered = (HAL_GPIO_ReadPin(LIMIT_BOTTOM_PORT, LIMIT_BOTTOM_PIN) == GPIO_PIN_RESET);
#endif
    return state;
}

void limit_switches_mock_set(bool top, bool bottom) {
#ifdef MOCK_MODE
    g_mock_top = top;
    g_mock_bottom = bottom;
#endif
}

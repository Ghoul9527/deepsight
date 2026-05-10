#include "motor_ctrl.h"
#include "board_config.h"
#include <math.h>

#ifdef MOCK_MODE
#include "mock_motor.h"
#endif

static MotorState g_motor;

void motor_init(void) {
    g_motor.current_speed_rpm = 0.0f;
    g_motor.current_a = 0.0f;
    g_motor.enabled = false;

#ifdef MOCK_MODE
    mock_motor_init();
#else
    /* ── TIM PWM for motor speed ── */
    __HAL_RCC_TIM2_CLK_ENABLE();
    TIM_HandleTypeDef htim2 = {0};
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = (SystemCoreClock / (MOTOR_PWM_FREQ_HZ * 1000)) - 1;
    htim2.Init.Period = 999;  /* 0-999 = 0%-100% duty */
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_PWM_Init(&htim2);
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, MOTOR_PWM_CHANNEL);
    HAL_TIM_PWM_Start(&htim2, MOTOR_PWM_CHANNEL);

    /* ── DIR GPIO ── */
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = MOTOR_DIR_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(MOTOR_DIR_PORT, &gpio);

    /* ── ENABLE GPIO ── */
    gpio.Pin = MOTOR_ENABLE_PIN;
    HAL_GPIO_Init(MOTOR_ENABLE_PORT, &gpio);
    HAL_GPIO_WritePin(MOTOR_ENABLE_PORT, MOTOR_ENABLE_PIN, GPIO_PIN_RESET);

    /* ── ADC for current sensing ── */
    __HAL_RCC_ADC1_CLK_ENABLE();
    ADC_HandleTypeDef hadc1 = {0};
    hadc1.Instance = ADC1;
    hadc1.Init.Resolution = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode = DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    HAL_ADC_Init(&hadc1);
#endif
}

void motor_set_speed(float speed_pct) {
    if (!g_motor.enabled) return;
    if (speed_pct > 1.0f) speed_pct = 1.0f;
    if (speed_pct < -1.0f) speed_pct = -1.0f;

#ifdef MOCK_MODE
    mock_motor_set_speed(speed_pct);
#else
    /* Set direction */
    GPIO_PinState dir = (speed_pct >= 0) ? GPIO_PIN_SET : GPIO_PIN_RESET;
    HAL_GPIO_WritePin(MOTOR_DIR_PORT, MOTOR_DIR_PIN, dir);

    /* Set PWM duty */
    uint32_t duty = (uint32_t)(fabsf(speed_pct) * 999);
    __HAL_TIM_SET_COMPARE(TIM2, MOTOR_PWM_CHANNEL, duty);
#endif
}

void motor_stop(void) {
    motor_set_speed(0.0f);
}

void motor_enable(void) {
    g_motor.enabled = true;
#ifdef MOCK_MODE
    printf("[MOCK] Motor enabled\n");
#else
    HAL_GPIO_WritePin(MOTOR_ENABLE_PORT, MOTOR_ENABLE_PIN, GPIO_PIN_SET);
#endif
}

void motor_disable(void) {
    motor_set_speed(0.0f);
    g_motor.enabled = false;
#ifdef MOCK_MODE
    printf("[MOCK] Motor disabled\n");
#else
    HAL_GPIO_WritePin(MOTOR_ENABLE_PORT, MOTOR_ENABLE_PIN, GPIO_PIN_RESET);
#endif
}

MotorState motor_get_state(void) {
#ifdef MOCK_MODE
    g_motor.current_speed_rpm = mock_motor_get_speed();
    g_motor.current_a = mock_motor_get_current();
#else
    /* Read current from ADC */
    HAL_ADC_Start(&hadc1);
    if (HAL_ADC_PollForConversion(&hadc1, 10) == HAL_OK) {
        uint32_t adc = HAL_ADC_GetValue(&hadc1);
        /* Current sense: 0.1 V/A, 3.3V Vref, 12-bit ADC */
        g_motor.current_a = (adc * 3.3f / 4095.0f) / 0.1f;
    }
#endif
    return g_motor;
}

void motor_mock_update(float dt) {
#ifdef MOCK_MODE
    mock_motor_update(dt);
#endif
}

#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H

#ifdef MOCK_MODE
/* Mock mode: no real hardware */
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#else
#include "stm32f4xx_hal.h"
#endif

/* Control loop */
#define CONTROL_LOOP_HZ         100
#define CONTROL_LOOP_PERIOD_MS  10

/* Serial */
#define SERIAL_BAUD             115200

/* Winch parameters */
#define WINCH_MAX_SPEED_MM_S    500.0f
#define WINCH_MAX_TRAVEL_MM     5000.0f
#define WINCH_ENCODER_TICKS_MM  100

/* Motor */
#define MOTOR_PWM_FREQ_HZ       20000
#define MOTOR_CURRENT_LIMIT_A   15.0f
#define MOTOR_PWM_CHANNEL       TIM_CHANNEL_1
#define MOTOR_DIR_PIN           GPIO_PIN_4
#define MOTOR_DIR_PORT          GPIOA
#define MOTOR_ENABLE_PIN        GPIO_PIN_5
#define MOTOR_ENABLE_PORT       GPIOA

/* Current sense ADC */
#define MOTOR_CURRENT_ADC       ADC1
#define MOTOR_CURRENT_CHANNEL   ADC_CHANNEL_0

/* Limit switch pins */
#define LIMIT_TOP_PIN           GPIO_PIN_0
#define LIMIT_TOP_PORT          GPIOB
#define LIMIT_BOTTOM_PIN        GPIO_PIN_1
#define LIMIT_BOTTOM_PORT       GPIOB

/* Emergency stop pin */
#define ESTOP_PIN               GPIO_PIN_10
#define ESTOP_PORT              GPIOB
#define ESTOP_ACTIVE_LOW        1

/* Safety */
#define MAX_SPEED_OVERRIDE_MM_S 200.0f
#define AUTO_STOP_ON_LIMIT      1
#define AUTO_STOP_ON_ESTOP     1

#endif /* BOARD_CONFIG_H */

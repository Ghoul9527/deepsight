/* STM32F4xx HAL Configuration stub — mock mode.
 * In real builds, use the STM32CubeF4-generated configuration.
 */
#ifndef STM32F4XX_HAL_CONF_H
#define STM32F4XX_HAL_CONF_H

#ifdef MOCK_MODE
/* No HAL in mock mode */
#else
#include "stm32f4xx_hal.h"

#define HSE_VALUE 8000000U
#define HSI_VALUE 16000000U
#define LSE_VALUE 32768U
#define LSI_VALUE 32000U

#define HAL_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_UART_MODULE_ENABLED
#define HAL_TIM_MODULE_ENABLED
#endif

#endif /* STM32F4XX_HAL_CONF_H */

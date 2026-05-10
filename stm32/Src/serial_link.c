#include "serial_link.h"
#include <string.h>

/* ── Mock-mode globals ── */
static char g_mock_input[256] = {0};
static bool g_mock_has_data = false;

#ifndef MOCK_MODE
/* ── Real UART state ── */
static UART_HandleTypeDef g_uart;
static char g_rx_buf[256];
static volatile uint8_t g_rx_idx = 0;
static volatile bool g_rx_complete = false;
#endif

void serial_init(void) {
#ifdef MOCK_MODE
    printf("[MOCK] Serial initialized\n");
#else
    /* UART1 on PA9 (TX) / PA10 (RX) */
    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef gpio = {0};
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART1;

    gpio.Pin = GPIO_PIN_9;  /* TX */
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin = GPIO_PIN_10; /* RX */
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &gpio);

    g_uart.Instance = USART1;
    g_uart.Init.BaudRate = SERIAL_BAUD;
    g_uart.Init.WordLength = UART_WORDLENGTH_8B;
    g_uart.Init.StopBits = UART_STOPBITS_1;
    g_uart.Init.Parity = UART_PARITY_NONE;
    g_uart.Init.Mode = UART_MODE_TX_RX;
    g_uart.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&g_uart);

    /* Start interrupt-based RX */
    g_rx_idx = 0;
    g_rx_complete = false;
    HAL_UART_Receive_IT(&g_uart, (uint8_t *)g_rx_buf, 1);
#endif
}

bool serial_available(void) {
#ifdef MOCK_MODE
    return g_mock_has_data;
#else
    return g_rx_complete;
#endif
}

char serial_read_char(void) {
#ifdef MOCK_MODE
    if (!g_mock_has_data) return 0;
    return g_mock_input[0];
#else
    /* Not used with line-based read */
    return 0;
#endif
}

void serial_read_line(SerialLink *link) {
    memset(link->buffer, 0, sizeof(link->buffer));
    link->len = 0;

#ifdef MOCK_MODE
    if (g_mock_has_data) {
        strncpy(link->buffer, g_mock_input, sizeof(link->buffer) - 1);
        link->len = strlen(link->buffer);
        g_mock_has_data = false;
    }
#else
    if (g_rx_complete) {
        strncpy(link->buffer, g_rx_buf, sizeof(link->buffer) - 1);
        link->len = g_rx_idx;
        /* Restart RX */
        g_rx_idx = 0;
        g_rx_complete = false;
        HAL_UART_Receive_IT(&g_uart, (uint8_t *)g_rx_buf, 1);
    }
#endif
}

void serial_write(const char *data) {
#ifdef MOCK_MODE
    printf("[MOCK→Pi] %s\n", data);
#else
    HAL_UART_Transmit(&g_uart, (uint8_t *)data, strlen(data), 100);
#endif
}

void serial_write_line(const char *data) {
    char buf[512];
    int n = snprintf(buf, sizeof(buf), "%s\n", data);
    if (n >= (int)sizeof(buf)) n = sizeof(buf) - 1;
#ifdef MOCK_MODE
    printf("[MOCK→Pi] %s\n", buf);
#else
    HAL_UART_Transmit(&g_uart, (uint8_t *)buf, n, 100);
#endif
}

void serial_mock_inject(const char *line) {
#ifdef MOCK_MODE
    strncpy(g_mock_input, line, sizeof(g_mock_input) - 1);
    g_mock_has_data = true;
#endif
}

#ifndef MOCK_MODE
/* UART RX interrupt callback — fills line buffer byte by byte */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance != USART1) return;

    char c = g_rx_buf[g_rx_idx];
    if (c == '\n' || g_rx_idx >= sizeof(g_rx_buf) - 1) {
        g_rx_buf[g_rx_idx] = '\0';
        g_rx_complete = true;
    } else {
        g_rx_idx++;
    }

    /* Continue receiving next byte if not complete */
    if (!g_rx_complete) {
        HAL_UART_Receive_IT(&g_uart, (uint8_t *)&g_rx_buf[g_rx_idx], 1);
    }
}
#endif

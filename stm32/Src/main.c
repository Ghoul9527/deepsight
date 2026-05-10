#include "board_config.h"
#include "winch_fsm.h"
#include "motor_ctrl.h"
#include "limit_switches.h"
#include "e_stop.h"
#include "serial_link.h"
#include "command_parser.h"
#include "safety.h"

#include <stdio.h>

#ifdef MOCK_MODE
#include <unistd.h>  /* usleep */
#define HAL_Delay(ms) usleep((ms) * 1000)
#endif

static WinchFSM g_winch;
static SafetyModule g_safety;
static float g_elapsed_s = 0.0f;

static void process_command(const char *line) {
    ParsedCommand cmd;
    if (!command_parse(line, &cmd)) return;

    safety_notify_command(&g_safety, g_elapsed_s);

    if (strcmp(cmd.type, "cmd.winch.set") == 0) {
        float speed = cmd.speed;
        /* Map -1..1 to mm/s */
        speed *= WINCH_MAX_SPEED_MM_S;
        winch_fsm_set_speed(&g_winch, speed);
        printf("[CMD] Winch speed: %.1f mm/s\n", speed);
    }
    else if (strcmp(cmd.type, "cmd.winch.stop") == 0) {
        winch_fsm_stop(&g_winch);
        printf("[CMD] Winch stop\n");
    }
    else if (strcmp(cmd.type, "sys.safety") == 0) {
        if (strstr(line, "emergency")) {
            estop_trigger_command();
            winch_fsm_emergency_stop(&g_winch);
            printf("[SAFETY] Emergency stop triggered\n");
        }
    }
    else if (strcmp(cmd.type, "sys.heartbeat") == 0) {
        /* No action needed */
    }
}

static void send_telemetry(void) {
    LimitState limits = limit_switches_read();
    EStopState estop = estop_read();
    MotorState motor = motor_get_state();

    char buf[512];
    snprintf(buf, sizeof(buf),
        "{\"msg_id\":\"%d\",\"timestamp_ns\":%lld,"
        "\"node_id\":\"stm32\",\"type\":\"tel.winch_state\","
        "\"payload\":{"
        "\"position_mm\":%.1f,\"speed_mm_s\":%.1f,"
        "\"limit_top\":%s,\"limit_bottom\":%s,"
        "\"e_stop_active\":%s,\"motor_current_a\":%.2f}}",
        (int)g_elapsed_s,
        (long long)(g_elapsed_s * 1e9),
        g_winch.position_mm, g_winch.speed_mm_s,
        limits.top_triggered ? "true" : "false",
        limits.bottom_triggered ? "true" : "false",
        estop != ESTOP_INACTIVE ? "true" : "false",
        motor.current_a
    );
    serial_write_line(buf);
}

static void send_heartbeat(void) {
    char buf[256];
    snprintf(buf, sizeof(buf),
        "{\"msg_id\":\"hb\",\"timestamp_ns\":%lld,"
        "\"node_id\":\"stm32\",\"type\":\"sys.heartbeat\","
        "\"payload\":{}}",
        (long long)(g_elapsed_s * 1e9)
    );
    serial_write_line(buf);
}

#ifndef MOCK_MODE
static void SystemClock_Config(void) {
    /* Configure HSE/PLL for 168 MHz (STM32F4).
     * Override in your board-specific file for exact crystal frequency.
     */
    RCC_OscInitTypeDef osc = {0};
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 8;
    osc.PLL.PLLN = 336;
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = 7;
    HAL_RCC_OscConfig(&osc);

    RCC_ClkInitTypeDef clk = {0};
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                  | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV4;
    clk.APB2CLKDivider = RCC_HCLK_DIV2;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5);
}
#endif

#ifdef MOCK_MODE
int main(void) {
#else
int main(void) {
    HAL_Init();
    SystemClock_Config();
#endif
    printf("\n=== STM32 Winch Controller ===\n");

    /* Initialize subsystems */
    serial_init();
    winch_fsm_init(&g_winch);
    motor_init();
    motor_enable();
    limit_switches_init();
    estop_init();
    safety_init(&g_safety);

    printf("State: %s | Position: %.1f mm\n", winch_state_name(g_winch.state), g_winch.position_mm);

    /* Main control loop @ 100 Hz */
    uint32_t tick = 0;
    while (1) {
        g_elapsed_s = tick * (1.0f / CONTROL_LOOP_HZ);

        /* Read serial commands */
        if (serial_available()) {
            SerialLink link;
            serial_read_line(&link);
            if (link.len > 0) {
                process_command(link.buffer);
            }
        }

        /* Update subsystems */
        LimitState limits = limit_switches_read();
        EStopState estop = estop_read();

#ifdef MOCK_MODE
        /* Simulate limit switches from winch position */
        limit_switches_mock_set(
            g_winch.position_mm <= 0.0f,
            g_winch.position_mm >= WINCH_MAX_TRAVEL_MM
        );
#endif

        /* Safety check */
        safety_check(&g_safety, &g_winch, limits, estop, g_elapsed_s);

        /* Update winch */
        winch_fsm_update(&g_winch, 1.0f / CONTROL_LOOP_HZ);

        /* Update motor simulation */
#ifdef MOCK_MODE
        motor_mock_update(1.0f / CONTROL_LOOP_HZ);
#endif

        /* Telemetry (every 100ms = 10 Hz) */
        if (tick % 10 == 0) {
            send_telemetry();
        }

        /* Heartbeat (every 500ms = 2 Hz) */
        if (tick % 50 == 0) {
            send_heartbeat();
        }

        tick++;
        HAL_Delay(CONTROL_LOOP_PERIOD_MS);
    }

    return 0;
}

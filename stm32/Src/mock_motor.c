#include "mock_motor.h"
#include <math.h>

static float g_mock_speed = 0.0f;
static float g_mock_target = 0.0f;
static float g_mock_current = 0.0f;

void mock_motor_init(void) {
    g_mock_speed = 0.0f;
    g_mock_target = 0.0f;
    g_mock_current = 0.0f;
}

void mock_motor_set_speed(float speed_pct) {
    g_mock_target = speed_pct * 3000.0f;  /* Max 3000 RPM */
}

float mock_motor_get_speed(void) {
    return g_mock_speed;
}

float mock_motor_get_current(void) {
    return g_mock_current;
}

void mock_motor_update(float dt) {
    /* Simulate motor ramp */
    float error = g_mock_target - g_mock_speed;
    g_mock_speed += error * dt * 10.0f;  /* 10 Hz motor response */
    /* Current proportional to speed + load (simulated) */
    g_mock_current = fabs(g_mock_speed) * 0.003f + 0.5f;
}

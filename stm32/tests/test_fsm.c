/* Unit tests for STM32 Winch Controller — compile with MOCK_MODE=1 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>

#include "../Src/winch_fsm.h"
#include "../Src/command_parser.h"
#include "../Src/safety.h"
#include "../Src/e_stop.h"

static int tests_run = 0;
static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) static void name(void)
#define RUN_TEST(name) do { \
    tests_run++; \
    printf("  %s ... ", #name); \
    name(); \
    tests_passed++; \
    printf("PASSED\n"); \
} while(0)

#define ASSERT_EQ(a, b) do { \
    if ((a) != (b)) { \
        printf("FAILED\n    ASSERT_EQ(%s, %s): %d != %d\n", #a, #b, (int)(a), (int)(b)); \
        tests_failed++; tests_passed--; return; \
    } \
} while(0)

#define ASSERT_FLOAT_EQ(a, b, eps) do { \
    if (fabs((a) - (b)) > (eps)) { \
        printf("FAILED\n    ASSERT_FLOAT_EQ: %f != %f (eps=%f)\n", (double)(a), (double)(b), (double)(eps)); \
        tests_failed++; tests_passed--; return; \
    } \
} while(0)

#define ASSERT_TRUE(cond) do { \
    if (!(cond)) { \
        printf("FAILED\n    ASSERT_TRUE(%s) is false\n", #cond); \
        tests_failed++; tests_passed--; return; \
    } \
} while(0)

#define ASSERT_FALSE(cond) ASSERT_TRUE(!(cond))

/* ── Winch FSM Tests ─────────────────────────────────── */

TEST(test_fsm_init) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    ASSERT_EQ(fsm.state, WINCH_IDLE);
    ASSERT_FLOAT_EQ(fsm.speed_mm_s, 0.0f, 0.01f);
    ASSERT_FLOAT_EQ(fsm.position_mm, 2500.0f, 0.01f);
}

TEST(test_fsm_set_speed_up) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    ASSERT_EQ(fsm.state, WINCH_MOVING_UP);
    ASSERT_FLOAT_EQ(fsm.target_speed, 100.0f, 0.01f);
}

TEST(test_fsm_set_speed_down) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, -200.0f);
    ASSERT_EQ(fsm.state, WINCH_MOVING_DOWN);
}

TEST(test_fsm_set_speed_zero_idles) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    winch_fsm_set_speed(&fsm, 0.0f);
    ASSERT_EQ(fsm.state, WINCH_IDLE);
}

TEST(test_fsm_speed_clamping) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 999.0f);
    ASSERT_FLOAT_EQ(fsm.target_speed, WINCH_MAX_SPEED_MM_S, 0.01f);
    winch_fsm_set_speed(&fsm, -999.0f);
    ASSERT_FLOAT_EQ(fsm.target_speed, -WINCH_MAX_SPEED_MM_S, 0.01f);
}

TEST(test_fsm_update_moves_position) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    float pos_before = fsm.position_mm;
    winch_fsm_update(&fsm, 0.1f);
    ASSERT_TRUE(fsm.position_mm > pos_before);
}

TEST(test_fsm_emergency_stop) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    winch_fsm_emergency_stop(&fsm);
    ASSERT_EQ(fsm.state, WINCH_ESTOP);
    ASSERT_FLOAT_EQ(fsm.speed_mm_s, 0.0f, 0.01f);
}

TEST(test_fsm_estop_blocks_commands) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_emergency_stop(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    ASSERT_EQ(fsm.state, WINCH_ESTOP);
    ASSERT_FLOAT_EQ(fsm.target_speed, 0.0f, 0.01f);
}

TEST(test_fsm_position_bounds) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    /* Must be in a moving state for position clamping to apply */
    winch_fsm_set_speed(&fsm, -100.0f);
    fsm.position_mm = -10.0f;
    winch_fsm_update(&fsm, 0.1f);
    ASSERT_TRUE(fsm.position_mm >= 0.0f);

    winch_fsm_set_speed(&fsm, 100.0f);
    fsm.position_mm = WINCH_MAX_TRAVEL_MM + 100.0f;
    winch_fsm_update(&fsm, 0.1f);
    ASSERT_TRUE(fsm.position_mm <= WINCH_MAX_TRAVEL_MM);
}

TEST(test_fsm_stop_transitions) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);
    winch_fsm_stop(&fsm);
    ASSERT_EQ(fsm.state, WINCH_STOPPING);
    /* After update, speed should ramp toward 0 */
    winch_fsm_update(&fsm, 1.0f);
    ASSERT_TRUE(fsm.speed_mm_s < 100.0f);
}

TEST(test_fsm_encoder) {
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_encoder(&fsm, 350000);
    ASSERT_EQ(fsm.encoder_ticks, 350000);
    ASSERT_FLOAT_EQ(fsm.position_mm, 3500.0f, 0.1f);
}

TEST(test_winch_state_names) {
    ASSERT_EQ(strcmp(winch_state_name(WINCH_IDLE), "IDLE"), 0);
    ASSERT_EQ(strcmp(winch_state_name(WINCH_MOVING_UP), "MOVING_UP"), 0);
    ASSERT_EQ(strcmp(winch_state_name(WINCH_MOVING_DOWN), "MOVING_DOWN"), 0);
    ASSERT_EQ(strcmp(winch_state_name(WINCH_STOPPING), "STOPPING"), 0);
    ASSERT_EQ(strcmp(winch_state_name(WINCH_ESTOP), "ESTOP"), 0);
    ASSERT_EQ(strcmp(winch_state_name(WINCH_ERROR), "ERROR"), 0);
}

/* ── Command Parser Tests ────────────────────────────── */

TEST(test_parse_winch_set) {
    ParsedCommand cmd;
    bool ok = command_parse("{\"type\":\"cmd.winch.set\",\"payload\":{\"speed\":150,\"direction\":\"up\"}}", &cmd);
    ASSERT_TRUE(ok);
    ASSERT_EQ(strcmp(cmd.type, "cmd.winch.set"), 0);
    ASSERT_FLOAT_EQ(cmd.speed, 150.0f, 0.01f);
}

TEST(test_parse_winch_stop) {
    ParsedCommand cmd;
    bool ok = command_parse("{\"type\":\"cmd.winch.stop\"}", &cmd);
    ASSERT_TRUE(ok);
    ASSERT_EQ(strcmp(cmd.type, "cmd.winch.stop"), 0);
}

TEST(test_parse_invalid_json) {
    ParsedCommand cmd;
    bool ok = command_parse("not json!", &cmd);
    ASSERT_FALSE(ok);
}

TEST(test_parse_null_input) {
    bool ok = command_parse(NULL, NULL);
    ASSERT_FALSE(ok);
}

/* ── Safety Module Tests ─────────────────────────────── */

TEST(test_safety_init) {
    SafetyModule s;
    safety_init(&s);
    ASSERT_FALSE(s.auto_stop_active);
}

TEST(test_safety_command_timeout) {
    SafetyModule s;
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);

    safety_init(&s);
    safety_notify_command(&s, 0.0f);

    LimitState limits = {false, false};
    safety_check(&s, &fsm, limits, ESTOP_INACTIVE, 2.0f);
    ASSERT_TRUE(s.auto_stop_active);
}

TEST(test_safety_command_resets_timer) {
    SafetyModule s;
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);

    safety_init(&s);
    safety_notify_command(&s, 0.0f);
    safety_notify_command(&s, 0.5f);
    safety_check(&s, &fsm, (LimitState){false, false}, ESTOP_INACTIVE, 1.2f);
    ASSERT_FALSE(s.auto_stop_active);
}

TEST(test_safety_estop_immediate) {
    SafetyModule s;
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);

    safety_init(&s);
    safety_check(&s, &fsm, (LimitState){false, false}, ESTOP_ACTIVE_HARDWARE, 0.1f);
    ASSERT_EQ(fsm.state, WINCH_ESTOP);
}

TEST(test_safety_limit_top_stops_up) {
    SafetyModule s;
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, 100.0f);  /* Moving up */

    safety_init(&s);
    safety_notify_command(&s, 0.0f);
    LimitState limits = {true, false};  /* Top limit triggered */
    safety_check(&s, &fsm, limits, ESTOP_INACTIVE, 0.1f);
    ASSERT_EQ(fsm.state, WINCH_STOPPING);
}

TEST(test_safety_limit_bottom_stops_down) {
    SafetyModule s;
    WinchFSM fsm;
    winch_fsm_init(&fsm);
    winch_fsm_set_speed(&fsm, -100.0f);  /* Moving down */

    safety_init(&s);
    safety_notify_command(&s, 0.0f);
    LimitState limits = {false, true};  /* Bottom limit triggered */
    safety_check(&s, &fsm, limits, ESTOP_INACTIVE, 0.1f);
    ASSERT_EQ(fsm.state, WINCH_STOPPING);
}

int main(void) {
    printf("\n=== STM32 Winch Controller Unit Tests ===\n\n");

    printf("Winch FSM:\n");
    RUN_TEST(test_fsm_init);
    RUN_TEST(test_fsm_set_speed_up);
    RUN_TEST(test_fsm_set_speed_down);
    RUN_TEST(test_fsm_set_speed_zero_idles);
    RUN_TEST(test_fsm_speed_clamping);
    RUN_TEST(test_fsm_update_moves_position);
    RUN_TEST(test_fsm_emergency_stop);
    RUN_TEST(test_fsm_estop_blocks_commands);
    RUN_TEST(test_fsm_position_bounds);
    RUN_TEST(test_fsm_stop_transitions);
    RUN_TEST(test_fsm_encoder);
    RUN_TEST(test_winch_state_names);

    printf("\nCommand Parser:\n");
    RUN_TEST(test_parse_winch_set);
    RUN_TEST(test_parse_winch_stop);
    RUN_TEST(test_parse_invalid_json);
    RUN_TEST(test_parse_null_input);

    printf("\nSafety Module:\n");
    RUN_TEST(test_safety_init);
    RUN_TEST(test_safety_command_timeout);
    RUN_TEST(test_safety_command_resets_timer);
    RUN_TEST(test_safety_estop_immediate);
    RUN_TEST(test_safety_limit_top_stops_up);
    RUN_TEST(test_safety_limit_bottom_stops_down);

    printf("\n=== Results: %d/%d passed, %d failed ===\n",
           tests_passed, tests_run, tests_failed);

    return tests_failed > 0 ? 1 : 0;
}

#ifndef M6_DECISION_H
#define M6_DECISION_H

/**
 * @file m6_decision.h
 * @brief Current public design notes for M6 Decision Engine
 *
 * Important: the live Python module is still a placeholder.
 * This header describes the intended direction after the navigation redesign:
 * M6 should orchestrate sensor fusion, static-route navigation, and alarm flow.
 */

#include <stdint.h>
#include <stdbool.h>

#define M6_FUSION_ALARM_THRESH   0.7f
#define M6_FUSION_CLEAR_THRESH   0.4f
#define M6_VISION_CONF_THRESH    0.5f
#define M6_SENSOR_POLL_MS        500
#define M6_W_VISION              0.5f
#define M6_W_SMOKE               0.3f
#define M6_W_IR                  0.2f
#define M6_BATTERY_LOW_V         6.8f

typedef enum {
    M6_OK                  =  0,
    M6_ERR_INIT            = -1,
    M6_ERR_INVALID         = -2,
    M6_ERR_NOT_IMPLEMENTED = -3
} m6_status_t;

typedef enum {
    M6_STATE_INIT      = 0,
    M6_STATE_NAVIGATE  = 1,
    M6_STATE_VERIFY    = 2,
    M6_STATE_ALARM     = 3,
    M6_STATE_STOP      = 4
} m6_fsm_state_t;

typedef struct {
    float fusion_score;
    double timestamp;
    char snapshot_label[64];
} m6_alarm_event_t;

m6_status_t m6_init(void);
m6_status_t m6_run(void);
m6_status_t m6_stop(void);
m6_status_t m6_get_state(m6_fsm_state_t *state_out);

#endif /* M6_DECISION_H */

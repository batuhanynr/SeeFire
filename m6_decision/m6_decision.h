#ifndef M6_DECISION_H
#define M6_DECISION_H

/**
 * @file m6_decision.h
 * @brief Decision Engine (FSM) - public interface
 * @author Emre Can Tuncer (200104004115), Semih Sarkoca (220104004038), Ahmet Furkan Arslan (220104004044), Halil Buğra Şen (230104004088)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: FSM states, fusion score, alarm control
 */

#include <stdint.h>
#include <stdbool.h>
#include "m3_sensors.h"
#include "m4_vision.h"
#include "m5_navigation.h"

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M6_FUSION_ALARM_THRESH   0.7f   /**< Fusion score to enter ALARM state */
#define M6_FUSION_CLEAR_THRESH   0.4f   /**< Fusion score below which FALSE_ALARM is logged */
#define M6_VISION_CONF_THRESH    0.5f   /**< YOLO confidence to enter VERIFY state */
#define M6_SENSOR_POLL_MS        500    /**< M3 fusion sensor poll interval (ms) */
#define M6_W_VISION              0.5f   /**< Fusion weight: YOLO confidence */
#define M6_W_SMOKE               0.3f   /**< Fusion weight: smoke sensor */
#define M6_W_IR                  0.2f   /**< Fusion weight: IR temperature */
#define M6_BATTERY_LOW_V         7.2f   /**< Battery voltage for low-battery warning */

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M6 functions */
typedef enum {
    M6_OK           =  0,   /**< Success */
    M6_ERR_INIT     = -1,   /**< Module dependency not ready */
    M6_ERR_INVALID  = -2    /**< Invalid parameter or NULL pointer */
} m6_status_t;

/** @brief Discrete states of the SeeFire finite-state machine */
typedef enum {
    M6_STATE_INIT    = 0,   /**< System startup; resolving map availability */
    M6_STATE_EXPLORE = 1,   /**< Wall-following exploration; building map */
    M6_STATE_PATROL  = 2,   /**< Looping through saved waypoints */
    M6_STATE_VERIFY  = 3,   /**< Approaching suspicious location for confirmation */
    M6_STATE_ALARM   = 4    /**< Fire confirmed; LED + buzzer active */
} m6_fsm_state_t;

/** @brief Alarm event record passed to M7 and M2 when alarm fires */
typedef struct {
    m6_fsm_state_t  prev_state;       /**< State before entering ALARM */
    float           fusion_score;     /**< Score that triggered the alarm (0.0–1.0) */
    float           pos_x;            /**< Estimated robot X position (m) */
    float           pos_y;            /**< Estimated robot Y position (m) */
    double          timestamp;        /**< Unix epoch at moment of alarm */
    uint8_t        *snapshot_jpeg;    /**< Pointer to JPEG buffer from M4 */
    uint32_t        snapshot_size;    /**< Size of snapshot_jpeg in bytes */
} m6_alarm_event_t;

/* ── Decision Engine API ────────────────────────────────────────────────── */

/**
 * @brief Initialise the Decision Engine with references to all dependent modules.
 *        Sets FSM to M6_STATE_INIT.
 * @return M6_OK on success, M6_ERR_INIT if any dependency is NULL.
 */
m6_status_t m6_init(void);

/**
 * @brief Start the FSM main loop. Blocks until KeyboardInterrupt / m6_stop().
 *        Internally polls M3 every ~500 ms and M4/M5 on every iteration.
 * @return M6_OK when loop exits cleanly.
 */
m6_status_t m6_run(void);

/**
 * @brief Signal the FSM loop to stop after the current iteration.
 * @return M6_OK always.
 */
m6_status_t m6_stop(void);

/**
 * @brief Retrieve the current FSM state.
 * @param state_out  Pointer to m6_fsm_state_t to receive current state.
 * @return M6_OK on success, M6_ERR_INVALID if state_out is NULL.
 */
m6_status_t m6_get_state(m6_fsm_state_t *state_out);

/**
 * @brief Calculate a 0.0–1.0 threat fusion score from vision and sensor inputs.
 *        Formula: (W_VISION × vision_conf) + (W_SMOKE × smoke_score)
 *                 + (W_IR × ir_score)
 *        Where smoke_score = smoke_level/1023 and
 *              ir_score = clamp((ir_temp - 40) / 60, 0, 1).
 * @param vision   Pointer to the latest M4 vision result.
 * @param sensors  Pointer to the latest M3 fusion sensor reading.
 * @param score_out  Pointer to float receiving the computed score.
 * @return M6_OK on success, M6_ERR_INVALID if any pointer is NULL.
 */
m6_status_t m6_calculate_fusion_score(const m4_vision_result_t *vision,
                                       const m3_fusion_data_t   *sensors,
                                       float                    *score_out);

/**
 * @brief Transition to ALARM state: activate LED/buzzer via M2,
 *        save JPEG snapshot via M4, and log event via M7.
 * @param event  Populated alarm event struct.
 * @return M6_OK on success, M6_ERR_INVALID if event is NULL.
 */
m6_status_t m6_trigger_alarm(const m6_alarm_event_t *event);

/**
 * @brief Deactivate alarm and return FSM to previous state (EXPLORE or PATROL).
 *        Called on manual reset or configurable timeout.
 * @return M6_OK on success.
 */
m6_status_t m6_reset_alarm(void);

#endif /* M6_DECISION_H */

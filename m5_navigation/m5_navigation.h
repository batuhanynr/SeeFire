#ifndef M5_NAVIGATION_H
#define M5_NAVIGATION_H

/**
 * @file m5_navigation.h
 * @brief Current public design notes for M5 Navigation
 *
 * Mirrors the current Python implementation:
 * - static, pre-drawn route
 * - south-to-north sector traversal
 * - start-position verification
 * - obstacle bypass with encoder-backed return
 *
 * M5 no longer performs exploration or occupancy-grid generation.
 */

#include <stdint.h>
#include <stdbool.h>

#define M5_STEP_DISTANCE_CM        5.0f
#define M5_SIDE_STEP_CM            5.0f
#define M5_OBSTACLE_THRESHOLD_CM   20.0f
#define M5_OBSTACLE_CLEAR_CM       40.0f
#define M5_START_LEFT_CM           30.0f
#define M5_START_RIGHT_CM          30.0f
#define M5_POSITION_TOLERANCE_CM   5.0f
#define M5_FINE_TUNE_STEP_CM       2.0f

typedef enum {
    M5_OK               =  0,
    M5_ERR_MOTOR        = -1,
    M5_ERR_SENSOR       = -2,
    M5_ERR_INVALID      = -3,
    M5_ERR_START_POSE   = -4,
    M5_ERR_STUCK        = -5
} m5_status_t;

typedef struct {
    float target_north_cm;
    uint16_t sector_id;
} m5_waypoint_t;

typedef struct {
    float left_cm;
    float front_cm;
    float right_cm;
} m5_nav_reading_t;

typedef struct {
    uint16_t current_sector;
    float current_north_cm;
    float target_north_cm;
    bool midpoint_triggered;
    bool obstacle_active;
} m5_nav_status_t;

m5_status_t m5_verify_start_position(void);
m5_status_t m5_run_navigation(const m5_waypoint_t *waypoints, uint16_t count);
m5_status_t m5_handle_obstacle(uint16_t sector_id);
m5_status_t m5_stop_navigation(void);

#endif /* M5_NAVIGATION_H */

#ifndef M5_NAVIGATION_H
#define M5_NAVIGATION_H

/**
 * @file m5_navigation.h
 * @brief Navigation & Mapping - public interface
 * @author Ahmet Furkan Arslan (220104004044), Yusuf Alperen Celik (220104004064)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: NavCommand, occupancy grid, execute_command
 */

#include <stdint.h>
#include <stdbool.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M5_GRID_RESOLUTION_M    0.10f   /**< Occupancy grid cell size (metres) */
#define M5_GRID_WIDTH_CELLS     40      /**< Max grid width (4 m / 0.1 m) */
#define M5_GRID_HEIGHT_CELLS    40      /**< Max grid height (4 m / 0.1 m) */
#define M5_OBSTACLE_DIST_CM     20      /**< Stop distance for obstacle avoidance (cm) */
#define M5_WALL_FOLLOW_DIST_CM  30      /**< Target wall-following distance (cm) */
#define M5_NAV_LOOP_MS          100     /**< Navigation loop period (ms) */
#define M5_MAP_JSON_PATH        "/data/map.json" /**< Default map file path */

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M5 functions */
typedef enum {
    M5_OK               =  0,  /**< Success */
    M5_ERR_MOTOR        = -1,  /**< M2 motor API call failed */
    M5_ERR_SENSOR       = -2,  /**< M3 sensor read failed */
    M5_ERR_MAP          = -3,  /**< Map load/save failed */
    M5_ERR_INVALID      = -4,  /**< Invalid parameter or NULL pointer */
    M5_ERR_STUCK        = -5   /**< Robot is stuck; recovery in progress */
} m5_status_t;

/** @brief High-level navigation commands issued by M6 Decision Engine */
typedef enum {
    M5_CMD_EXPLORE      = 0,  /**< Wall-following exploration; builds occupancy map */
    M5_CMD_PATROL       = 1,  /**< Loop through saved waypoints */
    M5_CMD_VERIFY       = 2,  /**< Approach a suspicious heading for closer inspection */
    M5_CMD_STOP         = 3,  /**< Full stop; hold position */
    M5_CMD_RESUME       = 4   /**< Resume previous command after VERIFY/STOP */
} m5_nav_command_t;

/** @brief Navigation order passed to execute_command() */
typedef struct {
    m5_nav_command_t command;           /**< Command to execute */
    float            target_heading;    /**< VERIFY: desired yaw in degrees (0–360); ignored otherwise */
    uint8_t          speed_override;    /**< Optional speed (0–100); 0 = use default */
} m5_nav_order_t;

/** @brief Occupancy grid cell states */
typedef enum {
    M5_CELL_UNKNOWN   = 0,  /**< Not yet visited */
    M5_CELL_FREE      = 1,  /**< Confirmed passable */
    M5_CELL_OCCUPIED  = 2   /**< Obstacle detected */
} m5_cell_state_t;

/** @brief 2-D position in the robot's coordinate frame */
typedef struct {
    float x_m;   /**< X position in metres */
    float y_m;   /**< Y position in metres */
} m5_position_t;

/** @brief Navigation status snapshot polled by M6 Decision Engine */
typedef struct {
    char          state[16];           /**< "exploring" | "patrolling" | "verifying" | "stopped" */
    uint16_t      current_waypoint;    /**< Index of active waypoint */
    uint16_t      total_waypoints;     /**< Total waypoints in patrol route */
    bool          is_stuck;            /**< True if recovery behaviour is active */
    bool          exploration_complete;/**< True after full loop back to start */
    m5_position_t estimated_pos;       /**< Dead-reckoning position estimate */
} m5_nav_status_t;

/* ── Navigation API ─────────────────────────────────────────────────────── */

/**
 * @brief Initialise the navigation module; load saved map if available.
 *        Calls M7 load_map() internally.
 * @return M5_OK on success, M5_ERR_MAP if map file is corrupted.
 */
m5_status_t m5_init_navigation(void);

/**
 * @brief Issue a navigation command. The module runs a background loop
 *        at ~100 ms calling M3 sensors and M2 motor APIs.
 *        Called by M6 on every state transition.
 * @param order  Pointer to the navigation order to execute.
 * @return M5_OK on success, M5_ERR_INVALID if order is NULL.
 */
m5_status_t m5_execute_command(const m5_nav_order_t *order);

/**
 * @brief Retrieve a snapshot of the current navigation status.
 *        Called by M6 Decision Engine on every FSM iteration.
 * @param status_out  Pointer to caller-owned m5_nav_status_t struct.
 * @return M5_OK on success, M5_ERR_INVALID if status_out is NULL.
 */
m5_status_t m5_get_nav_status(m5_nav_status_t *status_out);

/**
 * @brief Feed the latest sensor data into the navigation control loop.
 *        Called internally by the navigation thread; exposed for testing.
 * @param ultrasonic_left_cm   Distance from left HC-SR04 (cm).
 * @param ultrasonic_right_cm  Distance from right HC-SR04 (cm).
 * @return M5_OK on success.
 */
m5_status_t m5_update_navigation(float ultrasonic_left_cm,
                                  float ultrasonic_right_cm);

/**
 * @brief Save the current occupancy grid to a JSON file.
 *        Called by M5 at end of exploration and periodically during patrol.
 * @param filepath  Destination path; NULL defaults to M5_MAP_JSON_PATH.
 * @return M5_OK on success, M5_ERR_MAP on file write failure.
 */
m5_status_t m5_save_map(const char *filepath);

/**
 * @brief Load an occupancy grid from a JSON file.
 *        Called by M5 at startup via M7 load_map().
 * @param filepath  Source path; NULL defaults to M5_MAP_JSON_PATH.
 * @return M5_OK on success, M5_ERR_MAP if file not found or invalid.
 */
m5_status_t m5_load_map(const char *filepath);

/**
 * @brief Stop the navigation thread and release resources.
 * @return M5_OK always.
 */
m5_status_t m5_cleanup(void);

#endif /* M5_NAVIGATION_H */

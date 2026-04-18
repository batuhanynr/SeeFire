#ifndef M7_LOGGING_H
#define M7_LOGGING_H

/**
 * @file m7_logging.h
 * @brief Data Logging & Output - public interface
 * @author Batuhan Yanar (220104004059), Yusuf Alperen Celik (220104004064)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: event logging, map persistence, snapshot save
 */

#include <stdint.h>
#include <stdbool.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M7_DB_PATH          "/data/seefire.db"      /**< Default SQLite DB path */
#define M7_MAP_PATH         "/data/map.json"         /**< Default map JSON path */
#define M7_SNAPSHOT_DIR     "/data/snapshots/"       /**< JPEG snapshot directory */
#define M7_EVENT_LIMIT_MAX  1000                     /**< Max events returned by get_events */

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M7 functions */
typedef enum {
    M7_OK            =  0,  /**< Success */
    M7_ERR_INIT      = -1,  /**< Database or directory initialisation failed */
    M7_ERR_WRITE     = -2,  /**< Write operation failed */
    M7_ERR_READ      = -3,  /**< Read or query failed */
    M7_ERR_INVALID   = -4   /**< NULL pointer or bad parameter */
} m7_status_t;

/** @brief Known event type identifiers stored in the SQLite database */
typedef enum {
    M7_EVT_STATE_CHANGE      = 0,  /**< FSM state transition */
    M7_EVT_FIRE_DETECTED     = 1,  /**< Alarm triggered */
    M7_EVT_FALSE_ALARM       = 2,  /**< Verify returned below clear threshold */
    M7_EVT_EXPLORATION_DONE  = 3,  /**< Full exploration loop completed */
    M7_EVT_PATROL_STARTED    = 4,  /**< Patrol phase began */
    M7_EVT_OBSTACLE_AVOIDED  = 5,  /**< Obstacle avoidance manoeuvre executed */
    M7_EVT_LOW_BATTERY       = 6,  /**< Battery below warning threshold */
    M7_EVT_SYSTEM_START      = 7,  /**< System initialisation complete */
    M7_EVT_SYSTEM_STOP       = 8   /**< Graceful shutdown */
} m7_event_type_t;

/**
 * @brief Event record written to SQLite and returned by get_events().
 */
typedef struct {
    int64_t         row_id;         /**< Auto-assigned primary key (0 before insert) */
    m7_event_type_t event_type;     /**< Event classification */
    double          timestamp;      /**< Unix epoch seconds */
    float           pos_x;         /**< Robot X position at event time (m) */
    float           pos_y;         /**< Robot Y position at event time (m) */
    float           confidence;    /**< Fusion threat score (0.0–1.0) */
    float           vision_conf;   /**< Raw YOLO confidence (0.0–1.0) */
    int32_t         smoke_level;   /**< MQ-2 ADC value at event time (0–1023) */
    float           ir_temp;       /**< MLX90614 surface temperature (°C) */
    char            snapshot_path[256]; /**< Absolute JPEG path; empty if no photo */
    char            details[512];  /**< Reserved JSON blob for future extension */
} m7_event_t;

/* ── Database API ───────────────────────────────────────────────────────── */

/**
 * @brief Initialise the SQLite database and create the events table if absent.
 *        Must be called before any other M7 function.
 * @return M7_OK on success, M7_ERR_INIT on failure.
 */
m7_status_t m7_init_database(void);

/**
 * @brief Insert an event record into the SQLite database.
 *        Called by M6 on every state change and alarm event.
 * @param event   Pointer to a populated m7_event_t (row_id is ignored on input).
 * @param row_id_out  Pointer to int64_t receiving the new auto-increment row ID.
 * @return M7_OK on success, M7_ERR_WRITE on failure, M7_ERR_INVALID if NULL.
 */
m7_status_t m7_log_event(const m7_event_t *event, int64_t *row_id_out);

/**
 * @brief Query the most recent events from the database.
 * @param event_type  Filter by type; pass -1 to return all event types.
 * @param limit       Maximum number of events to return (1–M7_EVENT_LIMIT_MAX).
 * @param events_out  Caller-owned array of m7_event_t to receive results.
 * @param count_out   Pointer to uint16_t; receives the number of results written.
 * @return M7_OK on success, M7_ERR_READ on query failure.
 */
m7_status_t m7_get_events(int32_t event_type, uint16_t limit,
                           m7_event_t *events_out, uint16_t *count_out);

/**
 * @brief Close the SQLite database connection gracefully.
 * @return M7_OK always.
 */
m7_status_t m7_close_database(void);

/* ── Map Persistence API ────────────────────────────────────────────────── */

/**
 * @brief Serialise the occupancy grid to a JSON file on the SD card.
 *        Called by M5 at end of exploration and periodically.
 * @param map_json  NULL-terminated JSON string representing the occupancy grid.
 * @param filepath  Destination path; NULL defaults to M7_MAP_PATH.
 * @return M7_OK on success, M7_ERR_WRITE on file write failure.
 */
m7_status_t m7_save_map(const char *map_json, const char *filepath);

/**
 * @brief Read the occupancy grid JSON from the SD card.
 *        Called by M5 at system startup.
 * @param buf       Caller-owned buffer to receive the JSON string.
 * @param buf_size  Size of buf in bytes.
 * @param filepath  Source path; NULL defaults to M7_MAP_PATH.
 * @return M7_OK on success, M7_ERR_READ if file not found or buf too small.
 */
m7_status_t m7_load_map(char *buf, uint32_t buf_size, const char *filepath);

/* ── Snapshot API ───────────────────────────────────────────────────────── */

/**
 * @brief Write a JPEG snapshot to the snapshots directory.
 *        Filename format: img_NNN.jpg where NNN is a zero-padded counter.
 * @param jpeg_data   Pointer to JPEG byte buffer from M4.
 * @param jpeg_size   Size of jpeg_data in bytes.
 * @param path_out    Caller-owned char buffer (≥256 bytes) receiving the absolute path.
 * @return M7_OK on success, M7_ERR_WRITE on failure.
 */
m7_status_t m7_save_snapshot(const uint8_t *jpeg_data, uint32_t jpeg_size,
                              char *path_out);

#endif /* M7_LOGGING_H */

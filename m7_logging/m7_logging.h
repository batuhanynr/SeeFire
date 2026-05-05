#ifndef M7_LOGGING_H
#define M7_LOGGING_H

/**
 * @file m7_logging.h
 * @brief Current public design notes for M7 Logging & Output
 *
 * Mirrors the current Python module at `m7_logging/logging.py`.
 */

#include <stdint.h>
#include <stdbool.h>

#define M7_DATA_DIR_ENV     "SEEFIRE_DATA_DIR"
#define M7_EVENT_LIMIT_MAX  1000

typedef enum {
    M7_OK            =  0,
    M7_ERR_INIT      = -1,
    M7_ERR_WRITE     = -2,
    M7_ERR_READ      = -3,
    M7_ERR_INVALID   = -4
} m7_status_t;

typedef struct {
    char timestamp[64];
    char event_type[32];
    float fusion_score;
    char sensor_data[512];
    char snapshot_path[256];
} m7_event_t;

m7_status_t m7_init(void);
m7_status_t m7_log_event(const m7_event_t *event, int64_t *row_id_out);
m7_status_t m7_get_events(const char *event_type, uint16_t limit);
m7_status_t m7_save_map(const char *map_json);
m7_status_t m7_load_map(char *buf, uint32_t buf_size);
m7_status_t m7_save_snapshot(const uint8_t *jpeg_data, uint32_t jpeg_size, int64_t event_id);

#endif /* M7_LOGGING_H */

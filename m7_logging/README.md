# M7_LOGGING — Data Logging & Output

One-sentence purpose: Provides SQLite event logging, JSON map persistence, and JPEG snapshot management on the Raspberry Pi SD card; has no module dependencies and should be initialised first.

**Author:** Batuhan Yanar (220104004059), Yusuf Alperen Çelik (220104004064)  
**Module ID:** M7  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| `sqlite3` (stdlib) | Python | Event database |
| `json`, `os`, `pathlib`, `time` (stdlib) | Python | File and timestamp management |
| MicroSD card (RPi default) | Hardware | Stores map.json, seefire.db, JPEG snapshots |

> M7 has **no module dependencies**. It should be initialised before M5 and M6.

---

## Quick-Start Integration Example

```c
#include "m7_logging.h"

int main(void) {
    // Must be called first — creates DB and snapshots directory
    if (m7_init_database() != M7_OK) {
        return -1;
    }

    // Log system start event
    m7_event_t evt = {
        .event_type = M7_EVT_SYSTEM_START,
        .timestamp  = 1743200000.0,  // time.time()
        .pos_x      = 0.0f,
        .pos_y      = 0.0f,
        .confidence = 0.0f
    };
    int64_t row_id = 0;
    m7_log_event(&evt, &row_id);

    // Save occupancy grid
    const char *map_json = "{\"cells\": []}";
    m7_save_map(map_json, NULL);  // NULL = default path

    // Load map at startup
    char buf[65536];
    m7_load_map(buf, sizeof(buf), NULL);

    // Save JPEG snapshot
    uint8_t jpeg[4096];  // example buffer
    char path_out[256];
    m7_save_snapshot(jpeg, sizeof(jpeg), path_out);

    m7_close_database();
    return 0;
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m7_init_database()` | — | `m7_status_t` | Creates DB and tables if absent |
| `m7_log_event(event, row_id_out)` | `const m7_event_t *`, `int64_t *` | `m7_status_t` | Called by M6 on every event |
| `m7_get_events(event_type, limit, events_out, count_out)` | `int32_t`, `uint16_t`, `m7_event_t *`, `uint16_t *` | `m7_status_t` | Pass -1 for all types |
| `m7_close_database()` | — | `m7_status_t` | Graceful SQLite shutdown |
| `m7_save_map(map_json, filepath)` | `const char *`, `const char *` | `m7_status_t` | NULL filepath = default |
| `m7_load_map(buf, buf_size, filepath)` | `char *`, `uint32_t`, `const char *` | `m7_status_t` | NULL filepath = default |
| `m7_save_snapshot(jpeg_data, jpeg_size, path_out)` | `const uint8_t *`, `uint32_t`, `char *` | `m7_status_t` | Auto-numbered img_NNN.jpg |

---

## Known Limitations & TODOs

- SQLite WAL mode is not yet enabled; concurrent writes from M5 (map) and M6 (events) may cause brief locking.
- SD card wear levelling is not considered; high-frequency logging (every 500 ms) may reduce card lifespan over very long deployments.
- The `details` JSON blob field in `m7_event_t` is reserved but not yet used by any module.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: event logging, map persistence, snapshot save |

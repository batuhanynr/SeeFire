# M5_NAVIGATION — Navigation & Mapping

One-sentence purpose: Implements wall-following exploration, occupancy grid mapping, waypoint patrol, and obstacle avoidance by consuming M3 sensor data and issuing M2 motor commands.

**Author:** Ahmet Furkan Arslan (220104004044), Yusuf Alperen Çelik (220104004064)  
**Module ID:** M5  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| M2 `m2_motor_drive()` API | Module | Navigation calls motor API |
| M3 `m3_get_navigation_sensors()` API | Module | Wall-following needs ultrasonic sensors |
| M7 `m7_save_map()` / `m7_load_map()` API | Module | Map persistence at startup and end of explore |
| numpy ≥ 1.24.0 | Python package | Occupancy grid, vector math |
| `json`, `math`, `time`, `threading` | stdlib | Map serialisation, nav loops |

---

## Quick-Start Integration Example

```c
#include "m5_navigation.h"

int main(void) {
    // Load saved map at startup (calls M7 internally)
    if (m5_init_navigation() != M5_OK) {
        return -1;
    }

    // Issue EXPLORE command from M6
    m5_nav_order_t order = {
        .command         = M5_CMD_EXPLORE,
        .target_heading  = 0.0f,
        .speed_override  = 0      // use default speed
    };
    m5_execute_command(&order);

    // Poll status (called by M6 on every FSM iteration)
    m5_nav_status_t status;
    m5_get_nav_status(&status);
    if (status.exploration_complete) {
        m5_save_map(NULL);  // persist map to /data/map.json
    }

    // Issue VERIFY command: approach heading 45°
    m5_nav_order_t verify_order = {
        .command        = M5_CMD_VERIFY,
        .target_heading = 45.0f,
        .speed_override = 50
    };
    m5_execute_command(&verify_order);

    m5_cleanup();
    return 0;
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m5_init_navigation()` | — | `m5_status_t` | Loads map; starts nav thread |
| `m5_execute_command(order)` | `const m5_nav_order_t *` | `m5_status_t` | Called by M6 on state transitions |
| `m5_get_nav_status(status_out)` | `m5_nav_status_t *` | `m5_status_t` | Polled by M6 each FSM iteration |
| `m5_update_navigation(left, right, heading)` | `float`, `float`, `float` | `m5_status_t` | Internal; exposed for unit testing |
| `m5_save_map(filepath)` | `const char *` | `m5_status_t` | NULL = default path |
| `m5_load_map(filepath)` | `const char *` | `m5_status_t` | NULL = default path |
| `m5_cleanup()` | — | `m5_status_t` | Stops nav thread |

---

## Known Limitations & TODOs

- Dead-reckoning position estimation drifts over long runs; alternative odometry correction is required.
- Patrol waypoints are generated automatically from the explored grid; manual waypoint injection is not yet supported.
- Recovery behaviour when `is_stuck == true` is a simple reverse-and-turn; more sophisticated recovery is a future TODO.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: execute_command, get_nav_status, save_map, load_map |

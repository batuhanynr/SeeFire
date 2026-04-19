# M6_DECISION — Decision Engine (FSM)

One-sentence purpose: Runs the five-state finite-state machine (INIT → EXPLORE → PATROL → VERIFY → ALARM) that fuses sensor and vision inputs to control robot behaviour and trigger alarms.

**Author:** Emre Can Tuncer (200104004115), Semih Sarkoca (220104004038), Ahmet Furkan Arslan (220104004044), Halil Buğra Şen (230104004088)
**Module ID:** M6  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| Multiprocessing Architecture | Architecture | **CRITICAL:** M6 FSM and M5 Navigation must run in separate processes from M4 Vision to prevent YOLO inference bottlenecks from delaying sensor polling (HC-SR04), which would cause collisions. |
| M2 `m2_set_alarm()`, `m2_get_battery_voltage()` | Module | Alarm output and low-battery monitoring |
| M3 `m3_get_fusion_sensors()` | Module | Polled every ~500 ms |
| M4 `m4_get_latest_result()`, `m4_capture_snapshot()` | Module | Vision input each FSM iteration |
| M5 `m5_execute_command()`, `m5_get_nav_status()` | Module | Navigation control and feedback |
| M7 `m7_log_event()` | Module | Event logging on every state change |
| `threading`, `time`, `logging` (stdlib) | Python | FSM loop and debug logging |

---

## Quick-Start Integration Example

```c
#include "m6_decision.h"

int main(void) {
    // Initialise all dependencies first, then M6
    if (m6_init() != M6_OK) {
        return -1;
    }

    // Start FSM loop (blocking; runs until m6_stop() is called)
    m6_run();

    return 0;
}

// --- Example: manual fusion score calculation for unit testing ---
void test_fusion(void) {
    m4_vision_result_t vision = { .detection_count = 1 };
    vision.detections[0].confidence = 0.8f;

    m3_fusion_data_t sensors = {
        .smoke_level = 500,
        .ir_temp     = 75.0f
    };

    float score = 0.0f;
    m6_calculate_fusion_score(&vision, &sensors, &score);
    // Expected: 0.5*0.8 + 0.3*(500/1023) + 0.2*clamp((75-40)/60,0,1) ≈ 0.69
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m6_init()` | — | `m6_status_t` | Sets FSM to M6_STATE_INIT |
| `m6_run()` | — | `m6_status_t` | Blocking FSM loop |
| `m6_stop()` | — | `m6_status_t` | Signals loop to exit |
| `m6_get_state(state_out)` | `m6_fsm_state_t *` | `m6_status_t` | Current FSM state |
| `m6_calculate_fusion_score(vision, sensors, score_out)` | pointers | `m6_status_t` | Returns 0.0–1.0 threat score |
| `m6_trigger_alarm(event)` | `const m6_alarm_event_t *` | `m6_status_t` | Activates LED/buzzer, logs event |
| `m6_reset_alarm()` | — | `m6_status_t` | Deactivates alarm, restores prior state |

---

## FSM State Transitions (Quick Reference)

| From | To | Condition |
|---|---|---|
| INIT | EXPLORE | No saved map found |
| INIT | PATROL | Saved map loaded |
| EXPLORE / PATROL | VERIFY | vision_conf > 0.5 OR smoke_alert OR ir_temp > threshold |
| VERIFY | ALARM | fusion_score > 0.7 |
| VERIFY | PATROL | fusion_score < 0.4 |
| ALARM | EXPLORE / PATROL | Manual reset or timeout |

---

## Known Limitations & TODOs

- Alarm auto-reset timeout value is not yet configurable via `config.py`; currently requires code change.
- Fusion weights (W_VISION, W_SMOKE, W_IR) are fixed constants; dynamic tuning via runtime config is planned.
- Multi-fire scenario (two simultaneous hotspots) is not handled; FSM only tracks one alarm at a time.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: FSM states, fusion score, alarm control, reset |

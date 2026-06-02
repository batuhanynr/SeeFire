# SeeFire — Current Architecture Notes

CSE 396 project repository for the SeeFire indoor fire-detection robot.

This file describes the **current codebase truth**. When it conflicts with older reports, headers, or draft READMEs, follow this file and the live Python modules.

## Baseline and Deviations

The project still follows the high-level SeeFire concept from `docs/SeeFire_Module_Documentation_Report.md`: a Raspberry Pi based indoor fire-detection robot with modular ownership (`M1`–`M7`).

The main deviation is navigation:
- The map is **static and pre-drawn**. M5 does not build an occupancy grid anymore.
- The route is split into **south-to-north sectors** defined by `config.WAYPOINTS`.
- Before motion starts, the robot validates its placement by comparing left/right HC-SR04 readings against known start references.
- Arduino is **not used**. Motor control, ultrasonic reads, and encoder pulse counting are all handled directly on the Raspberry Pi GPIO stack.

## Module Status

| ID | Module | Current Status | Notes |
|---|---|---|---|
| M1 | Chassis & Mechanics | Hardware-only | No Python implementation. |
| M2 | Motor Control & Power | Implemented | L298N drive, alarm I/O, battery voltage read, encoder-backed distance API, `cleanup()` with GPIO release, `SEEFIRE_FORCE_MOCK` env var, mock mode. 5 tests. |
| M3 | Sensor Integration | Implemented | MQ-2, MLX90614 (raw SMBus, no adafruit dependency), HC-SR04 x3 (`left/front/right`), median-filtered nav reads, deterministic mock RNG, `SEEFIRE_FORCE_MOCK` env var, full GPIO cleanup, mock mode. 6 tests. |
| M4 | Vision | Partially implemented | Camera open/close, frame capture, background `_update_loop` thread, obstacle turn-direction hint (Canny edge). Fire/smoke YOLOv8n inference pipeline not integrated yet (placeholder). 0 tests. |
| M5 | Navigation | Implemented | Waypoint-driven sector traversal, obstacle bypass redesign (wall-hit retreat, forward-pass acquire/release, 4-direction midpoint scan, encoder rollback via `_drive_lateral`), sütun-uyumlu position correction, median-filtered D₀, offline simülatör (`m5_navigation/sim/`). 13 tests. |
| M6 | Decision Engine | Implemented | FSM with 5 states (`INIT → NAVIGATE → VERIFY → ALARM → STOP`). Fusion score (`_calculate_fusion_score` with config weights). `_on_snapshot` callback for M7 logging + state transitions. Battery health monitoring. Wired into `main.py`. 0 tests. |
| M7 | Logging & Output | Implemented | SQLite (WAL mode, thread-safe), event logging, JSON map save/load with atomic write (`os.replace`), JPEG snapshot persistence (`event_id_timestamp.jpg`). 14 tests. |

## Runtime Reality

- `main.py` initializes `M7 -> M2 -> M3 -> M4`, then starts `DecisionEngine.start()` (M6 FSM loop).
- M6 FSM calls `NavigationController.run()` under the hood — M5 is wired via M6.
- M4 YOLOv8n inference is still a placeholder (`mock_fire=0.0, mock_smoke=0.0` in `_update_loop`).
- Persistent files default to `runtime_data/` inside the repo unless `SEEFIRE_DATA_DIR` is set.
- `SEEFIRE_FORCE_MOCK=1` env var forces mock mode even when RPi.GPIO is available.

## Sensor and Motion Model

- Ultrasonics: `left`, `front`, `right`
- Obstacle detection: front HC-SR04
- Start-position verification: left/right HC-SR04
- Main odometry source: wheel encoders
- Obstacle bypass direction:
  - primary: camera pixel-gap heuristic from M4
  - fallback: left/right ultrasonic comparison
- Obstacle clearance:
  - bypass right: use `left_cm`
  - bypass left: use `right_cm`

## Mock Mode

Mock mode is intentional and part of the development workflow.

- If `RPi.GPIO` is missing, M2 and M3 fall back to simulated behavior.
- If OpenCV/Numpy are missing, M4 still imports and returns `None` for turn-direction hints.
- Mock mode should work on normal development machines without a writable `/data` mount.

## Source of Truth Priority

When documents disagree, use this order:

1. Live Python code under `m2_motor/`, `m3_sensors/`, `m4_vision/`, `m5_navigation/`, `m6_decision/`, `m7_logging/`
2. `config.py`
3. This file
4. `docs/nelerdegisti.md`
5. `docs/SeeFire_Module_Documentation_Report.md`

## Immediate Gaps

- M4 fire/smoke inference is still pending (YOLOv8n placeholder in `vision.py:75-76`).
- M6 FSM is implemented but has 0 tests.
- `m6_decision/tests/` directory is empty.
- Several legacy `.h` files and old README sections still describe the original explore/patrol architecture; update them cautiously and prefer Python behavior over header drafts.

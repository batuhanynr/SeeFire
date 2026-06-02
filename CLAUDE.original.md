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
| M2 | Motor Control & Power | Implemented | L298N drive, alarm I/O, battery voltage read, encoder-backed distance API, mock mode. |
| M3 | Sensor Integration | Implemented | MQ-2, MLX90614, HC-SR04 x3 (`left/front/right`), median-filtered nav reads, mock mode. |
| M4 | Vision | Partially implemented | Camera open/close, frame capture, obstacle turn-direction hint. Fire/smoke inference pipeline is not integrated yet. |
| M5 | Navigation | Implemented | Sector traversal on static route, midpoint/waypoint snapshot hooks, obstacle bypass, start verification. |
| M6 | Decision Engine | Not implemented | `m6_decision` is still a placeholder; no live FSM loop yet. |
| M7 | Logging & Output | Implemented | SQLite event log, JSON save/load helpers, JPEG snapshot persistence. |

## Runtime Reality

- `main.py` currently initializes `M7 -> M2 -> M3 -> M4`.
- `M5` can be exercised independently from Python, but is not yet wired into `main.py`.
- `M6` is not yet wired because the decision engine has not been implemented.
- Persistent files default to `runtime_data/` inside the repo unless `SEEFIRE_DATA_DIR` is set.

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

1. Live Python code under `m2_motor/`, `m3_sensors/`, `m4_vision/`, `m5_navigation/`, `m7_logging/`
2. `config.py`
3. This file
4. `docs/nelerdegisti.md`
5. `docs/SeeFire_Module_Documentation_Report.md`

## Immediate Gaps

- M6 FSM and alarm orchestration are still pending.
- M4 fire/smoke inference is still pending.
- Several legacy `.h` files and old README sections still describe the original explore/patrol architecture; update them cautiously and prefer Python behavior over header drafts.

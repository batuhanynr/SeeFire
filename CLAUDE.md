# SeeFire — Current Architecture Notes

CSE 396 project repo for SeeFire indoor fire-detection robot.

**Current codebase truth.** Conflicts with older reports/headers/draft READMEs: follow this file and live Python modules.

## Baseline and Deviations

Follows high-level SeeFire concept from `docs/SeeFire_Module_Documentation_Report.md`: Raspberry Pi indoor fire-detection robot, modular ownership (`M1`–`M7`).

Main deviation — navigation:
- Map **static and pre-drawn**. M5 no longer builds occupancy grid.
- Route split into **south-to-north sectors** defined by `config.WAYPOINTS`.
- Before motion: robot validates placement by comparing left/right HC-SR04 readings against known start references.
- Arduino **not used**. Motor control, ultrasonic reads, encoder pulse counting all handled on Raspberry Pi GPIO stack.

## Module Status

| ID | Module | Current Status | Notes |
|---|---|---|---|
| M1 | Chassis & Mechanics | Hardware-only | No Python implementation. |
| M2 | Motor Control & Power | Implemented | L298N drive, alarm I/O, battery voltage read, encoder-backed distance API, mock mode. |
| M3 | Sensor Integration | Implemented | MQ-2, MLX90614, HC-SR04 x3 (`left/front/right`), median-filtered nav reads, mock mode. |
| M4 | Vision | Partially implemented | Camera open/close, frame capture, obstacle turn-direction hint. Fire/smoke inference pipeline not integrated yet. |
| M5 | Navigation | Implemented | Sector traversal on static route, midpoint/waypoint snapshot hooks, obstacle bypass, start verification. |
| M6 | Decision Engine | Not implemented | `m6_decision` still placeholder; no live FSM loop yet. |
| M7 | Logging & Output | Implemented | SQLite event log, JSON save/load helpers, JPEG snapshot persistence. |

## Runtime Reality

- `main.py` initializes `M7 -> M2 -> M3 -> M4`.
- `M5` exercisable independently from Python, not yet wired into `main.py`.
- `M6` not wired — decision engine not implemented.
- Persistent files default to `runtime_data/` inside repo unless `SEEFIRE_DATA_DIR` set.

## Sensor and Motion Model

- Ultrasonics: `left`, `front`, `right`
- Obstacle detection: front HC-SR04
- Start-position verification: left/right HC-SR04
- Main odometry: wheel encoders
- Obstacle bypass direction:
  - primary: camera pixel-gap heuristic from M4
  - fallback: left/right ultrasonic comparison
- Obstacle clearance:
  - bypass right: use `left_cm`
  - bypass left: use `right_cm`

## Mock Mode

Mock mode intentional, part of dev workflow.

- `RPi.GPIO` missing: M2/M3 fall back to simulated behavior.
- OpenCV/Numpy missing: M4 still imports, returns `None` for turn-direction hints.
- Mock mode works on dev machines without writable `/data` mount.

## Source of Truth Priority

When documents disagree:

1. Live Python code under `m2_motor/`, `m3_sensors/`, `m4_vision/`, `m5_navigation/`, `m7_logging/`
2. `config.py`
3. This file
4. `docs/nelerdegisti.md`
5. `docs/SeeFire_Module_Documentation_Report.md`

## Immediate Gaps

- M6 FSM and alarm orchestration pending.
- M4 fire/smoke inference pending.
- Legacy `.h` files and old README sections still describe original explore/patrol architecture; update cautiously, prefer Python behavior over header drafts.
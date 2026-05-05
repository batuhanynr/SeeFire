# SeeFire — Original Report vs Current Code

This note tracks the main deviations from `SeeFire_Module_Documentation_Report.md`.

Use this file together with `CLAUDE.md` when older documents disagree with the current repository.

## 1. Core Project Direction

The project is still the same SeeFire robot described in the Assignment 3 report:
- Raspberry Pi based
- modular structure (`M1`–`M7`)
- offline operation
- fire-detection goal

The largest changes are in navigation and implementation maturity.

## 2. Navigation Changes

### Original report

- unknown-environment exploration
- wall-following
- occupancy-grid creation
- explore/patrol transition

### Current code

- the map is **pre-drawn**
- the route is **static**
- movement is **south-to-north sector traversal**
- start placement is validated with left/right HC-SR04 before motion
- waypoint and midpoint snapshot hooks exist in M5
- there is no live exploration phase in M5

## 3. Hardware / I/O Changes

| Topic | Original report | Current code |
|---|---|---|
| Ultrasonic layout | 2 sensors | 3 sensors: `left`, `front`, `right` |
| ADC wording | MCP3008 in parts of the docs | Current Python code uses MCP3208-style 12-bit conversion |
| Navigation I/O | Some drafts implied alternate controller setups | Current implementation targets Raspberry Pi GPIO directly |
| Arduino | Mentioned in some side documents | **Not used** |

## 4. Software Maturity Changes

| Module | Current reality |
|---|---|
| M2 | Implemented with mock mode, battery read, encoder-backed distance API |
| M3 | Implemented with fusion data and median-filtered nav reads |
| M4 | Only camera/frame and turn-direction hint are live; fire inference pipeline is still pending |
| M5 | Static-route navigation is implemented |
| M6 | Still placeholder; no live FSM loop yet |
| M7 | Implemented |

This means some old documents still describe a fully wired `INIT -> EXPLORE -> PATROL -> VERIFY -> ALARM` runtime, but the repository has not reached that stage yet.

## 5. Mock Mode and Development Environment

The repository now supports normal development machines much better than the original report assumed.

- Missing `RPi.GPIO` triggers mock behavior in M2/M3
- Missing OpenCV/Numpy keeps M4 importable with degraded behavior
- Persistent files default to repo-local `runtime_data/` unless `SEEFIRE_DATA_DIR` is set

This is intentional so the team can develop without the physical robot connected.

## 6. Source-of-Truth Rule

When there is a conflict:

1. Python implementation
2. `config.py`
3. `CLAUDE.md`
4. this file
5. older reports and headers

## 7. Important Clarification for Future Report Writing

If a future report is produced, it should say:
- the navigation map is static and prepared beforehand
- the robot verifies left/right wall references at startup
- Raspberry Pi handles the hardware directly
- Arduino is not part of the current architecture
- M6 FSM is planned but not yet implemented in the repository

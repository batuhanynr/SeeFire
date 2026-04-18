# SeeFire — Autonomous Fire Detection Robot

CSE 396 — Computer Engineering Project, Gebze Technical University (2025-2026 Spring)

## Module Overview

| ID | Module | Dependencies | Description |
|---|---|---|---|
| M1 | Chassis & Mechanics | — | Physical assembly, 3D printing, cabling. No code. |
| M2 | Motor Control & Power | M1 | L298N H-bridge, PWM drive, LiPo monitoring, alarm I/O |
| M3 | Sensor Integration | M1 | MQ-2, MLX90614, DHT22, HC-SR04 x2, MPU6050 drivers |
| M4 | AI & Vision | — | YOLOv8n INT8 inference, OpenCV pipeline, snapshot capture |
| M5 | Navigation & Mapping | M2, M3 | Wall-following, occupancy grid, waypoint patrol |
| M6 | Decision Engine | M3, M4 | FSM (INIT→EXPLORE→PATROL→VERIFY→ALARM), sensor fusion |
| M7 | Data Logging & Output | — | SQLite event log, JSON map export/import, JPEG snapshot storage |

## Architecture

All modules run as **Python threads** on a single **Raspberry Pi 4B (4 GB RAM)** running Raspberry Pi OS 64-bit Bookworm. No network, no FPGA, no secondary MCU. Inter-module communication is via direct Python function calls, `threading.Lock`, and `threading.Event`.

**Startup order:** `main.py` initializes M7 → M2 → M3 → M4 → M5 → M6.

### Data Flow
```
M3 (Sensors) ──get_fusion_sensors()──> M6 (Decision Engine)
M3 (Sensors) ──get_navigation_sensors()──> M5 (Navigation)
M4 (Vision)  ──get_latest_result()──> M6
M5 (Nav)     ──motor_drive()──> M2 (Motor)
M6 (Decision)──execute_command()──> M5
M6 (Decision)──set_alarm()──> M2
M6 (Decision)──log_event()──> M7 (Data Logging)
M5 (Nav)     ──save_map()/load_map()──> M7
M6 (Decision)──capture_snapshot()──> M4 → M7 (JPEG storage)
```

## Technical Stack

| Library | Version | Module | Purpose |
|---|---|---|---|
| RPi.GPIO | >= 0.7.1 | M2, M3 | GPIO + PWM |
| smbus2 | >= 0.4.1 | M3 | I2C bus |
| adafruit-circuitpython-mlx90614 | latest | M3 | MLX90614 driver |
| mpu6050-raspberrypi | >= 1.2 | M3 | MPU6050 IMU |
| Adafruit_DHT | >= 1.4.0 | M3 | DHT22 driver |
| sqlite3 | stdlib | M7 | Event database |
| opencv-python | >= 4.8.0 | M4 | Frame capture |
| ultralytics | >= 8.0.0 | M4 | YOLOv8n inference |
| numpy | >= 1.24.0 | M4, M5 | Array ops |
| Pillow | >= 9.5.0 | M4 | JPEG encode/decode |

> **Note:** The technical stack is not rigid. Library versions may be upgraded, downgraded, or new dependencies added as the project requires. The table above reflects the initial baseline, not a fixed constraint.

## Coding Conventions

- **Language:** Python 3.11+
- **All shared constants** live in `config.py` — never hardcode pin numbers, I2C addresses, thresholds, or file paths
- **Thread safety:** All shared mutable state must be protected with `threading.Lock`
- **Module interfaces:** Use typed dataclass structures defined in each module (e.g., `m3_fusion_data_t`, `m7_event_t`)
- **Error handling:** Validate at system boundaries (sensor reads, file I/O). Trust internal function calls
- **No comments** unless the WHY is non-obvious
- **Each module** lives in its own directory with code, header, README, and tests.

## File Structure

```
SeeFire/
├── main.py              # Entry point — init order: M7→M2→M3→M4→M5→M6
├── config.py            # Shared constants (pins, thresholds, weights, paths)
├── m2_motor/
│   ├── motor.py         # Motor & power control
│   ├── m2_motor.h       # Interface header
│   ├── README.md        # Module documentation
│   └── tests/
├── m3_sensors/
│   ├── sensors.py       # Sensor integration (5 sensors)
│   ├── m3_sensors.h     # Interface header
│   ├── README.md        # Module documentation
│   └── tests/
├── m4_vision/
│   ├── vision.py        # AI & vision (YOLOv8n)
│   ├── m4_vision.h
│   ├── README.md
│   └── tests/
├── m5_navigation/
│   ├── navigation.py    # Navigation & mapping
│   ├── m5_navigation.h
│   ├── README.md
│   └── tests/
├── m6_decision/
│   ├── decision.py      # Decision engine (FSM)
│   ├── m6_decision.h
│   ├── README.md
│   └── tests/
├── m7_logging/
│   ├── logging.py       # Data logging & output
│   ├── m7_logging.h     # Interface header
│   ├── README.md        # Module documentation
│   └── tests/
├── docs/
│   ├── SeeFire_Interface_report.md
│   ├── SeeFire_Project_Proposal.md
│   └── Similar_Projects.md
└── requirements.txt
```

## Critical Hardware Constraints

- **MQ-2 warm-up:** ~60s before stable readings. INIT state must account for this.
- **MCP3208 ADC:** Required for MQ-2 analog → SPI. CS on GPIO 5.
- **MPU6050 drift:** Gyroscope integration drifts over time. Wall-reference correction needed for long patrols.
- **SQLite WAL mode:** Required to prevent write contention between M5 map saves and M6 event logs.
- **LiPo monitoring:** Voltage divider ADC circuit — resistor values and calibration TBD.

## Fusion Score Formula (M6)

```
fusion_score = (0.5 * vision_conf) + (0.3 * smoke_score) + (0.2 * ir_score)
smoke_score = smoke_level / 1023
ir_score = clamp((ir_temp - 40) / 60, 0, 1)
```

## Similar Projects Reference

Reference repos analyzed for inspiration (see `Similar_Projects.md`):
- **pdsuthar10/Automatic-Fire-Fighting-Robot:** Best reference for obstacle avoidance decision tree, multi-directional sensor fusion, state machine pattern. Arduino C++ — adapt concept, not code.
- **nikhiljainjain/Fire-fighting-Robot:** RPi + Python GPIO setup template, motor PWM control. Direct copy-paste potential for M2.
- **HamzaR13/Firefighting-Robot:** Ultrasonic distance conversion — directly usable for M3 HC-SR04 driver.
- **Circuit-Digest:** Hardware wiring diagram reference (H-bridge, flame sensor, pump).

**Rule:** Use concepts and patterns from these repos. Do not blindly copy-paste Arduino C++ into Python.

## Agent Usage Style

- **Language:** Internal reasoning in English. User-facing responses in Turkish with English technical terms.
- **Approach:** Prefer building on existing solutions over reinventing. Check `Similar_Projects.md` before implementing from scratch.
- **Workflow:** Read existing code before writing. Use `config.py` constants. Maintain the module interface contract.
- **Testing:** M7 can be tested standalone. M3 can be tested with mock sensor data. Always verify thread safety.

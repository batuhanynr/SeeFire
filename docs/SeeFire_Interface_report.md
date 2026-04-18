# SeeFire

## Autonomous Fire Detection Robot

## ASSIGNMENT 2

### Module Interface & Header Design Report

**Field Details**

Course CSE 396 - Computer Engineering Project

University Gebze Technical University | Computer Engineering Department

Semester 2025 - 2026 Spring

Date 01 March 2025

### Team Members

**Full Name Student ID Module(s)**

Emre Can Tuncer 200104004115 M4 (AI & Vision) + M6 (Decision Engine)

Batuhan Yanar 220104004059 M7 (Data Logging) + M3 (Sensor Integration)

Ahmet Furkan Arslan 220104004044 M5 (Navigation) + M6 (Decision Engine)

Alperen Sahin 220104004943 M1 (Chassis) + M3 (Sensor Integration)

Semih Sarkoca 220104004038 M6 (Decision Engine) + M4 (AI & Vision)

Yusuf Alperen Celik 220104004064 M5 (Navigation) + M7 (Data Logging)

Bekir Emre Sarpinar 220104004039 M3 (Sensor Integration) + M2 (Motor Control)

Halil Bugra Sen 230104004088 M1 (Chassis) + M6 (Decision Engine)


## 1. Project Overview

SeeFire is an autonomous wheeled robot designed for indoor fire hazard detection using edge
computing. All software modules run on a single Raspberry Pi 4B. Inter-module communication is
handled exclusively through local Python function calls, threading events, and shared data structures
— no external network or serial communication is used. The robot explores an unknown indoor
environment, builds an occupancy grid map, patrols the mapped area, and raises a multi-modal alarm
(LED + buzzer + JPEG snapshot) when fire or smoke is detected with sufficient confidence.

### 1.1 Module-Student Matching Table

```
Module ID Module Name Responsible Student(s) Brief Role
```
```
M1 Chassis & Mechanics Alperen Sahin Halil Buğra Şen^ Physical assembly, 3D printing, cabling
```
```
M2 Motor Control & Power Bekir Emre SarEmre Can Tuncerıpınar
```
```
L298N H-bridge, PWM
drive, LiPo monitoring,
alarm I/O
```
```
M3 Sensor Integration
```
```
Alperen Sahin
Bekir Emre Sarıpınar
Batuhan Yanar
```
```
MQ-2, MLX90614,
DHT22, HC-SR04,
MPU6050 drivers and
fusion API
```
```
M4 AI & Vision Emre Can Tuncer Semih Sarıkoca
```
```
YOLOv8n INT
inference, OpenCV
pipeline, snapshot
capture
```
```
M5 Navigation & Mapping Ahmet Furkan Arslan Yusuf Alperen Celik
```
```
Wall-following,
occupancy grid,
waypoint patrol,
obstacle avoidance
```
```
M6 Decision Engine
```
```
Ahmet Furkan Arslan
Semih Sarıkoca
Halil Buğra Şen
```
```
FSM (INIT->EXPLORE-
>PATROL->VERIFY-
>ALARM), sensor fusion
scoring
```
```
M7 Data Logging & Output Batuhan YanarYusuf Alperen Ç^ elik
```
```
SQLite event log, JSON
map export/import,
JPEG snapshot storage
```

## 2. System / Module Overview

### 2.1 Block Diagram

The diagram below shows all seven modules and the primary data flows between them. All
communication is in-process on the Raspberry Pi 4.

#### +----------------+ GPIO/PWM +------------------+

```
| M1 Chassis | --------------> | M2 Motor & |
| (Hardware) | | Power Control |
+----------------+ +--------+---------+
| motor_drive()
+----------------+ get_nav_sensors() |
| M3 Sensor | -----------------------> |
| Integration | +--------v---------+
| | get_fusion() | M5 Navigation |
| | --------------> | & Mapping |
+----------------+ | +--------+---------+
| | execute_command()
+----------------+ | +--------v---------+
| M4 AI & | +-------->| M6 Decision |
| Vision | get_result() | Engine (FSM) |
| (YOLOv8n) | --------------> | |
+----------------+ +--------+---------+
| log_event()
+---------v----------+
| M7 Data Logging |
| SQLite + JSON |
+--------------------+
```
### 2.2 Module Descriptions

**M1 - Chassis & Mechanics**

Provides the physical platform: a REX 4WD aluminium chassis, custom 3D-printed mounts for the
camera and sensors, and the wiring harness connecting all electronics. M1 must be complete before
any other module can be tested on real hardware.

**M2 - Motor Control & Power**

Drives the L298N H-bridge motor driver using Raspberry Pi GPIO and hardware PWM at ~1 kHz.
Exposes motor_drive(), motor_stop(), and motor_turn() for M5, and set_alarm() for M6. Monitors LiPo
battery voltage via an ADC voltage divider.

**M3 - Sensor Integration**
Aggregates five sensors: MQ-2 smoke (SPI ADC), MLX90614 IR temperature (I2C), DHT22 ambient
temperature/humidity (single-wire GPIO), two HC-SR04 ultrasonics (GPIO), and MPU6050 IMU (I2C).
Provides get_fusion_sensors() for M6 and get_navigation_sensors() for M5.

**M4 - AI & Vision**

Captures frames from a USB webcam at 320x320 px and runs YOLOv8n INT8 inference in a
background thread targeting >= 5 FPS on the RPi 4 CPU. Exposes get_latest_result() for M6 and
capture_snapshot() for JPEG alarm photos.

**M5 - Navigation & Mapping**


Implements wall-following exploration using HC-SR04 distances, dead-reckoning position tracking with
MPU6050, and a 40x40 cell (10 cm resolution) occupancy grid. Transitions between EXPLORE,
PATROL, VERIFY, and STOP modes on orders from M6.

**M6 - Decision Engine**
Hosts the five-state FSM (INIT -> EXPLORE -> PATROL -> VERIFY -> ALARM). Polls M3 sensors
every ~500 ms and M4 vision on every FSM iteration. Computes a weighted fusion score (0.5 x vision
+ 0.3 x smoke + 0.2 x IR) to decide state transitions and alarm triggering.

**M7 - Data Logging & Output**

Maintains an SQLite database of timestamped events, serialises the occupancy grid as JSON, and
stores alarm JPEG snapshots on the SD card. Has no module dependencies and must be initialised
before M5 and M6.

### 2.3 Overall System Architecture

All modules execute as Python threads on a single Raspberry Pi 4 (4 GB RAM) running Raspberry Pi
OS (64-bit Bookworm). The entry point main.py initialises modules in the order M7 -> M2 -> M3 -> M

- > M5 -> M6 to satisfy all dependencies. There is no network communication, no FPGA, and no
secondary microcontroller; all real-time constraints are soft and managed through Python
threading.Event and time.sleep() calls.


## 3. Hardware & Platform Summary

```
Component Model / Spec Module Notes
SBC (Single Board
Computer) Raspberry Pi 4B -^ 4 GB RAM^ All^
```
```
Single compute node for all
SW modules
```
```
Chassis REX 4WD aluminium kit M1 4 DC motors, preplatform - drilled
```
```
Motor Driver L298N H-bridge M2 6 GPIO pins (IN1ENB) - 4, ENA,
```
```
Battery LiPo 11.1V 3S + 5V step-down M2 RPi and motors powered separately
```
```
Gas Sensor MQ-2 smoke/gas sensor M3 Analog SPI ADC-^ requires MCP
```
```
IR Thermometer MLX90614 M3 I2C 0x5A, object surface temperature
```
```
Ambient Temp/Humidity DHT22 M3 Single-wire GPIO
```
```
Ultrasonic HC-SR04 x 2 M3 Left + right obstacle detection
```
```
IMU MPU6050 M3 I2C 0x68, yaw heading
Camera USB webcam M4 15 - 20 FPS at 320x320 px
```
```
3D Printed Parts PLA, >= 0.2 mm resolution x4 M
```
```
Camera bracket, sensor
mounts, enclosure, LED
frame
```
```
Storage MicroSD (RPi default) M7 map.json, seefire.db, snapshots/
```
### 3.1 Communication Buses

```
Bus Devices Speed / Configuration
I2C MLX90614 (0x5A), MPU6050 (0x68) 100 kHz standard mode
SPI MCP3208 ADC for MQ- 2 SPI0, CS via GPIO 5
GPIO HC-SR04 x2, DHT22, L298N, LED, Buzzer 3.3V logic level, RPi GPIO
USB Webcam USB 2.0, Video4Linux
PWM L298N ENA, ENB ~1 kHz, GPIO 12 & 13
```
### 3.2 External Libraries / SDKs

```
Library Version Module Purpose
RPi.GPIO >= 0.7.1 M2, M3 GPIO and PWM control
smbus2 >= 0.4.1 M3 I2C bus access
adafruit-circuitpython-mlx90614 latest M3 MLX90614 IR temperature driver
mpu6050-raspberrypi >= 1.2 M3 MPU6050 IMU driver
Adafruit_DHT >= 1.4.0 M3 DHT22 ambient sensor driver
opencv-python >= 4.8.0 M4 Frame capture and preprocessing
```

**Library Version Module Purpose**

ultralytics >= 8.0.0 M4 YOLOv8n model loading and inference

numpy >= 1.24.0 M4, M5 Array operations, occupancy grid

Pillow >= 9.5.0 M4 JPEG encoding/decoding

sqlite3 stdlib M7 Event database


## 4. Inter-Module Communication

All inter-module communication uses direct Python function calls within the same process. Shared
mutable state is protected by threading.Lock objects inside each module. The table below is the single
source of truth for all module interfaces.

```
From To Function / Signal Type Direction Frequency
M3 M6 get_fusion_sensors() m3_fusion_data_t M3 -> M6 ~500 ms
M3 M5 get_navigation_sensors() m3_nav_data_t M3 -> M5 ~100-200 ms
```
```
M4 M6 get_latest_result() m4_vision_result_t M4 -> M6 Each FSM iteration
```
```
M4 M6 capture_snapshot() JPEG bytes M4 -> M6 ALARM state only
```
```
M6 M5 execute_command(order) m5_nav_order_t M6 -> M5 On state transitions
```
```
M5 M6 get_nav_status() m5_nav_status_t M5 -> M6 Each FSM iteration
```
```
M5 M2 motor_drive(dir, speed) m2_direction_t, int M5 -> M2 ~100 ms
M5 M2 motor_turn(angle, speed) float, int M5 -> M2 On demand
M6 M2 set_alarm(led, buzzer) bool, bool M6 -> M2 ALARM state
M2 M6 get_battery_voltage() float (V) M2 -> M6 ~10 s
```
```
M6 M7 log_event(event) m7_event_t M6 -> M7 Every FSM event
```
```
M5 M7 save_map(map_json) JSON string M5 -> M7 Explore done / periodic
```
```
M7 M5 load_map(buf, size) JSON string M7 -> M5 System startup only
```

## 5. Decision Engine - FSM State Transitions

```
From State To State Condition Action Taken
```
```
INIT EXPLORE No saved map found at startup Issue NavCommand.EXPLORE
```
```
INIT PATROL Saved map loaded successfully Load grid, issue NavCommand.PATROL
```
```
EXPLORE VERIFY vision_conf > 0.5 OR smoke_alert OR ir_temp > 60 C Pause exploration, approach target heading
```
```
PATROL VERIFY vision_conf > 0.5 OR smoke_alert OR ir_temp > 60 C Pause patrol, approach target heading
```
```
VERIFY ALARM fusion_score > 0.7 LED on, buzzer on, save JPEG, log event
```
```
VERIFY PATROL fusion_score < 0.4 Log FALSE_ALARM event, resume patrol
```
```
ALARM EXPLORE/PATROL Manual reset or configurable timeout Deactivate alarm, restore prior state
```
### 5.1 Fusion Score Formula

The threat fusion score (0.0-1.0) is computed by m6_calculate_fusion_score() as follows:

```
fusion_score = (0.5 x vision_conf) + (0.3 x smoke_score) + (0.2 x ir_score)
smoke_score = smoke_level / 1023
ir_score = clamp((ir_temp - 40) / 60, 0, 1)
```
Weights are defined in config.py and can be tuned without modifying any module code.


## 6. Critical Dependencies & Development Order

```
Step Modules Ready What Becomes Possible
1 M1 complete M2 motor testing on real hardware; M3 physical sensor mounting
2 M2 API ready M5 navigation tested on real hardware with real motors
3 M3 API ready M5 wall-following with ultrasonic + IMU; M6 sensor fusion unit tests
4 M4 pipeline ready M6 FSM tested with live YOLO detection results
5 M7 API ready M5 map save/load on startup; M6 event log verified
6 M5 + M6 ready End-to-end integration tests and full demo run
```
Critical Path: M1 -> M2 -> M5 -> Integration. M4 is fully independent and can be developed in parallel
against recorded video footage. M7 has no dependencies and should be completed early to unblock
M5 and M6 logging.


## 7. Known Risks & Open Questions

**R1 - YOLOv8n INT8 Performance on RPi 4**
The target is >= 5 FPS inference on the CPU. Actual throughput depends on the INT8 quantised model
and OpenCV preprocessing overhead. If performance falls below target, options include reducing input
resolution below 320x320 or using ONNX Runtime instead of the ultralytics Python API.

**R2 - MQ-2 Warm-Up Time**

The MQ-2 sensor requires approximately 60 seconds of warm-up before readings are stable. This
means the robot should not enter fire-detection mode immediately after power-on. A warm-up delay in
the INIT state must be agreed between M3 and M6.

**R3 - MPU6050 Heading Drift**
Gyroscope integration accumulates error over time, causing heading drift. For short demo runs (< 10
minutes) this is acceptable, but long patrols may deviate significantly. Complementary filtering or wall-
reference correction must be evaluated before final integration.

**R4 - MCP3208 ADC SPI Wiring for MQ- 2**

The MQ-2 is an analogue sensor and requires an external SPI ADC (MCP3208 or similar) since the
RPi 4 has no built-in ADC. The exact wiring and SPI chip-select pin must be confirmed between M
and M3 before sensor integration testing can begin.

**R5 - SQLite Concurrent Write Contention**

M5 saves the map (large JSON) and M6 logs events (frequent small writes) to the same SD card.
Without WAL mode, SQLite may block briefly. WAL mode should be enabled in M7 v0.2.

**R6 - LiPo Battery Monitoring Accuracy**
The voltage divider ADC circuit for battery monitoring has not yet been designed or tested. Resistor
values, ADC channel assignment, and calibration constants need to be finalised between M1 and M
before battery monitoring can be validated.


## 8. config.py - Shared Constants Reference

All pin assignments, I2C addresses, thresholds, fusion weights, and file paths are centralised in
config.py. No module should hard-code any of these values.

```
# GPIO Pin Assignments
MOTOR_IN1, MOTOR_IN2, MOTOR_IN3, MOTOR_IN4 = 17, 18, 27, 22
MOTOR_ENA, MOTOR_ENB = 12, 13
TRIG_LEFT, ECHO_LEFT = 23, 24
TRIG_RIGHT, ECHO_RIGHT = 25, 8
DHT22_PIN = 4 MQ2_CS_PIN = 5 LED_PIN = 26 BUZZER_PIN = 19
```
```
# I2C Addresses
MLX90614_ADDR = 0x5A MPU6050_ADDR = 0x
```
```
# Detection Thresholds
SMOKE_THRESHOLD = 300 # MQ-2 ADC value (0-1023)
IR_TEMP_THRESHOLD = 60.0 # degrees C - MLX90614 surface temperature
VISION_CONF_THRESHOLD = 0.5 # YOLO confidence to enter VERIFY state
FUSION_ALARM_THRESH = 0.7 # fusion_score to trigger ALARM state
FUSION_CLEAR_THRESH = 0.4 # fusion_score below which FALSE_ALARM is declared
```
```
# Navigation
OBSTACLE_DIST_CM = 20 # HC-SR04 stop threshold (cm)
GRID_RESOLUTION_M = 0.10 # Occupancy grid cell size (m)
WALL_FOLLOW_DIST_CM = 30 # Target wall-following distance (cm)
```
```
# Fusion Weights (must sum to 1.0)
W_VISION = 0.5 W_SMOKE = 0.3 W_IR = 0.
```
```
# File Paths
MAP_JSON_PATH = "/data/map.json"
SQLITE_DB_PATH = "/data/seefire.db"
SNAPSHOT_DIR = "/data/snapshots/"
```

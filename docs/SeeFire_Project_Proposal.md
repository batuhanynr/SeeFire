## Gebze Technical University
### Computer Engineering Department
### CSE 396 Computer Engineering Project
### 2025–2026 Spring

# SeeFire
## Autonomous Fire Detection Robot with Edge Computing
### Project Proposal

**Team Members / Student ID:**
* Emre Can Tuncer – 200104004115
* Batuhan Yanar – 220104004059
* Ahmet Furkan Arslan – 220104004044
* Alperen Şahin – 220104004943
* Semih Sarıkoca – 220104004038
* Yusuf Alperen Çelik – 220104004064
* Bekir Emre Sarıpmar – 220104004039
* Halil Buğra Şen – 230104004088

**Instructor:** Dr. Salih Sarp

---

## 1. Introduction and Problem Statement

Fires in enclosed industrial spaces —warehouses, factories, storage units— are a well-known safety problem. These places tend to be large, poorly ventilated, and full of flammable materials. If a fire breaks out at night or over the weekend when nobody is around, it can grow out of control before anyone even notices.

Most buildings rely on ceiling-mounted smoke detectors and heat sensors. They work, but they have obvious drawbacks: fixed coverage, blind spots in large open areas, no way to pinpoint exactly where the fire started, and a tendency to produce false alarms. They also cannot give you any visual confirmation —you just get a beeping alarm and have to figure out the rest yourself.

We want to build something better. **SeeFire** is an autonomous wheeled robot that patrols indoor areas and actively looks for fire hazards. It carries a USB camera to spot flames and smoke visually, an infrared temperature sensor to catch heat anomalies, and a gas sensor to pick up smoke particles in the air. All of this processing happens on the robot itself —on a Raspberry Pi 4— without any internet connection or cloud servers. We are going with an **edge computing** approach, meaning the robot decides on its own, locally, which gives us faster reaction times and zero dependency on network infrastructure.

---

## 2. Literature Review and References

### 2.1 Vision-Based Fire Detection with YOLO
The YOLO family has become a go-to choice for real-time fire and smoke detection. Talaat and Zain Eldin [1] applied YOLOv8 to fire detection in smart city scenarios. Deng et al. [5] added SlimNeck to YOLOv8 for a 2.7% recall improvement, while Xu et al. [6] proposed DSS-YOLO, a modified YOLOv8n focusing on early-stage fires.

### 2.2 Edge AI for Fire Detection
Running inference on small boards like Raspberry Pi is no longer just theoretical. Hossain et al. [2] deployed a quantized YOLOv8 on a Raspberry Pi 5. Our project uses a Pi 4; although slower, the robot moves at a pace where a slightly lower frame rate is acceptable. Andriyadi et al. [3] used a similar setup but relied on MQTT, whereas SeeFire remains fully offline.

### 2.3 Indoor Navigation for Mobile Robots
For navigating unknown indoor spaces, wall-following is a reliable approach. While SLAM methods like GMapping exist, they require LiDAR, which exceeds our budget. We will use ultrasonic-based wall-following with grid-based occupancy mapping and an MPU6050 for heading.

---

## 3. Hardware Architecture and Data Collection

### 3.1 Components and Budget
The estimated total budget is approximately **5,100 TL** (as of March 2026).
* **Core:** Raspberry Pi 4 (4 GB) — chosen for cost-efficiency over Pi 5.
* **Vision:** USB Webcam — more durable and cost-effective than the Pi Camera Module.
* **Chassis:** REX 4WD chassis kit with L298N motor driver.
* **Sensors:** MQ-2 (Smoke), MLX90614 (IR Temp), DHT22 (Ambient Temp/Humidity), MPU6050 (IMU), HC-SR04 (Ultrasonic x2).
* **Power:** LiPo 11.1V battery with 5V step-down converter.

### 3.2 3D Printed Parts
We will design and print: camera brackets, sensor mounts, an electronics enclosure, and an LED panel frame using FreeCAD or Fusion 360.

---

## 4. Software Methodology I: AI and Computer Vision

### 4.1 Why YOLOv8n
We chose YOLOv8n (Nano) because it is the lightest variant. We will apply **INT8 quantization** to optimize it for the Pi 4 CPU. The input resolution will be 320x320 px to maintain a balance between speed and detection distance.

### 4.2 Sensor Fusion
To reduce false positives, SeeFire uses a "voting" system:
1. **Visual:** YOLOv8n detects flame/smoke.
2. **Thermal:** MLX90614 confirms high heat in that direction.
3. **Gas:** MQ-2 detects smoke particles.
4. **Ambient:** DHT22 monitors sudden temperature spikes.

---

## 5. Software Methodology II: Navigation and Mapping

### 5.1 Robot States
* **EXPLORE:** Traces walls, builds a 2D grid map, and saves waypoints.
* **PATROL:** Follows the saved waypoints continuously.
* **VERIFY:** Pauses to investigate a suspicious reading.
* **ALARM:** Confirms threat, triggers LEDs/Buzzer, and logs coordinates.

### 5.2 Mapping and Drift Correction
The robot uses a 10cm x 10cm occupancy grid saved as a **JSON file**. To handle "dead reckoning" drift from the wheels, the robot uses ultrasonic sensors to reference known walls and "nudge" its estimated position back to reality.

---

## 6. Evaluation and Success Metrics

* **Must-Have:** Autonomous movement, obstacle avoidance, YOLOv8n fire detection, and basic alarm triggering.
* **Should-Have:** Full occupancy grid mapping, sensor fusion logic, waypoint-based patrolling, and map persistence (loading map from JSON).
* **Target:** >85% detection accuracy with <10% false positives.

---

## 7. Team Structure (Module Assignments)

| Module | Key Tasks |
| :--- | :--- |
| **M1: Chassis** | Assembly, 3D parts, physical wiring. |
| **M2: Motor/Power** | L298N driver, PWM control, battery management. |
| **M3: Sensors** | GPIO/I2C drivers, MQ-2, MLX, MPU6050 calibration. |
| **M4: AI & Vision** | OpenCV pipeline, YOLOv8n training & INT8 optimization. |
| **M5: Navigation** | Wall-following, grid mapping, drift correction. |
| **M6: Decision Engine** | State machine, sensor fusion logic. |
| **M7: Data Logging** | SQLite logs, JSON export/import. |

---

## 8. Risk Analysis

* **Part Delays:** Handled by developing against pre-recorded data or simulations.
* **Pi 4 Performance:** If too slow, resolution will be lowered or FPS capped (5–10 FPS is sufficient for slow patrol).
* **False Alarms:** Mitigated by requiring multiple sensors to agree before alarming.
* **Map Drift:** Corrected using ultrasonic wall-referencing.

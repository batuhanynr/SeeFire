# M1_CHASSIS — Chassis & Mechanical Assembly

One-sentence purpose: Defines the 4WD wheeled platform structure, motor mounts (4× 6V DC geared motors), sensor mounting points, power distribution, and provides mechanical specifications for all downstream modules.

**Author:** Halil Buğra Şen (230104004088), Alperen Şahin (220104004943)  
**Module ID:** M1  
**Version:** 0.1

---

## Physical Specifications

### Chassis Platform
| Parameter | Value | Notes |
|-----------|-------|-------|
| **Length** | 200 mm | Total footprint |
| **Width** | 150 mm | Total footprint |
| **Height** | 100 mm | Body clearance |
| **Wheelbase** | 140 mm | Front-to-rear axle distance |
| **Track Width** | 120 mm | Left-to-right wheel distance |
| **SBC** | Raspberry Pi 4 | 4GB RAM variant |

### Motor System (4WD)
| Parameter | Value | Notes |
|-----------|-------|-------|
| **Motor Type** | DC 6V Geared | One per wheel |
| **Rated Voltage** | 6.0 V | Typical for hobby robots |
| **No-Load RPM** | ~100 RPM | Wheel speed control via PWM |
| **Stall Torque** | ~0.8 N⋅m | Sufficient for flat-surface navigation |
| **Wheel Diameter** | 65 mm | Compatible with motor torque |

### Power Distribution
| Component | Voltage | Current (Idle) | Current (Max) | Notes |
|-----------|---------|---|---|---|
| **Li-ion Pack (2S1P)** | 7.4 V nom. | — | 10-20 A | 2x 18650 (2600 mAh); XT60 connector |
| **Motor Controller (L298N)** | 7.4 V → 6 V | — | 2 A | Dual H-bridges for 4 motors |
| **RPi + Peripherals** | 5.0 V (regulated) | 0.5 A | 3.0 A | Separate buck converter from Li-ion |
| **Alarm System** | 5.0 V | 0.05 A | 0.5 A | LED + buzzer on 330 Ω + 100 Ω |

---

## Mechanical Assembly

### Motor Mount Layout
```
        [Front]
    FL  ─ ─ ─  FR
    ║           ║
    ═══════════   (wheelbase = 140 mm)
    ║           ║
    RL  ─ ─ ─  RR
        [Rear]

Motor IDs: 0=FL, 1=FR, 2=RL, 3=RR
```

### Sensor Mounting Points
| Sensor | Location | Offset | Mount Height | Purpose |
|--------|----------|--------|--------------|---------|
| **HC-SR04 (Center)** | Front center | 0 mm | ~50 mm | Obstacle detection |
| **HC-SR04 (Right)** | Front right corner | 45 deg angle | ~50 mm | Wall-following/Cornering |
| **HC-SR04 (Left)** | Front left corner | 45 deg angle | ~50 mm | Wall-following/Cornering |
| **MLX90614** | Top center | — | ~80 mm | IR temperature (fire detection) |
| **MQ-2** | Top-front | ±15 mm | ~60 mm | Smoke/gas sensor |
| **USB Webcam** | Front-top | ±10 mm tilt | ~90 mm | Fire/smoke vision |

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| **4× DC 6V Motors** | Hardware | Geared motors with 3 mm shaft |
| **4× Plastic Wheels** | Hardware | 65 mm diameter, friction tires |
| **Li-ion 2S Pack** | Hardware | 7.4 V / 2600 mAh (18650 cells) |
| **L298N Motor Controller** | Hardware | Dual H-bridge; supports 4 motors |
| **Motor Mounts** | Hardware | Aluminum brackets or 3D-printed |
| **Chassis Frame** | Hardware | Aluminum or acrylic base + walls |
| **Power Connectors** | Hardware | XT60 (battery), JST-XH (motor leads) |
| **M2 (Motor Control)** | Module | Controls motors via GPIO + PWM |
| **M3 (Sensors)** | Module | Mounts on defined points |
| **M5 (Navigation)** | Module | Receives sensor data from M3 |

---

## Assembly Checklist

- [ ] **Mechanical Frame**: Assemble chassis base, motor mounts, and wheel axles
- [ ] **Motor Installation**: Mount 4 DC motors (FL, FR, RL, RR) to frame
- [ ] **Wheel Attachment**: Fit wheels to motor shafts; test free spin
- [ ] **Power Connections**: Connect LiPo battery → L298N motor controller
- [ ] **Motor Wiring**: Connect L298N outputs to motor pairs (L+R per side)
- [ ] **Sensor Mounting**: Install all sensor brackets at specified offsets and heights
- [ ] **Cable Management**: Route sensor and power cables; secure with zip-ties
- [ ] **Raspberry Pi Mount**: Secure RPi on top; connect GPIO and USB peripherals
- [ ] **Pre-Power Test**: Visually inspect all connections before first power-on

---

## Quick-Start Integration Example

```c
#include "m1_chassis.h"

int main(void) {
    // Verify the assembly is complete
    if (!m1_verify_assembly()) {
        printf("ERROR: Chassis assembly incomplete or misaligned.\n");
        return -1;
    }

    // Get motor mount for front-left motor
    M1_MotorMount fl_motor = m1_get_motor_mount(0);  // Motor ID 0 = FL
    printf("FL Motor: PWM pin = %d, Dir pins = %d, %d\n",
           fl_motor.pwm_pin, fl_motor.dir_pin_a, fl_motor.dir_pin_b);

    return 0;
}
```

---

## Testing & Validation

1. **No-Load Test**: Spin each motor individually via M2 PWM at 50% duty; verify smooth rotation.
2. **Load Test**: Drive chassis forward/backward/left/right; verify equal wheel speeds.
3. **Battery Test**: Monitor voltage during motion; trigger alarm if V < 9.6 V.
4. **Sensor Calibration**: Verify sensor readings match physical positions (obstacle distance, tilt angle, etc.).

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2025-03-01 | Initial draft: physical specs, motor layout, sensor mount points |


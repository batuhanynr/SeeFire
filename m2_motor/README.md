# M2_MOTOR — Motor Control & Power Management

One-sentence purpose: Controls the L298N H-bridge to drive the 4WD chassis and manages LiPo battery monitoring, alarm LED, and buzzer.

**Author:** Bekir Emre Sarpınar (220104004039)
**Module ID:** M2  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| M1 (Chassis) | Hardware | Robot must be physically assembled before motor testing |
| LM2596 Buck Converter | Hardware | **CRITICAL:** Steps down LiPo to 5V to safely power the Raspberry Pi, isolating it from motor voltage drops |
| RPi.GPIO ≥ 0.7.1 | Python package | `sudo apt install python3-rpi.gpio` |
| `time` (stdlib) | Python package | PWM timing |

---

## Quick-Start Integration Example

```c
#include "m2_motor.h"

int main(void) {
    // Initialise GPIO and PWM
    if (m2_init_motors() != M2_OK) {
        return -1;
    }

    // Drive forward at 70% speed
    m2_motor_drive(M2_DIR_FORWARD, 70);

    // Check battery
    float voltage;
    m2_get_battery_voltage(&voltage);
    if (voltage < M2_BATTERY_LOW_V) {
        m2_blink_led(M2_BLINK_SLOW);
    }

    // Turn 90 degrees clockwise
    m2_motor_turn(90.0f, 80);

    // Stop and trigger alarm
    m2_motor_stop();
    m2_set_alarm(true, true);

    // Cleanup
    m2_cleanup();
    return 0;
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m2_init_motors()` | — | `m2_status_t` | Call first; sets up GPIO/PWM |
| `m2_motor_drive(direction, speed)` | `m2_direction_t`, `uint8_t` | `m2_status_t` | Speed 0–100 % |
| `m2_motor_stop()` | — | `m2_status_t` | Zero duty cycle |
| `m2_motor_turn(angle_deg, speed)` | `float`, `uint8_t` | `m2_status_t` | Timed differential drive |
| `m2_get_battery_voltage(voltage_out)` | `float *` | `m2_status_t` | Returns volts via ADC |
| `m2_set_alarm(led_on, buzzer_on)` | `bool`, `bool` | `m2_status_t` | Activates GPIO 26 / 19 |
| `m2_blink_led(pattern)` | `m2_blink_pattern_t` | `m2_status_t` | Non-blocking background thread |
| `m2_get_state(state_out)` | `m2_state_t *` | `m2_status_t` | Snapshot of current state |
| `m2_cleanup()` | — | `m2_status_t` | Releases GPIO resources |

---

## Known Limitations & TODOs

- Battery ADC requires a hardware voltage divider on the LiPo output; exact resistor values must be confirmed with M1.
- PWM frequency is fixed at 1 kHz; dynamic adjustment not yet supported.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: motor_drive, motor_stop, motor_turn, set_alarm, blink_led |

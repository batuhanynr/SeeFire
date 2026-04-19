# M3_SENSORS — Sensor Integration Hub

One-sentence purpose: Drivers and calibration for MQ-2, MLX90614, and HC-SR04 (×2); exposes a unified fusion API for M6 and a navigation API for M5.

**Author:** Alperen Şahin (220104004943), Bekir Emre Sarpınar (220104004039), Batuhan Yanar (220104004059)  
**Module ID:** M3  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| M1 (Chassis) | Hardware | Sensors must be physically mounted first |
| Logic Level Converter | Hardware | **CRITICAL:** Steps down 5V lines (HC-SR04 ECHO) to 3.3V to protect Pi GPIO pins |
| MCP3208/MCP3008 ADC | Hardware | **CRITICAL:** Raspberry Pi has no analog inputs. MQ-2 analog pin MUST connect via SPI ADC to get true 0-1023 smoke readings, not digital thresholds. |
| I2C Wiring Constraint | Hardware | I2C jumper wires (MLX90614) must stay < 15-20cm to prevent signal loss/lockup. Wrap reads in `try-except`. |
| RPi.GPIO ≥ 0.7.1 | Python package | HC-SR04 GPIO |
| spidev | Python package | SPI communication for ADC |
| smbus2 ≥ 0.4.1 | Python package | I2C for MLX90614 |
| adafruit-circuitpython-mlx90614 | Python package | IR temperature driver |
| I2C enabled on RPi OS | OS config | `sudo raspi-config → Interfaces → I2C` |

---

## Quick-Start Integration Example

```c
#include "m3_sensors.h"

int main(void) {
    if (m3_init_sensors() != M3_OK) {
        return -1;
    }

    // --- M6 usage: read fire-detection sensors ---
    m3_fusion_data_t fusion;
    if (m3_get_fusion_sensors(&fusion) == M3_OK) {
        if (fusion.smoke_alert || fusion.ir_temp > 60.0f) {
            // Hand off to M6 decision engine
        }
    }

    // --- M5 usage: read navigation sensors ---
    m3_nav_data_t nav;
    if (m3_get_navigation_sensors(&nav) == M3_OK) {
        float left  = nav.ultrasonic.left_cm;
        float right = nav.ultrasonic.right_cm;
        // Feed into wall-following algorithm
    }

    m3_cleanup();
    return 0;
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m3_init_sensors()` | — | `m3_status_t` | Initialises all 5 sensors |
| `m3_set_smoke_threshold(threshold)` | `int32_t` | `m3_status_t` | Default: 300 |
| `m3_set_ir_temp_threshold(threshold_c)` | `float` | `m3_status_t` | Default: 60.0 °C |
| `m3_get_fusion_sensors(data_out)` | `m3_fusion_data_t *` | `m3_status_t` | Called by M6 ~500 ms |
| `m3_get_ultrasonic_distances(data_out)` | `m3_ultrasonic_t *` | `m3_status_t` | Called by M5 ~100 ms |
| `m3_get_navigation_sensors(data_out)` | `m3_nav_data_t *` | `m3_status_t` | Ultrasonic in one call |
| `m3_cleanup()` | — | `m3_status_t` | Releases GPIO and I2C |

---

## Known Limitations & TODOs

- MQ-2 requires a warm-up period (~60 s) before readings are stable; cold-start readings should be discarded.
- MCP3208 ADC SPI wiring for MQ-2 must be confirmed with M1 before final integration.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: all sensor drivers, fusion API, navigation API |

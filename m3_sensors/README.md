# M3 Sensors

Current purpose: provide unified sensor access for fire-detection inputs and navigation inputs.

## Live Sensors

- MQ-2 smoke/gas via ADC
- MLX90614 IR thermometer
- HC-SR04 x3
  - `left`
  - `front`
  - `right`

## Public Data Shapes

- `FusionData`
  - `smoke_level`
  - `smoke_alert`
  - `ir_temp`
  - `timestamp`
- `NavData`
  - `left_cm`
  - `front_cm`
  - `right_cm`
  - `timestamp`

`NavData.center_cm` still exists as a compatibility alias for older code/tests, but new code should use `front_cm`.

## Notes

- MQ-2 warm-up is respected outside mock mode
- `get_navigation_sensors_filtered()` applies a median filter
- Mock mode is supported when Raspberry Pi libraries are unavailable

Older README text that described only two ultrasonics or wall-following consumers is obsolete.

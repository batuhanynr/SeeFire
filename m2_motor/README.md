# M2 Motor & Power

Current purpose: low-level actuation, alarm I/O, battery-voltage readout, and encoder-backed distance helpers for M5.

## Implemented Today

- `init_hardware()`
- `motor_drive()`
- `motor_turn()`
- `motor_stop()`
- `set_alarm()`
- `get_battery_voltage()`
- `drive_distance_cm()`
- `turn_left_90()`
- `turn_right_90()`
- `stop()`
- `get_total_distance_cm()`
- `set_total_distance_cm()`

## Notes

- Battery monitoring assumes a 2S pack and the divider constants in `config.py`
- Mock mode is supported when `RPi.GPIO` is unavailable
- Encoder counts are used for distance accumulation; turns are still time-based

Older README text that only described the original C-style header API is incomplete relative to the live Python module.

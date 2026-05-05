from .motor import (
    init_hardware,
    motor_drive,
    motor_turn,
    motor_stop,
    set_alarm,
    get_battery_voltage,
    drive_distance_cm,
    turn_left_90,
    turn_right_90,
    stop,
    get_total_distance_cm,
)
from .motor import _instance as _motor_instance


def set_total_distance_cm(value: float) -> None:
    _motor_instance.set_total_distance_cm(value)

__all__ = [
    "init_hardware", "motor_drive", "motor_turn", "motor_stop",
    "set_alarm", "get_battery_voltage",
    "drive_distance_cm", "turn_left_90", "turn_right_90", "stop",
    "get_total_distance_cm", "set_total_distance_cm",
]

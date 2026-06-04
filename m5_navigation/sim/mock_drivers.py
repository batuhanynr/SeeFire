"""Install sim-backed mock drivers into m2_motor, m3_sensors, m4_vision.

This bypasses the modules' own mock-mode (which returns random/fixed values)
with deterministic readings derived from the World's geometry. NavigationController
then runs unchanged on top.
"""
import time
import m2_motor
import m3_sensors
import m4_vision

from m3_sensors.sensors import NavData


def install_mock_drivers(world):
    """Patch motor/sensor module-level functions to read/write `world`."""

    # ----- m2_motor -----
    m2_motor.drive_distance_cm    = world.drive_distance_cm
    m2_motor.turn_left_90         = world.turn_left_90
    m2_motor.turn_right_90        = world.turn_right_90
    m2_motor.stop                 = world.stop
    m2_motor.get_total_distance_cm = world.get_total_distance_cm
    m2_motor.set_total_distance_cm = world.set_total_distance_cm

    # ----- m3_sensors -----
    def _read():
        l, f, r = world.sensor_readings()
        return NavData(left_cm=l, front_cm=f, right_cm=r, timestamp=time.time())

    def _filtered(samples: int = 3):
        # World is deterministic; samples doesn't change result.
        return _read()

    m3_sensors.get_navigation_sensors          = _read
    m3_sensors.get_navigation_sensors_filtered = _filtered

    def _front(samples: int = 2):
        _, f, _ = world.sensor_readings()
        return f

    m3_sensors.get_front_distance = _front

    # ----- m4_vision -----
    m4_vision.determine_turn_direction = lambda frame=None: world.turn_hint
    m4_vision.capture_frame            = lambda: None
    m4_vision.close                    = lambda: None
    m4_vision.init                     = lambda: None

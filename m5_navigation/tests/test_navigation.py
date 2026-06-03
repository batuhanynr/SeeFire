import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure SeeFire is in path for imports
sys.path.insert(0, os.path.join(os.getcwd(), "SeeFire"))

import config
from m5_navigation.position import PositionVerifier
from m5_navigation.obstacle import ObstacleAvoidance, ObstacleBlockedError

def test_position_verifier_start_ok():
    """Verify start when sensors are within tolerance."""
    # Mock return value for get_navigation_sensors_filtered
    mock_reading = MagicMock()
    mock_reading.left_cm = config.START_LEFT_CM + 1.0
    mock_reading.right_cm = config.START_RIGHT_CM - 1.0
    
    with patch('m3_sensors.get_navigation_sensors_filtered', return_value=mock_reading):
        pv = PositionVerifier()
        # Should not raise any error
        pv.verify_start()

@patch('m2_motor.turn_right_90')
@patch('time.sleep')
def test_position_verifier_start_aligns_when_off_center(mock_sleep, mock_turn):
    """Verify start spins the robot in place when off-center, then stops when aligned."""
    mock_reading_off = MagicMock(left_cm=45.0, right_cm=30.0) # diff = 15.0 > 10.0
    mock_reading_on = MagicMock(left_cm=30.0, right_cm=30.0)  # diff = 0.0 <= 10.0

    with patch('m3_sensors.get_navigation_sensors_filtered', side_effect=[mock_reading_off, mock_reading_on]):
        pv = PositionVerifier()
        pv.verify_start()

        # Should have turned right once to align
        mock_turn.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)

def test_obstacle_avoidance_direction_decision():
    """Verify that avoidance uses camera hint first, then ultrasonic."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)
    
    # 1. Camera says LEFT
    with patch('m4_vision.determine_turn_direction', return_value="LEFT"):
        assert oa._decide_direction() == "LEFT"
        
    # 2. Camera says NONE, ultrasonic says RIGHT is clearer
    mock_reading = MagicMock()
    mock_reading.left_cm = 20.0
    mock_reading.right_cm = 50.0 # Right has more space
    
    with patch('m4_vision.determine_turn_direction', return_value=None), \
         patch('m3_sensors.get_navigation_sensors_filtered', return_value=mock_reading):
        assert oa._decide_direction() == "RIGHT"

@patch('m2_motor.get_total_distance_cm', return_value=150.0)
@patch('m2_motor.motor.MotorM2.set_total_distance_cm')
@patch('m2_motor.motor.MotorM2.motor_turn')
@patch('m2_motor.motor.MotorM2.motor_drive')
def test_avoidance_maneuver_flow(mock_drive, mock_turn, mock_set_dist, mock_get_dist):
    """Verify the sequence of motor commands during an avoidance maneuver."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)
    
    # Mock camera to force RIGHT
    with patch('m4_vision.determine_turn_direction', return_value="RIGHT"):
        # Mock the whole bypass attempt: 10 cm side + 20 cm forward.
        with patch.object(ObstacleAvoidance, '_attempt_bypass',
                          return_value=(10.0, 20.0)):
            oa.avoid(sector_id=1, reference_distance=15.0)

            # New design: lateral moves roll back the encoder per step inside
            # _attempt_bypass / _return_to_route. avoid() itself doesn't touch
            # set_total_distance_cm; we just verify the flow ran to completion.
            pv.verify_and_correct.assert_called_once()


@patch('m2_motor.get_total_distance_cm', return_value=150.0)
@patch('m2_motor.motor.MotorM2.set_total_distance_cm')
@patch('m2_motor.motor.MotorM2.motor_turn')
@patch('m2_motor.motor.MotorM2.motor_drive')
def test_avoidance_retries_on_wall_hit(mock_drive, mock_turn, mock_set_dist, mock_get_dist):
    """First side blocked by wall → robot retreats and tries the other side."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)

    # First attempt: wall hit (None). Second: side=10, forward=20.
    attempts = [None, (10.0, 20.0)]

    with patch('m4_vision.determine_turn_direction', return_value="RIGHT"), \
         patch.object(ObstacleAvoidance, '_attempt_bypass',
                      side_effect=attempts) as mock_attempt:
        oa.avoid(sector_id=1, reference_distance=15.0)

        assert mock_attempt.call_count == 2
        # Second attempt should be from the opposite side (LEFT).
        assert mock_attempt.call_args_list[1].args[1] == "LEFT"
        pv.verify_and_correct.assert_called_once()


@patch('m2_motor.get_total_distance_cm', return_value=150.0)
@patch('m2_motor.motor.MotorM2.set_total_distance_cm')
@patch('m2_motor.motor.MotorM2.motor_turn')
@patch('m2_motor.motor.MotorM2.motor_drive')
def test_avoidance_aborts_when_both_sides_blocked(mock_drive, mock_turn,
                                                  mock_set_dist, mock_get_dist):
    """Both directions hit walls → ObstacleBlockedError is raised."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)

    with patch('m4_vision.determine_turn_direction', return_value="RIGHT"), \
         patch.object(ObstacleAvoidance, '_attempt_bypass', return_value=None):
        with pytest.raises(ObstacleBlockedError):
            oa.avoid(sector_id=1, reference_distance=15.0)


def test_side_pass_clears_at_dynamic_threshold():
    """Clearance check uses D₀ + OBSTACLE_CLEARANCE_DELTA_CM, not a fixed value."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)

    # D₀ = 15 → threshold = 30. Two readings: first below, second above.
    reading_blocked = MagicMock(left_cm=20.0, right_cm=99.0, front_cm=99.0)
    reading_clear   = MagicMock(left_cm=35.0, right_cm=99.0, front_cm=99.0)

    with patch('m3_sensors.get_navigation_sensors_filtered',
               side_effect=[reading_blocked, reading_clear]), \
         patch('m2_motor.drive_distance_cm'):
        traveled, wall_hit = oa._side_pass(
            sector_id=1, direction="RIGHT", reference_distance=15.0
        )
        assert wall_hit is False
        assert traveled == config.SIDE_STEP_CM * 2   # one step taken before clear, plus one extra safety step
 

def test_forward_pass_clears_when_side_sensor_passes_obstacle():
    """After turning back north, the side sensor pointing at the obstacle
    must exceed D₀ + delta before the forward-pass returns."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)

    # RIGHT bypass: after turning back to north, obstacle is to our WEST → left.
    reading_alongside = MagicMock(left_cm=10.0, right_cm=99.0, front_cm=99.0)
    reading_past      = MagicMock(left_cm=40.0, right_cm=99.0, front_cm=99.0)

    with patch('m3_sensors.get_navigation_sensors_filtered',
               side_effect=[reading_alongside, reading_past]), \
         patch('m2_motor.drive_distance_cm'):
        forward = oa._forward_pass_obstacle(
            sector_id=1, direction="RIGHT", reference_distance=15.0
        )
        # One step taken before the second reading cleared, plus three extra safety steps
        assert forward == config.STEP_DISTANCE_CM * 4


def test_verify_and_correct_skips_when_corridor_width_mismatches():
    """Two-sensor sanity gate must skip correction when left+right ≠ expected
    corridor width (e.g. a column is partially blocking one sensor)."""
    # Expected sum = START_LEFT_CM + START_RIGHT_CM. We make it 22 cm off to force skip.
    mock_reading = MagicMock(
        left_cm=config.START_LEFT_CM - 15.0,
        right_cm=config.START_RIGHT_CM - 7.0
    )

    with patch('m3_sensors.get_navigation_sensors_filtered',
               return_value=mock_reading), \
          patch('m2_motor.turn_right_90') as mock_turn_r, \
          patch('m2_motor.turn_left_90') as mock_turn_l, \
          patch('m2_motor.drive_distance_cm') as mock_drive:
        pv = PositionVerifier()
        pv.verify_and_correct()
        # No motor commands issued — correction was skipped.
        mock_turn_r.assert_not_called()
        mock_turn_l.assert_not_called()
        mock_drive.assert_not_called()


def test_verify_and_correct_applies_when_width_consistent():
    """If left+right is within tolerance and left_err is large, correct."""
    # Sum is exactly consistent (START_LEFT_CM + START_RIGHT_CM), left_err = +6.0 > tolerance(5)
    mock_reading = MagicMock(
        left_cm=config.START_LEFT_CM + 6.0,
        right_cm=config.START_RIGHT_CM - 6.0
    )

    with patch('m3_sensors.get_navigation_sensors_filtered',
               return_value=mock_reading), \
          patch('m2_motor.turn_right_90') as mock_turn_r, \
          patch('m2_motor.turn_left_90') as mock_turn_l, \
          patch('m2_motor.drive_distance_cm') as mock_drive:
        pv = PositionVerifier()
        pv.verify_and_correct()
        # left_err = +6 > tolerance(5) → rightward correction
        mock_turn_r.assert_called_once()
        mock_drive.assert_called_once_with(config.FINE_TUNE_STEP_CM)
        mock_turn_l.assert_called_once()


def test_drive_lateral_preserves_north_progress():
    """Lateral drives must not pollute the north-progress encoder reading."""
    with patch('m2_motor.get_total_distance_cm', return_value=42.0), \
         patch('m2_motor.drive_distance_cm') as mock_drive, \
         patch('m2_motor.set_total_distance_cm') as mock_set:
        ObstacleAvoidance._drive_lateral(7.0)
        mock_drive.assert_called_once_with(7.0)
        mock_set.assert_called_once_with(42.0)


def test_four_direction_scan_captures_each_heading():
    """360° tarama 4 snapshot (K/D/G/B) ve 4 sağa dönüş yapar."""
    from m5_navigation.navigation import NavigationController

    captured = []
    with patch('m2_motor.stop'), \
         patch('m2_motor.turn_right_90') as mock_turn, \
         patch('time.sleep'):
        nc = NavigationController(snapshot_callback=lambda lbl: captured.append(lbl))
        nc._scan_360(segment_id=1)

    assert captured == [
        "seg1-K",
        "seg1-D",
        "seg1-G",
        "seg1-B",
    ]
    assert mock_turn.call_count == 4   # 4×90° = tam tur


def test_side_pass_detects_wall_via_front_sensor():
    """Wall detection during side-pass uses front_cm, not the rear sensor."""
    pv = MagicMock()
    oa = ObstacleAvoidance(pv)

    reading_wall = MagicMock(
        left_cm=10.0,                              # still seeing obstacle
        right_cm=99.0,
        front_cm=config.WALL_CLEARANCE_CM - 1.0,   # wall ahead
    )

    with patch('m3_sensors.get_navigation_sensors_filtered',
               return_value=reading_wall), \
         patch('m2_motor.drive_distance_cm'):
        traveled, wall_hit = oa._side_pass(
            sector_id=1, direction="RIGHT", reference_distance=15.0
        )
        assert wall_hit is True
        assert traveled == 0.0


def test_drive_segment_stops_at_target():
    """_drive_segment SEGMENT_CM kadar ilerleyip durduğunu doğrular."""
    from m5_navigation.navigation import NavigationController, SEGMENT_CM
    import m2_motor

    nc = NavigationController()
    m2_motor.set_total_distance_cm(0.0)

    mock_sensor_reading = MagicMock()
    mock_sensor_reading.front_cm = 100.0
    mock_sensor_reading.left_cm  = 200.0
    mock_sensor_reading.right_cm = 200.0

    # Encoder: önce 0, sonra SEGMENT_CM'e ulaş
    measured_distances = [0.0, SEGMENT_CM, SEGMENT_CM]

    with patch('m3_sensors.get_navigation_sensors_filtered',
               return_value=mock_sensor_reading), \
         patch('m2_motor.get_measured_distance_cm',
               side_effect=measured_distances), \
         patch('m2_motor.reset_encoder_window'), \
         patch('m2_motor.motor_drive') as mock_drive, \
         patch('m2_motor.stop') as mock_stop, \
         patch('m2_motor.set_total_distance_cm'), \
         patch('time.sleep'):

        nc._drive_segment(segment_id=1)

        # Forward sürüş başlatılmış olmalı
        mock_drive.assert_called_with("forward", config.DRIVE_SPEED)
        # Motor durdurulmuş olmalı
        mock_stop.assert_called()


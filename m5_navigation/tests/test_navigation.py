import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure SeeFire is in path for imports
sys.path.insert(0, os.path.join(os.getcwd(), "SeeFire"))

import config
from m5_navigation.position import PositionVerifier
from m5_navigation.obstacle import ObstacleAvoidance

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

def test_position_verifier_start_fails():
    """Verify start fails when sensors are outside tolerance."""
    mock_reading = MagicMock()
    mock_reading.left_cm = config.START_LEFT_CM + config.POSITION_TOLERANCE_CM + 1.0
    mock_reading.right_cm = config.START_RIGHT_CM
    
    with patch('m3_sensors.get_navigation_sensors_filtered', return_value=mock_reading):
        pv = PositionVerifier()
        with pytest.raises(RuntimeError) as excinfo:
            pv.verify_start()
        assert "Start position out of tolerance" in str(excinfo.value)

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
        # Mock side_pass to simulate clearing the obstacle after 10cm
        with patch.object(ObstacleAvoidance, '_side_pass', return_value=10.0):
            oa.avoid(sector_id=1)
            
            # Verify odometry was restored
            mock_set_dist.assert_called_with(150.0)
            # Verify fine-tuning was called
            pv.verify_and_correct.assert_called_once()


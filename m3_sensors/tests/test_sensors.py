import pytest
from unittest.mock import patch, MagicMock
from m3_sensors import sensors

# M3 tests updated for Raspberry Pi 4 Safe Mode
# Removed: MPU6050 and DHT22 hardware logic

def test_sensor_init():
    with patch('RPi.GPIO.setmode') as mock_setmode, \
         patch('RPi.GPIO.setup') as mock_setup:
        assert sensors.init_sensors() == True
        mock_setmode.assert_called_once()
        assert mock_setup.call_count >= 4

def test_get_fusion_sensors():
    with patch.object(sensors._instance, '_read_mcp3008', return_value=150) as mock_adc:
        fusion_data = sensors.get_fusion_sensors()
        assert fusion_data.smoke_level == 150
        assert type(fusion_data.smoke_alert) is bool
        assert fusion_data.ir_temp >= 0.0

def test_get_navigation_sensors():
    # Mocking 3 sensor readings: left, center, right
    with patch.object(sensors._instance, '_read_ultrasonic', side_effect=[15.0, 45.0, 20.0]):
        nav_data = sensors.get_navigation_sensors()
        assert nav_data.left_cm == 15.0
        assert nav_data.center_cm == 45.0
        assert nav_data.right_cm == 20.0

from unittest.mock import patch
from m3_sensors import sensors

# M3 tests updated for Raspberry Pi 4 Safe Mode
# Removed: MPU6050 and DHT22 hardware logic

def test_sensor_init():
    if sensors.MOCK_MODE:
        assert sensors.init_sensors() == True
        return

    with patch('m3_sensors.sensors.GPIO.setmode') as mock_setmode, \
         patch('m3_sensors.sensors.GPIO.setup') as mock_setup:
        assert sensors.init_sensors() == True
        mock_setmode.assert_called_once()
        assert mock_setup.call_count >= 4

def test_get_fusion_sensors():
    with patch.object(sensors._instance, '_read_mcp3208', return_value=150):
        fusion_data = sensors.get_fusion_sensors()
        assert fusion_data.smoke_level == 150
        assert type(fusion_data.smoke_alert) is bool
        assert fusion_data.ir_temp >= 0.0

def test_get_navigation_sensors():
    # Mocking 3 sensor readings: left, front, right
    with patch.object(sensors._instance, '_read_ultrasonic', side_effect=[15.0, 45.0, 20.0]):
        nav_data = sensors.get_navigation_sensors()
        assert nav_data.left_cm == 15.0
        assert nav_data.front_cm == 45.0
        assert nav_data.center_cm == 45.0
        assert nav_data.right_cm == 20.0

def test_mlx_failure_disables_sensor():
    """MLX90614 exception logs warning and sets _mlx_sensor to None."""
    s = sensors.SensorsM3()
    s._mlx_sensor = True
    s._bus = True

    with patch('m3_sensors.sensors.MOCK_MODE', False), \
         patch.object(s, '_read_mlx90614_celsius',
                      side_effect=OSError("I2C timeout")), \
         patch.object(s, '_read_mcp3208', return_value=0):
        result = s.get_fusion_sensors()
        assert s._mlx_sensor is None
        assert result.ir_temp == 25.0  # fallback value

def test_mlx_failure_stays_disabled():
    """After MLX fails, subsequent calls skip without retrying."""
    s = sensors.SensorsM3()
    s._mlx_sensor = None
    s._bus = True

    with patch('m3_sensors.sensors.MOCK_MODE', False), \
         patch.object(s, '_read_mlx90614_celsius') as mock_read, \
         patch.object(s, '_read_mcp3208', return_value=0):
        result = s.get_fusion_sensors()
        mock_read.assert_not_called()
        assert result.ir_temp == 25.0

def test_mock_ultrasonic_deterministic():
    """Mock ultrasonic returns consistent values for same conditions."""
    from m3_sensors.sensors import _RNG
    seed_before = _RNG.getstate()
    v1 = sensors._instance._read_ultrasonic(1, 2)
    _RNG.setstate(seed_before)
    v2 = sensors._instance._read_ultrasonic(1, 2)
    assert v1 == v2

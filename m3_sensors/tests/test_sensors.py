import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
import m3_sensors
import m3_sensors.sensors as _m3


def setup_module():
    _m3._init_time = None
    _m3._i2c_bus = None
    _m3._spi = None
    _m3._mlx_sensor = None
    _m3._dht_sensor = None
    _m3._mpu_sensor = None
    _m3._yaw_raw = 0.0


def _mock_init():
    _m3._init_time = time.time() - 120
    _m3._i2c_bus = MagicMock()
    _m3._spi = MagicMock()


def test_fusion_data_t_fields():
    data = m3_sensors.m3_fusion_data_t(
        smoke_level=100, ir_temp=45.0,
        ambient_temp=22.5, ambient_humidity=55.0,
        timestamp="2026-04-18T10:00:00Z",
    )
    assert data.smoke_level == 100
    assert data.ir_temp == 45.0
    assert data.ambient_temp == 22.5
    assert data.ambient_humidity == 55.0


def test_nav_data_t_fields():
    data = m3_sensors.m3_nav_data_t(
        dist_left=30.5, dist_right=25.0, yaw=90.0,
        timestamp="2026-04-18T10:00:00Z",
    )
    assert data.dist_left == 30.5
    assert data.dist_right == 25.0
    assert data.yaw == 90.0


def test_read_mq2_with_spi_mock():
    _mock_init()
    _m3._spi.xfer2.return_value = [0, 0b0000_0011, 0b1111_1111]
    result = m3_sensors.read_mq2()
    assert result == 1023


def test_read_mq2_no_spi():
    _m3._spi = None
    assert m3_sensors.read_mq2() == 0


def test_read_mlx90614_uses_reused_sensor():
    _mock_init()
    mock_mlx = MagicMock()
    mock_mlx.object_temperature = 37.5
    _m3._mlx_sensor = mock_mlx
    result = m3_sensors.read_mlx90614()
    assert result == 37.5


def test_read_mlx90614_i2c_fallback():
    _mock_init()
    _m3._mlx_sensor = None
    _m3._i2c_bus.read_i2c_block_data.return_value = [0x00, 0x4B, 0x00]
    result = m3_sensors.read_mlx90614()
    assert result > 0


def test_read_mlx90614_no_i2c():
    _m3._i2c_bus = None
    _m3._mlx_sensor = None
    assert m3_sensors.read_mlx90614() == 25.0


def test_read_dht22_uses_reused_sensor():
    mock_dht = MagicMock()
    mock_dht.temperature = 23.0
    mock_dht.humidity = 55.0
    _m3._dht_sensor = mock_dht
    temp, humidity = m3_sensors.read_dht22()
    assert temp == 23.0
    assert humidity == 55.0


def test_read_dht22_no_sensor():
    _m3._dht_sensor = None
    temp, humidity = m3_sensors.read_dht22()
    assert temp == 25.0
    assert humidity == 50.0


def test_read_dht22_read_failure():
    mock_dht = MagicMock()
    mock_dht.temperature = None
    _m3._dht_sensor = mock_dht
    temp, humidity = m3_sensors.read_dht22()
    assert temp == 25.0


def test_read_mpu6050_uses_reused_sensor():
    _mock_init()
    mock_mpu = MagicMock()
    mock_mpu.get_gyro_data.return_value = {"z": 10.0}
    _m3._mpu_sensor = mock_mpu
    _m3._yaw_raw = 0.0
    yaw = m3_sensors.read_mpu6050_yaw()
    assert isinstance(yaw, float)


def test_read_mpu6050_no_sensor():
    _m3._mpu_sensor = None
    assert m3_sensors.read_mpu6050_yaw() == 0.0


def test_read_hcsr04_mock():
    mock_gpio = MagicMock()
    mock_gpio.input.side_effect = [0, 1, 1, 0]
    with patch.dict("sys.modules", {"RPi": MagicMock(), "RPi.GPIO": mock_gpio}):
        mock_gpio.IN = 1
        mock_gpio.OUT = 0
        dist = m3_sensors.read_hcsr04(23, 24)
    assert isinstance(dist, float)


def test_get_fusion_sensors():
    _mock_init()
    with patch.object(_m3, "read_mq2", return_value=150), \
         patch.object(_m3, "read_mlx90614", return_value=42.5), \
         patch.object(_m3, "read_dht22", return_value=(24.0, 60.0)):
        data = m3_sensors.get_fusion_sensors()
    assert data.smoke_level == 150
    assert data.ir_temp == 42.5
    assert data.ambient_temp == 24.0
    assert data.ambient_humidity == 60.0
    assert data.timestamp != ""


def test_get_navigation_sensors():
    _mock_init()
    with patch.object(_m3, "read_hcsr04", side_effect=[30.0, 25.0]), \
         patch.object(_m3, "read_mpu6050_yaw", return_value=90.0):
        data = m3_sensors.get_navigation_sensors()
    assert data.dist_left == 30.0
    assert data.dist_right == 25.0
    assert data.yaw == 90.0


def test_is_mq2_ready_before_warmup():
    _m3._init_time = time.time()
    assert m3_sensors.is_mq2_ready() is False


def test_is_mq2_ready_after_warmup():
    _m3._init_time = time.time() - 120
    assert m3_sensors.is_mq2_ready() is True


def test_is_mq2_ready_no_init():
    _m3._init_time = None
    assert m3_sensors.is_mq2_ready() is False


def test_concurrent_fusion_reads():
    _mock_init()
    errors = []
    barrier = threading.Barrier(5)

    def reader(tid):
        try:
            barrier.wait(timeout=2)
            with patch.object(_m3, "read_mq2", return_value=tid), \
                 patch.object(_m3, "read_mlx90614", return_value=25.0), \
                 patch.object(_m3, "read_dht22", return_value=(20.0, 50.0)):
                m3_sensors.get_fusion_sensors()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(errors) == 0, f"Concurrent read errors: {errors}"

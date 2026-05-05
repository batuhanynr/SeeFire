from unittest.mock import patch
from m2_motor import motor

def test_motor_init():
    if motor.MOCK_MODE:
        assert motor.init_hardware() == True
        return

    with patch('m2_motor.motor.GPIO.setmode'), \
         patch('m2_motor.motor.GPIO.setup'), \
         patch('m2_motor.motor.GPIO.PWM'):
        assert motor.init_hardware() == True

def test_battery_voltage():
    if motor.MOCK_MODE:
        old_v = motor._instance.mock_battery_v
        motor._instance.mock_battery_v = 7.5
        try:
            voltage = motor.get_battery_voltage()
            assert 7.0 <= voltage <= 8.0
        finally:
            motor._instance.mock_battery_v = old_v
        return

    # Using 2S Li-ion logic: ADC 2047 (~2.5V after divider -> 7.5V battery)
    with patch('m3_sensors.sensors.read_battery_adc', return_value=2047):
        voltage = motor.get_battery_voltage()
        assert 7.0 <= voltage <= 8.0

def test_battery_voltage_can_drop_to_critical_range():
    if motor.MOCK_MODE:
        old_v = motor._instance.mock_battery_v
        motor._instance.mock_battery_v = 6.5
        try:
            voltage = motor.get_battery_voltage()
            assert voltage <= 6.6
        finally:
            motor._instance.mock_battery_v = old_v
        return

    with patch('m3_sensors.sensors.read_battery_adc', return_value=1770):  # ~6.5V
        voltage = motor.get_battery_voltage()
        assert voltage <= 6.6

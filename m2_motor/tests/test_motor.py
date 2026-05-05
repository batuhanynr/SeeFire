import pytest
from unittest.mock import patch
from m2_motor import motor

def test_motor_init():
    with patch('RPi.GPIO.setmode'), \
         patch('RPi.GPIO.setup'), \
         patch('RPi.GPIO.PWM'):
        assert motor.init_hardware() == True

def test_battery_voltage():
    # Mocking ADC readout (MCP3208) for battery calculation
    # Using 2S Li-ion logic: ADC 2047 (~2.5V after divider -> 7.5V battery)
    with patch('m3_sensors.sensors.read_battery_adc', return_value=2047):
        voltage = motor.get_battery_voltage()
        assert 7.0 <= voltage <= 8.0

def test_battery_status():
    with patch('m3_sensors.sensors.read_battery_adc', return_value=1770): # ~6.5V
        status = motor.get_battery_status()
        assert status["critical"] == True


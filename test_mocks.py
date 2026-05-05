import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG)

# import modules
from m3_sensors import sensors
from m2_motor import motor

print("\n=== SEEFIRE MOCK TEST ===")
print("\n--- 1. Initalizing Modules ---")
sensors.init_sensors()
motor.init_hardware()

print("\n--- 2. Testing M3 (Sensors) ---")
nav_data = sensors.get_navigation_sensors()
print(
    f"Navigation Data: Left={nav_data.left_cm:.2f}cm, "
    f"Front={nav_data.front_cm:.2f}cm, Right={nav_data.right_cm:.2f}cm"
)

fusion_data = sensors.get_fusion_sensors()
print(f"Fusion Data: Smoke Level={fusion_data.smoke_level}, IR Temp={fusion_data.ir_temp}C, Alert={fusion_data.smoke_alert}")

print("\n--- 3. Testing M2 (Motor & Power) ---")
motor.motor_drive("forward", 80)
motor.motor_turn(45, 50)
motor.set_alarm(led=True, buzzer=False)

battery_v = motor.get_battery_voltage()
print(f"Battery Voltage via ADC: {battery_v}V")
print("=========================\n")

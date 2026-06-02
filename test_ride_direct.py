#!/usr/bin/env python3
"""
SeeFire - Direct Wheel Test (Isolated from SSH Keyboard Latency)
Drives the wheels forward at 50% speed for 3 seconds, then stops.
"""
import sys
import os
import time

# Ensure current folder is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    print("RPi.GPIO not found. Running in MOCK MODE.")
    MOCK_MODE = True

def main():
    if MOCK_MODE:
        print("[MOCK] Motors starting at 50% speed forward...")
        time.sleep(3)
        print("[MOCK] Motors stopped.")
        return

    print("Initializing GPIO...")
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup pins
    pins = [
        config.MOTOR_IN1,
        config.MOTOR_IN2,
        config.MOTOR_IN3,
        config.MOTOR_IN4,
        config.MOTOR_ENA,
        config.MOTOR_ENB
    ]
    
    for pin in pins:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    # Start PWM at 1000Hz, 50% duty cycle
    pwm_a = GPIO.PWM(config.MOTOR_ENA, 1000)
    pwm_b = GPIO.PWM(config.MOTOR_ENB, 1000)
    
    pwm_a.start(50)
    pwm_b.start(50)

    # Forward direction
    GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN2, GPIO.LOW)
    GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN4, GPIO.LOW)

    print("SUCCESS: Motors running forward at 50% PWM!")
    print("Running for 3 seconds... Stand clear.")
    time.sleep(3)

    print("Stopping motors...")
    pwm_a.stop()
    pwm_b.stop()
    GPIO.cleanup()
    print("Cleaned up GPIO. Test complete.")

if __name__ == "__main__":
    main()

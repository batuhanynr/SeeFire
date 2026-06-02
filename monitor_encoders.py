#!/usr/bin/env python3
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO not found.")
    sys.exit(1)

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Configure pins as input with pull-down
    GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    print(f"Monitoring Raw Pin States (Ctrl+C to quit)...")
    print(f"Left Encoder (BCM {config.ENCODER_LEFT_PIN} / Pin 31)")
    print(f"Right Encoder (BCM {config.ENCODER_RIGHT_PIN} / Pin 26)")
    print("--------------------------------------------------")
    
    try:
        while True:
            left_val = GPIO.input(config.ENCODER_LEFT_PIN)
            right_val = GPIO.input(config.ENCODER_RIGHT_PIN)
            
            # Print current state
            sys.stdout.write(f"\rLeft: {left_val} | Right: {right_val}    ")
            sys.stdout.flush()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()

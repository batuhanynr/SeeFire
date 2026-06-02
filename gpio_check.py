import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

for pin in [4, 7]:
    print(f"\n--- Testing BCM {pin} ---")
    try:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        print(f"BCM {pin} setup OK")
    except Exception as e:
        print(f"BCM {pin} setup FAILED: {e}")
        continue
        
    try:
        GPIO.add_event_detect(pin, GPIO.RISING, callback=lambda x: print(f"Tick on {x}"), bouncetime=2)
        print(f"BCM {pin} event detect OK")
    except Exception as e:
        print(f"BCM {pin} event detect FAILED: {e}")

GPIO.cleanup()

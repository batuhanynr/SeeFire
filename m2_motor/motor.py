"""
M2 Motor Control Implementation
Follows the architecture rules defined in m2_motor.h
"""
import RPi.GPIO as GPIO
import config
import logging
import time

logger = logging.getLogger(__name__)

class MotorM2:
    def __init__(self):
        self._initialized = False
        
    def init_motors(self) -> bool:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        pins = [config.MOTOR_IN1, config.MOTOR_IN2, 
                config.MOTOR_IN3, config.MOTOR_IN4,
                config.MOTOR_ENA, config.MOTOR_ENB]
                
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            
        # L298N PWM initialization (Placeholder for full PWM wrapper)
        self.pwm_a = GPIO.PWM(config.MOTOR_ENA, 100) 
        self.pwm_b = GPIO.PWM(config.MOTOR_ENB, 100)
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        
        self._initialized = True
        logger.info("M2_Motor configured.")
        return True

    def drive(self, left_speed: int, right_speed: int) -> None:
        """Simplistic motor drive wrapper."""
        if not self._initialized:
            return
            
        def set_motor(in1, in2, pwm, speed):
            # Clamp speed perfectly -100 to 100
            speed = max(-100, min(100, speed))
            if speed > 0:
                GPIO.output(in1, GPIO.HIGH)
                GPIO.output(in2, GPIO.LOW)
                pwm.ChangeDutyCycle(speed)
            elif speed < 0:
                GPIO.output(in1, GPIO.LOW)
                GPIO.output(in2, GPIO.HIGH)
                pwm.ChangeDutyCycle(-speed)
            else:
                GPIO.output(in1, GPIO.LOW)
                GPIO.output(in2, GPIO.LOW)
                pwm.ChangeDutyCycle(0)
                
        set_motor(config.MOTOR_IN1, config.MOTOR_IN2, self.pwm_a, left_speed)
        set_motor(config.MOTOR_IN3, config.MOTOR_IN4, self.pwm_b, right_speed)

    def emergency_stop(self) -> None:
        if self._initialized:
            self.drive(0, 0)
            logger.info("Motor Emergency Stopped.")

    def _read_battery_voltage_dummy(self) -> float:
        # In a real setup, connect battery voltage divider to MCP3008 ADC
        return 7.4 # Nominal 2S Lipo
        
    def check_battery(self) -> int:
        v = self._read_battery_voltage_dummy()
        if v < 6.6: # config.py or M2_BATTERY_CRIT_V 
            logger.warning(f"CRITICAL BATTERY: {v}V")
            return 2
        if v < 7.2: # M2_BATTERY_LOW_V
            logger.warning(f"LOW BATTERY: {v}V")
            return 1
        return 0

_instance = MotorM2()
init_motors = _instance.init_motors
drive = _instance.drive
emergency_stop = _instance.emergency_stop
check_battery = _instance.check_battery

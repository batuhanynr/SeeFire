"""
M2 Motor Control & Power Implementation
Handles physical actuators: L298N driver, Alarm LED, Buzzer, and Battery Voltage.
Supports Mock Mode for development without physical robot.
"""
import config
import logging
import time

logger = logging.getLogger(__name__)

# Try to import RPi.GPIO (Mock if on macOS/Windows)
try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    logger.warning("RPi.GPIO not found. M2 will run in MOCK MODE. Hardware actions will just print to console.")
    MOCK_MODE = True


class MotorM2:
    def __init__(self):
        self._initialized = False
        self.pwm_a = None
        self.pwm_b = None
        self.mock_battery_v = 7.4 # Nominal dummy battery 
        
    def init_hardware(self) -> bool:
        if MOCK_MODE:
            logger.info("[MOCK] Hardware initialized.")
            self._initialized = True
            return True

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup Pins
        pins = [config.MOTOR_IN1, config.MOTOR_IN2, 
                config.MOTOR_IN3, config.MOTOR_IN4,
                config.MOTOR_ENA, config.MOTOR_ENB,
                config.LED_PIN, config.BUZZER_PIN]
                
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            
        # L298N PWM initialization (~1 kHz)
        self.pwm_a = GPIO.PWM(config.MOTOR_ENA, 1000) 
        self.pwm_b = GPIO.PWM(config.MOTOR_ENB, 1000)
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        
        self._initialized = True
        logger.info("M2 Hardware configured successfully on RPi.")
        return True

    def motor_drive(self, direction: str, speed: int) -> None:
        """
        Drives the robot. Direction can be "forward" or "backward".
        Speed is 0-100 percentage.
        """
        speed = max(0, min(100, speed)) # clamp 0-100

        if MOCK_MODE:
            logger.debug(f"[MOCK] motor_drive: {direction} at {speed}% speed")
            return

        if not self._initialized:
            return

        if direction == "forward":
            self._set_left_motor(speed)
            self._set_right_motor(speed)
        elif direction == "backward":
            self._set_left_motor(-speed)
            self._set_right_motor(-speed)
        else:
            self.motor_stop()

    def motor_turn(self, angle: float, speed: int) -> None:
        """
        Turns the robot right for positive angle, left for negative angle.
        """
        speed = max(0, min(100, speed))
        
        if MOCK_MODE:
            logger.debug(f"[MOCK] motor_turn: angle {angle} at {speed}% speed")
            return

        if not self._initialized:
            return

        # Simple differential drive for turning
        if angle > 0: # Turn Right
            self._set_left_motor(speed)
            self._set_right_motor(-speed)
        elif angle < 0: # Turn Left
            self._set_left_motor(-speed)
            self._set_right_motor(speed)
        else:
            self.motor_stop()

    def motor_stop(self) -> None:
        if MOCK_MODE:
            logger.debug("[MOCK] motor_stop")
            return

        if self._initialized:
            self._set_left_motor(0)
            self._set_right_motor(0)

    def _set_left_motor(self, speed: int):
        if speed > 0:
            GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
            GPIO.output(config.MOTOR_IN2, GPIO.LOW)
            self.pwm_a.ChangeDutyCycle(speed)
        elif speed < 0:
            GPIO.output(config.MOTOR_IN1, GPIO.LOW)
            GPIO.output(config.MOTOR_IN2, GPIO.HIGH)
            self.pwm_a.ChangeDutyCycle(-speed)
        else:
            GPIO.output(config.MOTOR_IN1, GPIO.LOW)
            GPIO.output(config.MOTOR_IN2, GPIO.LOW)
            self.pwm_a.ChangeDutyCycle(0)

    def _set_right_motor(self, speed: int):
        if speed > 0:
            GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
            GPIO.output(config.MOTOR_IN4, GPIO.LOW)
            self.pwm_b.ChangeDutyCycle(speed)
        elif speed < 0:
            GPIO.output(config.MOTOR_IN3, GPIO.LOW)
            GPIO.output(config.MOTOR_IN4, GPIO.HIGH)
            self.pwm_b.ChangeDutyCycle(-speed)
        else:
            GPIO.output(config.MOTOR_IN3, GPIO.LOW)
            GPIO.output(config.MOTOR_IN4, GPIO.LOW)
            self.pwm_b.ChangeDutyCycle(0)

    def set_alarm(self, led: bool, buzzer: bool) -> None:
        """
        Activates or deactivates the alarm outputs.
        """
        if MOCK_MODE:
            logger.debug(f"[MOCK] set_alarm: LED={led}, BUZZER={buzzer}")
            return

        if not self._initialized:
            return
            
        GPIO.output(config.LED_PIN, GPIO.HIGH if led else GPIO.LOW)
        GPIO.output(config.BUZZER_PIN, GPIO.HIGH if buzzer else GPIO.LOW)

    def get_battery_voltage(self) -> float:
        """
        Reads the battery voltage via MCP3208 ADC from M3 module.
        Returns the real voltage as a float.
        """
        if MOCK_MODE:
            # Simulate battery drain dynamically over time
            self.mock_battery_v -= 0.001 
            if self.mock_battery_v < config.BATTERY_CRIT_V:
                self.mock_battery_v = config.BATTERY_MAX_V # wrap around for testing
            return round(self.mock_battery_v, 2)

        try:
            from m3_sensors import sensors
            adc_value = sensors.read_battery_adc()
        except ImportError:
            logger.warning("Could not import M3 sensors to read battery.")
            adc_value = 0

        adc_ref_voltage = 3.3
        adc_max = 4095.0 # 12-bit ADC configured for MCP3208
        
        pin_voltage = (adc_value / adc_max) * adc_ref_voltage
        real_voltage = pin_voltage * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)
        
        return round(real_voltage, 2)

# Provide the public API as module-level functions
_instance = MotorM2()
init_hardware = _instance.init_hardware
motor_drive = _instance.motor_drive
motor_turn = _instance.motor_turn
motor_stop = _instance.motor_stop
set_alarm = _instance.set_alarm
get_battery_voltage = _instance.get_battery_voltage

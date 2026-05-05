"""
M2 Motor Control & Power Implementation
Handles physical actuators: L298N driver, Alarm LED, Buzzer, Battery Voltage,
and wheel-encoder distance tracking for waypoint navigation (M5).
Supports Mock Mode for development without physical robot.
"""
import config
import logging
import threading
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
        self.mock_battery_v = 7.4  # Nominal dummy battery

        # Encoder / odometry state
        self._tick_lock = threading.Lock()
        self._left_ticks = 0
        self._right_ticks = 0
        self._direction_sign = 0  # +1 forward, -1 backward, 0 stopped
        self._total_distance_cm = 0.0
        # Mock-mode time-based odometry
        self._motion_start_t = None
        self._motion_speed_cm_per_s = 0.0

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
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

        # Encoder pins as input with pull-down; rising-edge interrupts increment ticks.
        GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        try:
            GPIO.add_event_detect(config.ENCODER_LEFT_PIN, GPIO.RISING,
                                  callback=self._on_left_tick)
            GPIO.add_event_detect(config.ENCODER_RIGHT_PIN, GPIO.RISING,
                                  callback=self._on_right_tick)
        except RuntimeError as e:
            logger.warning("Encoder interrupt setup failed: %s", e)

        self._initialized = True
        logger.info("M2 Hardware configured successfully on RPi.")
        return True

    # ------------------------------------------------------------------
    # Encoder callbacks
    # ------------------------------------------------------------------

    def _on_left_tick(self, _channel):
        with self._tick_lock:
            self._left_ticks += 1

    def _on_right_tick(self, _channel):
        with self._tick_lock:
            self._right_ticks += 1

    def _reset_encoder_window(self):
        with self._tick_lock:
            self._left_ticks = 0
            self._right_ticks = 0
        self._motion_start_t = time.time()

    def _measured_distance_since_window_cm(self) -> float:
        """Return cm traveled since last _reset_encoder_window()."""
        if MOCK_MODE:
            elapsed = time.time() - (self._motion_start_t or time.time())
            return elapsed * self._motion_speed_cm_per_s
        with self._tick_lock:
            avg_ticks = (self._left_ticks + self._right_ticks) / 2.0
        return avg_ticks / config.ENCODER_TICKS_PER_CM

    @property
    def total_distance_cm(self) -> float:
        return self._total_distance_cm

    def set_total_distance_cm(self, value: float) -> None:
        self._total_distance_cm = float(value)

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

    # ------------------------------------------------------------------
    # Distance-based API (used by M5 navigation)
    # ------------------------------------------------------------------

    def drive_distance_cm(self, distance_cm: float) -> None:
        """Drive forward exactly `distance_cm` and stop. Blocking."""
        if distance_cm <= 0:
            return

        self._direction_sign = 1
        self._reset_encoder_window()
        self._motion_speed_cm_per_s = config.MOCK_CM_PER_SEC

        if MOCK_MODE:
            logger.debug("[MOCK] drive_distance_cm: %.1f", distance_cm)
        else:
            self._set_left_motor(config.DRIVE_SPEED)
            self._set_right_motor(config.DRIVE_SPEED)

        deadline = time.time() + (distance_cm / max(config.MOCK_CM_PER_SEC, 1e-3)) * 3.0
        while True:
            traveled = self._measured_distance_since_window_cm()
            if traveled >= distance_cm:
                break
            if time.time() > deadline:
                logger.warning("drive_distance_cm timed out at %.1f/%.1f cm",
                               traveled, distance_cm)
                break
            time.sleep(0.01)

        self.stop()
        self._total_distance_cm += distance_cm

    def turn_left_90(self) -> None:
        self._turn_in_place(direction=-1)

    def turn_right_90(self) -> None:
        self._turn_in_place(direction=+1)

    def _turn_in_place(self, direction: int) -> None:
        """direction: +1 right, -1 left. Time-based; encoder differential not used here."""
        if MOCK_MODE:
            logger.debug("[MOCK] turn_in_place: %s", "right" if direction > 0 else "left")
        else:
            speed = config.TURN_SPEED
            if direction > 0:
                self._set_left_motor(speed)
                self._set_right_motor(-speed)
            else:
                self._set_left_motor(-speed)
                self._set_right_motor(speed)

        time.sleep(config.MOCK_TURN_90_SECONDS)
        self.stop()

    def stop(self) -> None:
        self._direction_sign = 0
        self._motion_speed_cm_per_s = 0.0
        self.motor_stop()


# Provide the public API as module-level functions
_instance = MotorM2()
init_hardware = _instance.init_hardware
motor_drive = _instance.motor_drive
motor_turn = _instance.motor_turn
motor_stop = _instance.motor_stop
set_alarm = _instance.set_alarm
get_battery_voltage = _instance.get_battery_voltage
drive_distance_cm = _instance.drive_distance_cm
turn_left_90 = _instance.turn_left_90
turn_right_90 = _instance.turn_right_90
stop = _instance.stop


def get_total_distance_cm() -> float:
    return _instance.total_distance_cm

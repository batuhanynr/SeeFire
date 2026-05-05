"""
M3 Sensors Implementation
Follows the architecture rules defined in m3_sensors.h
Uses SPI (MCP3208) for MQ-2, I2C for MLX90614, and GPIO for HC-SR04.
Supports Mock Mode for development without physical sensors.
"""
from dataclasses import dataclass
import time
import logging

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    MOCK_MODE = True

try:
    from smbus2 import SMBus
    import adafruit_mlx90614
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

try:
    import spidev
    SPI_AVAILABLE = True
except ImportError:
    SPI_AVAILABLE = False

import config

logger = logging.getLogger(__name__)

@dataclass
class FusionData:
    smoke_level: int
    smoke_alert: bool
    ir_temp: float
    timestamp: float

@dataclass
class NavData:
    left_cm: float
    right_cm: float
    timestamp: float

class SensorsM3:
    def __init__(self):
        self._smoke_threshold = config.SMOKE_THRESHOLD
        self._ir_temp_threshold = config.IR_TEMP_THRESHOLD
        self._start_time = time.time()
        
        self._bus = None
        self._mlx_sensor = None
        self._spi = None
        
    def init_sensors(self) -> bool:
        if MOCK_MODE:
            logger.info("[MOCK] M3_Sensors initialized successfully.")
            return True

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup Ultrasonics
        for pin in (config.TRIG_LEFT, config.TRIG_RIGHT):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        for pin in (config.ECHO_LEFT, config.ECHO_RIGHT):
            GPIO.setup(pin, GPIO.IN)

        # Setup I2C (MLX90614)
        if MLX_AVAILABLE:
            try:
                self._bus = SMBus(1)
                self._mlx_sensor = adafruit_mlx90614.MLX90614(self._bus)
                logger.info("MLX90614 connected via I2C.")
            except Exception as e:
                logger.error(f"MLX90614 I2C failed: {e}")
                self._mlx_sensor = None

        # Setup SPI (MCP3208 for MQ2 and Battery)
        if SPI_AVAILABLE:
            try:
                self._spi = spidev.SpiDev()
                self._spi.open(0, 0)
                self._spi.max_speed_hz = 1350000
                logger.info("SPI MCP3208 connected.")
            except Exception as e:
                logger.error(f"SPI init failed: {e}")
                self._spi = None

        logger.info("M3_Sensors initialized successfully.")
        return True

    def _read_mcp3208(self, channel: int) -> int:
        if MOCK_MODE:
            if channel == config.BATTERY_ADC_CH:
                return int((7.4 / 3.3) * (config.VDIV_R2 / (config.VDIV_R1 + config.VDIV_R2)) * 4095) # mock bat
            return 150 # mock smoke
            
        if not self._spi:
            return 0
        adc = self._spi.xfer2([6 | (channel >> 2), (channel & 3) << 6, 0])
        data = ((adc[1] & 15) << 8) + adc[2]
        return data

    def _read_ultrasonic(self, trig_pin: int, echo_pin: int) -> float:
        if MOCK_MODE:
            import random
            return random.uniform(15.0, 45.0)

        GPIO.output(trig_pin, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(trig_pin, GPIO.LOW)
        
        start_t = time.time()
        stop_t = time.time()
        timeout = start_t + 0.04
        
        while GPIO.input(echo_pin) == 0 and time.time() < timeout:
            start_t = time.time()
        while GPIO.input(echo_pin) == 1 and time.time() < timeout:
            stop_t = time.time()
            
        elapsed = stop_t - start_t
        distance = (elapsed * 34300) / 2
        return distance

    def get_fusion_sensors(self) -> FusionData:
        smoke = self._read_mcp3208(config.MQ2_ADC_CH)
        is_warm = time.time() - self._start_time > config.MQ2_WARMUP_SECONDS
        
        if MOCK_MODE:
            is_warm = True # skip warmup in mock mode
            
        alert = bool(smoke > self._smoke_threshold) if is_warm else False
        
        ir = 25.0
        if MOCK_MODE:
            ir = 28.5
        elif self._mlx_sensor:
            try:
                ir = float(self._mlx_sensor.object_temperature)
            except Exception:
                pass
                
        return FusionData(smoke_level=smoke, smoke_alert=alert, ir_temp=ir, timestamp=time.time())

    def get_navigation_sensors(self) -> NavData:
        l = self._read_ultrasonic(config.TRIG_LEFT, config.ECHO_LEFT)
        r = self._read_ultrasonic(config.TRIG_RIGHT, config.ECHO_RIGHT)
        return NavData(left_cm=l, right_cm=r, timestamp=time.time())

    def read_battery_adc(self) -> int:
        """Expose Battery ADC channel for M2"""
        return self._read_mcp3208(config.BATTERY_ADC_CH)

    def cleanup(self) -> None:
        if self._spi:
            self._spi.close()
        if self._bus:
            self._bus.close()

# Default singleton
_instance = SensorsM3()
init_sensors = _instance.init_sensors
get_fusion_sensors = _instance.get_fusion_sensors
get_navigation_sensors = _instance.get_navigation_sensors
read_battery_adc = _instance.read_battery_adc
cleanup = _instance.cleanup

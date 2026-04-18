import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

__all__ = [
    "m3_fusion_data_t", "m3_nav_data_t",
    "init_sensors", "get_fusion_sensors", "get_navigation_sensors",
    "read_mq2", "read_mlx90614", "read_dht22", "read_hcsr04", "read_mpu6050_yaw",
    "is_mq2_ready",
]

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class m3_fusion_data_t:
    smoke_level: int       # MQ-2 raw ADC 0-1023
    ir_temp: float         # MLX90614 object surface temp in °C
    ambient_temp: float    # DHT22 ambient temperature in °C
    ambient_humidity: float # DHT22 relative humidity %
    timestamp: str         # ISO 8601 UTC

@dataclass
class m3_nav_data_t:
    dist_left: float       # HC-SR04 left distance in cm
    dist_right: float      # HC-SR04 right distance in cm
    yaw: float             # MPU6050 heading in degrees
    timestamp: str         # ISO 8601 UTC

# ---------------------------------------------------------------------------
# Sensor state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_init_time: float | None = None
_i2c_bus = None
_spi = None

_mlx_sensor = None
_dht_sensor = None
_mpu_sensor = None

_yaw_offset: float = 0.0
_yaw_raw: float = 0.0

# HC-SR04 polling interval to avoid tight busy-wait
_HCSR04_POLL_INTERVAL = 0.0001  # 100 µs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Bus initialization
# ---------------------------------------------------------------------------

def init_sensors() -> None:
    """Initialize I2C, SPI, GPIO and sensor objects. Call once at startup."""
    global _init_time, _i2c_bus, _spi, _mlx_sensor, _dht_sensor, _mpu_sensor

    _init_time = time.time()

    try:
        import smbus2
        _i2c_bus = smbus2.SMBus(1)
        logger.info("I2C bus initialized (bus 1)")
    except Exception as e:
        logger.warning("I2C init failed: %s — sensor reads will use fallbacks", e)
        _i2c_bus = None

    try:
        import spidev
        _spi = spidev.SpiDev()
        _spi.open(0, 0)
        _spi.max_speed_hz = 1_000_000
        logger.info("SPI bus initialized (CE0)")
    except Exception as e:
        logger.warning("SPI init failed: %s — MQ-2 reads will use fallbacks", e)
        _spi = None

    if _i2c_bus is not None:
        try:
            import adafruit_mlx90614
            _mlx_sensor = adafruit_mlx90614.MLX90614(_i2c_bus)
            logger.info("MLX90614 sensor object created")
        except ImportError:
            logger.info("adafruit_mlx90614 not available — using raw I2C fallback")
        except Exception as e:
            logger.warning("MLX90614 init failed: %s", e)

        try:
            import mpu6050
            _mpu_sensor = mpu6050.mpu6050(config.MPU6050_ADDR)
            logger.info("MPU6050 sensor object created")
        except Exception as e:
            logger.warning("MPU6050 init failed: %s", e)

    try:
        import adafruit_dht
        _dht_sensor = adafruit_dht.DHT22(config.DHT22_PIN)
        logger.info("DHT22 sensor object created")
    except Exception as e:
        logger.warning("DHT22 init failed: %s — using fallbacks", e)

    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        for pin in (config.TRIG_LEFT, config.TRIG_RIGHT, config.DHT22_PIN):
            GPIO.setup(pin, GPIO.IN)
        logger.info("GPIO pins configured")
    except Exception as e:
        logger.warning("GPIO init failed: %s — running in mock mode", e)

    logger.info("M3 sensor init complete. MQ-2 warm-up: %ds", config.MQ2_WARMUP_SECONDS)


# ---------------------------------------------------------------------------
# Individual sensor readers
# ---------------------------------------------------------------------------

def read_mq2() -> int:
    """Read MQ-2 smoke sensor via MCP3208 SPI ADC. Returns 0-1023."""
    if _spi is None:
        return 0
    adc_value = _spi.xfer2([1, (8 + 0) << 4, 0])
    raw = ((adc_value[1] & 3) << 8) | adc_value[2]
    return raw


def read_mlx90614() -> float:
    """Read MLX90614 IR thermometer object temperature in °C via I2C."""
    if _i2c_bus is None:
        return 25.0
    try:
        if _mlx_sensor is not None:
            return float(_mlx_sensor.object_temperature)
        data = _i2c_bus.read_i2c_block_data(config.MLX90614_ADDR, 0x07, 3)
        raw = (data[1] << 8) | data[0]
        return raw * 0.02 - 273.15
    except Exception as e:
        logger.warning("MLX90614 read error: %s", e)
        return 25.0


def read_dht22() -> tuple[float, float]:
    """Read DHT22 ambient temp (°C) and humidity (%). Returns (temp, humidity)."""
    try:
        if _dht_sensor is not None:
            temp = _dht_sensor.temperature
            humidity = _dht_sensor.humidity
            if temp is None or humidity is None:
                return (25.0, 50.0)
            return (float(temp), float(humidity))
        return (25.0, 50.0)
    except Exception as e:
        logger.debug("DHT22 read error: %s", e)
        return (25.0, 50.0)


def read_hcsr04(trigger_pin: int, echo_pin: int) -> float:
    """Read HC-SR04 ultrasonic distance in cm. Returns -1.0 on timeout."""
    try:
        import RPi.GPIO as GPIO
        GPIO.setup(trigger_pin, GPIO.OUT)
        GPIO.output(trigger_pin, True)
        time.sleep(0.00001)
        GPIO.output(trigger_pin, False)

        GPIO.setup(echo_pin, GPIO.IN)
        start = time.time()
        timeout = start + 0.04

        while GPIO.input(echo_pin) == 0:
            if time.time() > timeout:
                return -1.0
            time.sleep(_HCSR04_POLL_INTERVAL)
        pulse_start = time.time()

        while GPIO.input(echo_pin) == 1:
            if time.time() > timeout:
                return -1.0
            time.sleep(_HCSR04_POLL_INTERVAL)
        pulse_end = time.time()

        duration = pulse_end - pulse_start
        distance = duration * 34300 / 2
        return round(distance, 2)
    except Exception as e:
        logger.debug("HC-SR04 read error on trigger=%d echo=%d: %s", trigger_pin, echo_pin, e)
        return -1.0


def read_mpu6050_yaw() -> float:
    """Read current yaw from MPU6050 gyro integration. Degrees [-180, 180]."""
    global _yaw_raw
    try:
        if _mpu_sensor is None:
            return 0.0
        with _lock:
            gyro = _mpu_sensor.get_gyro_data()
            dt = 0.1
            _yaw_raw += gyro['z'] * dt
            yaw = (_yaw_raw + _yaw_offset) % 360
            if yaw > 180:
                yaw -= 360
            return round(yaw, 2)
    except Exception as e:
        logger.debug("MPU6050 read error: %s", e)
        return 0.0


# ---------------------------------------------------------------------------
# Fusion & Navigation API (called by M6 and M5)
# ---------------------------------------------------------------------------

def get_fusion_sensors() -> m3_fusion_data_t:
    """Aggregate smoke, IR temp, ambient temp/humidity for M6 decision engine."""
    with _lock:
        ts = _now_iso()
        smoke = read_mq2()
        ir_temp = read_mlx90614()
        ambient_temp, ambient_humidity = read_dht22()
        return m3_fusion_data_t(
            smoke_level=smoke,
            ir_temp=ir_temp,
            ambient_temp=ambient_temp,
            ambient_humidity=ambient_humidity,
            timestamp=ts,
        )


def get_navigation_sensors() -> m3_nav_data_t:
    """Aggregate ultrasonic distances and yaw for M5 navigation."""
    with _lock:
        ts = _now_iso()
        dist_left = read_hcsr04(config.TRIG_LEFT, config.ECHO_LEFT)
        dist_right = read_hcsr04(config.TRIG_RIGHT, config.ECHO_RIGHT)
        yaw = read_mpu6050_yaw()
        return m3_nav_data_t(
            dist_left=dist_left,
            dist_right=dist_right,
            yaw=yaw,
            timestamp=ts,
        )


def is_mq2_ready() -> bool:
    """Check if MQ-2 warm-up period has elapsed."""
    if _init_time is None:
        return False
    return (time.time() - _init_time) >= config.MQ2_WARMUP_SECONDS

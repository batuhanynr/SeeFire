import os
import logging

logger = logging.getLogger(__name__)

# Base data directory — all persistent files go here
DATA_DIR = os.environ.get("SEEFIRE_DATA_DIR", "/data")

# File paths
MAP_JSON_PATH = os.path.join(DATA_DIR, "map.json")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "seefire.db")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")

# --- GPIO Pin Assignments ---

# Motor Control (M2)
MOTOR_IN1, MOTOR_IN2, MOTOR_IN3, MOTOR_IN4 = 17, 18, 27, 22
MOTOR_ENA, MOTOR_ENB = 12, 13

# Sensor Integration (M3)
TRIG_LEFT, ECHO_LEFT = 23, 24
TRIG_RIGHT, ECHO_RIGHT = 25, 8
TRIG_CENTER, ECHO_CENTER = 16, 20 # 3rd Ultrasonic Sensor Added
MQ2_CS_PIN = 5
MQ2_ADC_CH = 0

# Alarm Outputs (M2/M6)
LED_PIN = 26
BUZZER_PIN = 19

# --- I2C Addresses ---

MLX90614_ADDR = 0x5A

# --- Detection Thresholds ---

SMOKE_THRESHOLD = 300
IR_TEMP_THRESHOLD = 60.0
VISION_CONF_THRESHOLD = 0.5
FUSION_ALARM_THRESH = 0.7
FUSION_CLEAR_THRESH = 0.4

# --- Navigation ---

OBSTACLE_DIST_CM = 20
GRID_RESOLUTION_M = 0.10
WALL_FOLLOW_DIST_CM = 30

# --- Battery Characteristics (2S Li-ion) ---
BATTERY_MAX_V     = 8.4   # Full charge
BATTERY_NOMINAL_V = 7.4   # Typical
BATTERY_LOW_V     = 6.8   # Warning threshold
BATTERY_CRIT_V    = 6.4   # Emergency stop / cutoff
BATTERY_ADC_CH    = 1     # Which MCP3208 channel
VDIV_R1           = 20000.0 # 20k Ohm
VDIV_R2           = 10000.0 # 10k Ohm (V_ADC = V_BAT * R2/(R1+R2))

# --- Fusion Weights (must sum to 1.0) ---

W_VISION = 0.5
W_SMOKE = 0.3
W_IR = 0.2

# --- Sensor ---

MQ2_WARMUP_SECONDS = 60


def validate_gpio_pins() -> None:
    all_pins = {
        "MOTOR_IN1": MOTOR_IN1, "MOTOR_IN2": MOTOR_IN2,
        "MOTOR_IN3": MOTOR_IN3, "MOTOR_IN4": MOTOR_IN4,
        "MOTOR_ENA": MOTOR_ENA, "MOTOR_ENB": MOTOR_ENB,
        "TRIG_LEFT": TRIG_LEFT, "ECHO_LEFT": ECHO_LEFT,
        "TRIG_RIGHT": TRIG_RIGHT, "ECHO_RIGHT": ECHO_RIGHT,
        "MQ2_CS_PIN": MQ2_CS_PIN,
        "LED_PIN": LED_PIN, "BUZZER_PIN": BUZZER_PIN,
    }
    seen = {}
    for name, pin in all_pins.items():
        if pin in seen:
            raise ValueError(f"GPIO pin conflict: {name} and {seen[pin]} both use pin {pin}")
        seen[pin] = name
    logger.info("GPIO pin validation passed: %d pins, no conflicts", len(all_pins))


def validate_fusion_weights() -> None:
    total = W_VISION + W_SMOKE + W_IR
    if not (0.99 <= total <= 1.01):
        raise ValueError(f"Fusion weights must sum to 1.0, got {total:.4f}")

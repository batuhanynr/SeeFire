import os
import logging

logger = logging.getLogger(__name__)

# Base data directory — all persistent files go here.
# Defaults to a repo-local directory so mock-mode works on dev machines
# without requiring a writable /data mount.
_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "runtime_data")
DATA_DIR = os.environ.get("SEEFIRE_DATA_DIR", _DEFAULT_DATA_DIR)

# File paths
MAP_JSON_PATH = os.path.join(DATA_DIR, "map.json")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "seefire.db")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")

# --- GPIO Pin Assignments ---

# Motor Control (M2)
MOTOR_IN1, MOTOR_IN2, MOTOR_IN3, MOTOR_IN4 = 17, 18, 27, 22
MOTOR_ENA, MOTOR_ENB = 12, 13

# Sensor Integration (M3)
# Source of truth: docs/Seefire Wiring Plan.md (BCM numbering)
TRIG_FRONT, ECHO_FRONT = 23, 24
TRIG_RIGHT, ECHO_RIGHT = 25, 21
TRIG_LEFT, ECHO_LEFT = 20, 16
MQ2_CS_PIN = 5
MQ2_ADC_CH = 0

# Wheel Encoders (single-channel pulse counting; direction inferred from motor command)
ENCODER_LEFT_PIN = 6
ENCODER_RIGHT_PIN = 7

# Alarm Outputs (M2/M6)
LED_PIN = 26
BUZZER_PIN = 19

# --- I2C Addresses ---

I2C_BUS = 1
MLX90614_ADDR = 0x5A

# --- Detection Thresholds ---

SMOKE_THRESHOLD = 300
IR_TEMP_THRESHOLD = 60.0
VISION_CONF_THRESHOLD = 0.5
FUSION_ALARM_THRESH = 0.7
FUSION_CLEAR_THRESH = 0.4

# --- Navigation (waypoint-based, south-to-north traversal) ---

# Route as list of (target_north_cm, sector_id). Distance is cumulative from start.
WAYPOINTS = [
    (1000, 1),
    (2000, 2),
    (2200, 3),
]

# Forward-step granularity for the main loop (smaller = finer midpoint detection)
STEP_DISTANCE_CM = 5.0
# Side-step granularity during obstacle bypass
SIDE_STEP_CM = 5.0

# Obstacle thresholds (front sensor)
OBSTACLE_THRESHOLD_CM = 55.0   # below this → obstacle, trigger avoidance

# Side-pass dynamic clearance: clearance-side sensor must exceed D₀ + delta
# to declare the obstacle cleared. D₀ is the front reading at detection time.
OBSTACLE_CLEARANCE_DELTA_CM = 15.0

# During side-pass the new "forward" sensor is `front`. If it drops below this
# we've hit the perpendicular wall → retreat and try the other side.
WALL_CLEARANCE_CM = 10.0

# Hard cap on side-pass travel before aborting (per attempt).
SIDE_PASS_SAFETY_CAP_CM = 200.0

# Hard cap on the forward-pass phase (drive north while obstacle is alongside).
FORWARD_PASS_SAFETY_CAP_CM = 100.0

# Start position reference (left/right wall distances at south origin)
START_LEFT_CM  = 200.0
START_RIGHT_CM = 200.0
POSITION_TOLERANCE_CM = 5.0
FINE_TUNE_STEP_CM     = 2.0

# Encoder calibration (20 ticks per 20.73cm wheel revolution -> ~0.965 ticks/cm)
ENCODER_TICKS_PER_CM = 1.6239
# Slots on the encoder disc = ticks per full wheel revolution. Set to your
# actual disc slot count (common slotted optical discs are 20). Used for RPM.
ENCODER_TICKS_PER_REV = 20.0
# Wheel diameter (mm). With ticks-per-rev gives true speed: one rev advances
# pi*diameter. (Note: ENCODER_TICKS_PER_CM above is a separate calibration and
# does not match this geometry; speed calc uses diameter + ticks-per-rev.)
WHEEL_DIAMETER_MM = 66.0

# Drive parameters
DRIVE_SPEED = 60   # PWM duty cycle 0-100 for forward
TURN_SPEED  = 75   # PWM duty cycle 0-100 for turning (increased for more torque/power)
# Motor speed trims to correct forward drift (1.0 = no trim)
# If the robot drifts right, decrease LEFT_MOTOR_TRIM (e.g. 0.90)
LEFT_MOTOR_TRIM = 1.0
RIGHT_MOTOR_TRIM = 0.95
# Time-based fallback for distance/turn when no encoder is wired (mock or hardware-absent)
MOCK_CM_PER_SEC      = 20.0  # nominal forward speed at DRIVE_SPEED duty
MOCK_TURN_RIGHT_90_SECONDS = 0.78  # nominal time for 90° right pivot at TURN_SPEED
MOCK_TURN_LEFT_90_SECONDS = 0.71   # nominal time for 90° left pivot at TURN_SPEED
MOCK_TURN_90_SECONDS = 0.71        # fallback/default nominal time for 90° pivot

# --- Battery Characteristics (2S Li-ion) ---
BATTERY_MAX_V     = 8.4   # Full charge
BATTERY_NOMINAL_V = 7.4   # Typical
BATTERY_LOW_V     = 6.8   # Warning threshold
BATTERY_CRIT_V    = 6.4   # Emergency stop / cutoff
BYPASS_BATTERY_CHECK = True   # ADC kalibre edilene kadar True — gerçek çalışmada False yapın
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
        "TRIG_FRONT": TRIG_FRONT, "ECHO_FRONT": ECHO_FRONT,
        "ENCODER_LEFT_PIN": ENCODER_LEFT_PIN,
        "ENCODER_RIGHT_PIN": ENCODER_RIGHT_PIN,
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

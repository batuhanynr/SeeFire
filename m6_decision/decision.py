"""
M6 Decision Engine.
Handles the main FSM (Finite State Machine) and health monitoring.
"""
import logging
import config
import threading
import time
from enum import Enum, auto
from m2_motor import motor
from m5_navigation.navigation import NavigationController, ObstacleBlockedError
import m7_logging

logger = logging.getLogger(__name__)


class ThreatVerificationTriggered(Exception):
    """Exception raised to interrupt navigation loop for verification when risk is high."""
    pass


class RobotState(Enum):
    INIT = auto()
    NAVIGATE = auto()
    VERIFY = auto()
    ALARM = auto()
    STOP = auto()


class DecisionEngine:
    def __init__(self):
        self.state = RobotState.INIT
        self._stop_event = threading.Event()
        self.fusion_score = 0.0
        # Initialize NavigationController with a callback that logs to M7
        self.nav = NavigationController(snapshot_callback=self._on_snapshot)

    def _on_snapshot(self, label: str) -> None:
        """Callback from M5 to capture state and log to M7."""
        import m4_vision
        import m3_sensors
        import json

        logger.info("[DECISION] Processing snapshot request: %s", label)

        # 1. Capture data
        frame = m4_vision.capture_frame()
        sensors = m3_sensors.get_fusion_sensors()
        fire_conf = m4_vision.get_fire_confidence()
        fire_side = m4_vision.get_fire_side()

        # 2. Calculate fusion score using real YOLO confidence.
        # When no model is loaded fire_conf=0.0; alarm can still trigger via
        # high smoke_level + ir_temp alone (combined weight 0.5).
        self.fusion_score = self._calculate_fusion_score(
            vision_conf=fire_conf,
            smoke_val=float(sensors.smoke_level),
            ir_temp=float(sensors.ir_temp)
        )

        # Check for state transition trigger
        if self.fusion_score >= config.FUSION_ALARM_THRESH and self.state == RobotState.NAVIGATE:
            logger.warning(
                "[DECISION] Fusion score %.2f exceeds alarm threshold! Fire side: %s",
                self.fusion_score, fire_side or "unknown"
            )
            self.state = RobotState.VERIFY
            raise ThreatVerificationTriggered("Threat verification triggered due to high fusion score")

        # 3. M7 Logging integration
        event = m7_logging.m7_event_t(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            event_type=f"SNAPSHOT_{label}",
            fusion_score=self.fusion_score,
            sensor_data=json.dumps({
                "smoke": sensors.smoke_level,
                "temp": sensors.ir_temp,
                "distance": motor.get_total_distance_cm(),
                "fire_side": fire_side,
                "fire_conf": fire_conf,
            }),
            snapshot_path=""  # Updated below
        )

        event_id = m7_logging.log_event(event)

        if frame is not None:
            import cv2
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                path = m7_logging.save_snapshot(buf.tobytes(), event_id)
                # Note: Ideally we'd update the DB record with path, but M7 API
                # currently doesn't expose a 'update_event_path' method.
                logger.info("Snapshot saved to %s", path)

    def _calculate_fusion_score(self, vision_conf: float, smoke_val: float, ir_temp: float) -> float:
        """
        Calculates the risk score based on weighted sensor inputs.
        Weights: Vision=0.5, Smoke=0.3, IR=0.2 (from config)
        """
        # Normalize smoke (4095 is max for 12-bit ADC)
        smoke_score = min(1.0, smoke_val / 4095.0)
        
        # Normalize IR (Threshold maps to 1.0)
        ir_score = min(1.0, ir_temp / config.IR_TEMP_THRESHOLD)
        
        score = (config.W_VISION * vision_conf) + \
                (config.W_SMOKE * smoke_score) + \
                (config.W_IR * ir_score)
        
        return round(float(score), 2)

    def start(self):
        logger.info("Decision Engine (FSM) started in state: %s", self.state)
        # Main State Machine Loop
        while not self._stop_event.is_set():
            if not check_battery_health():
                self.state = RobotState.STOP

            self._handle_state()
            time.sleep(0.1)

    def _handle_state(self):
        if self.state == RobotState.INIT:
            logger.info("[FSM] Initializing systems...")
            self.state = RobotState.NAVIGATE

        elif self.state == RobotState.NAVIGATE:
            logger.info("[DECISION] Starting navigation mission...")
            # Navigation is handled by NavigationController
            try:
                # We start navigation. During navigation, _on_snapshot will
                # update self.fusion_score based on periodic sensor checks.
                self.nav.run()
                
                # If navigation completes without ALARM triggering
                if self.state == RobotState.NAVIGATE:
                    self.state = RobotState.STOP
                    
            except ThreatVerificationTriggered:
                logger.info("[DECISION] Navigation paused for threat verification.")
                # self.state has already been set to RobotState.VERIFY in _on_snapshot
            except ObstacleBlockedError as e:
                logger.error("[DECISION] Navigation blocked: %s. Initiating abort.", e)
                self.state = RobotState.STOP
            except Exception as e:
                logger.error("[DECISION] Navigation failed: %s", e)
                self.state = RobotState.STOP

        elif self.state == RobotState.VERIFY:
            logger.info("[FSM] High risk detected (score=%.2f). Verifying threat...", self.fusion_score)
            # Stop navigation/movement to focus on verification
            motor.motor_stop()
            
            # Wait 2 seconds to see if score remains high (mock verification)
            time.sleep(2)
            if self.fusion_score >= config.FUSION_ALARM_THRESH:
                self.state = RobotState.ALARM
            else:
                logger.info("[FSM] Threat suspicious but not confirmed (score=%.2f). Resuming.", self.fusion_score)
                self.state = RobotState.NAVIGATE

        elif self.state == RobotState.ALARM:
            logger.error("[FSM] !!! FIRE ALARM ACTIVE !!! (Score: %.2f)", self.fusion_score)
            motor.set_alarm(led=True, buzzer=True)
            
            # Reset only if fusion score drops significantly
            if self.fusion_score < config.FUSION_CLEAR_THRESH:
                logger.info("[FSM] Risk cleared (score=%.2f). Resetting alarm.", self.fusion_score)
                motor.set_alarm(led=False, buzzer=False)
                self.state = RobotState.NAVIGATE

        elif self.state == RobotState.STOP:
            logger.info("[FSM] Shutdown.")
            motor.motor_stop()
            self._stop_event.set()


def check_battery_health() -> bool:
    """
    Monitor battery voltage. 
    If voltage drops below critical threshold, trigger emergency stop.
    Returns True if health is OK, False if critical.
    """
    if getattr(config, "BYPASS_BATTERY_CHECK", False):
        return True

    # Using the module-level function from Bekir's M2
    voltage = motor.get_battery_voltage()
    
    if voltage < config.BATTERY_CRIT_V:
        logger.error("CRITICAL BATTERY: %.2fV (Threshold: %.2fV). Emergency stop triggered.", 
                     voltage, config.BATTERY_CRIT_V)
        return False
    
    if voltage < config.BATTERY_LOW_V:
        logger.warning("LOW BATTERY: %.2fV (Threshold: %.2fV). Consider returning.", 
                       voltage, config.BATTERY_LOW_V)
        
    return True


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
from m5_navigation.navigation import NavigationController
import m7_logging

logger = logging.getLogger(__name__)


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

        # 2. Logic to update global fusion score (simplified for now)
        # In Phase 2, this will be more complex.
        self.fusion_score = 0.1  # Placeholder

        # 3. M7 Logging integration
        event = m7_logging.m7_event_t(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            event_type=f"SNAPSHOT_{label}",
            fusion_score=self.fusion_score,
            sensor_data=json.dumps({
                "smoke": sensors.smoke_level,
                "temp": sensors.ir_temp,
                "distance": motor.get_total_distance_cm()
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
            self.state = RobotState.NAVIGATE

        elif self.state == RobotState.NAVIGATE:
            logger.info("[DECISION] Starting navigation mission...")
            try:
                # This call blocks until navigation is complete or fails
                self.nav.run()
                self.state = RobotState.STOP
            except Exception as e:
                logger.error("[DECISION] Navigation failed: %s", e)
                self.state = RobotState.STOP

        elif self.state == RobotState.VERIFY:
            # Phase 2: High-frequency verification logic
            pass

        elif self.state == RobotState.ALARM:
            motor.set_alarm(led=True, buzzer=True)

        elif self.state == RobotState.STOP:
            motor.motor_stop()
            self._stop_event.set()


def check_battery_health() -> bool:
    """
    Monitor battery voltage. 
    If voltage drops below critical threshold, trigger emergency stop.
    Returns True if health is OK, False if critical.
    """
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


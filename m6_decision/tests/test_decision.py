import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Insert parent directory to ensure repo-level imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
from m6_decision.decision import (
    DecisionEngine,
    RobotState,
    check_battery_health,
    ThreatVerificationTriggered,
)
from m5_navigation.obstacle import ObstacleBlockedError


class TestDecisionEngine(unittest.TestCase):

    def setUp(self):
        # Prevent actual database writes during tests by mock patching configuration or logging
        self.db_patcher = patch("m7_logging.log_event", return_value=1)
        self.snap_patcher = patch("m7_logging.save_snapshot", return_value="/mock/snap.jpg")
        self.db_patcher.start()
        self.snap_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.snap_patcher.stop()

    def test_initial_state(self):
        engine = DecisionEngine()
        self.assertEqual(engine.state, RobotState.INIT)
        self.assertEqual(engine.fusion_score, 0.0)

    def test_calculate_fusion_score(self):
        engine = DecisionEngine()
        # Weights: Vision = 0.5, Smoke = 0.3, IR = 0.2
        # Case 1: All inputs zero
        score = engine._calculate_fusion_score(0.0, 0.0, 0.0)
        self.assertEqual(score, 0.0)

        # Case 2: Max inputs
        # Smoke: 4095 is max. IR: config.IR_TEMP_THRESHOLD (60.0) or higher is max.
        score = engine._calculate_fusion_score(1.0, 4095.0, 60.0)
        self.assertEqual(score, 1.0)

        # Case 3: Mixed inputs
        # Vision: 0.6 -> score component: 0.3
        # Smoke: 2047.5 (half of 4095) -> score component: 0.3 * 0.5 = 0.15
        # IR: 30.0 (half of 60.0) -> score component: 0.2 * 0.5 = 0.10
        # Expected: 0.3 + 0.15 + 0.10 = 0.55
        score = engine._calculate_fusion_score(0.6, 2047.5, 30.0)
        self.assertEqual(score, 0.55)

    @patch("m2_motor.motor.get_battery_voltage")
    def test_battery_health_states(self, mock_get_voltage):
        with patch.object(config, "BYPASS_BATTERY_CHECK", False):
            # Case 1: Voltage OK
            mock_get_voltage.return_value = 7.4
            self.assertTrue(check_battery_health())

            # Case 2: Voltage Low but OK to continue
            mock_get_voltage.return_value = 6.6
            self.assertTrue(check_battery_health())

            # Case 3: Voltage Critical (Emergency Stop)
            mock_get_voltage.return_value = 6.2
            self.assertFalse(check_battery_health())

    def test_init_transitions_to_navigate(self):
        engine = DecisionEngine()
        self.assertEqual(engine.state, RobotState.INIT)
        engine._handle_state()
        self.assertEqual(engine.state, RobotState.NAVIGATE)

    @patch("m4_vision.capture_frame", return_value=None)
    @patch("m3_sensors.get_fusion_sensors")
    @patch("m4_vision.get_fire_confidence", return_value=0.8)
    def test_on_snapshot_raises_verification_when_risk_high(self, mock_fire, mock_sensors, mock_frame):
        # Simulate YOLO detecting fire (fire_conf=0.8) + high smoke + high IR
        # Vision:  0.8 * 0.5  = 0.40
        # Smoke:   4095/4095 * 0.3 = 0.30
        # IR:      60/60 * 0.2     = 0.20
        # Total score: 0.90 → exceeds FUSION_ALARM_THRESH (0.6)
        mock_sens = MagicMock()
        mock_sens.smoke_level = 4095.0
        mock_sens.ir_temp = 60.0
        mock_sensors.return_value = mock_sens

        engine = DecisionEngine()
        engine.state = RobotState.NAVIGATE

        with self.assertRaises(ThreatVerificationTriggered):
            engine._on_snapshot("WAYPOINT")

        self.assertEqual(engine.state, RobotState.VERIFY)
        self.assertEqual(engine.fusion_score, 0.9)

    @patch("m4_vision.capture_frame", return_value=None)
    @patch("m3_sensors.get_fusion_sensors")
    @patch("m4_vision.get_fire_confidence", return_value=0.0)
    def test_on_snapshot_no_trigger_when_yolo_absent(self, mock_fire, mock_sensors, mock_frame):
        # Without YOLO (fire_conf=0.0) and moderate sensors, score stays below alarm threshold.
        # Vision:  0.0 * 0.5 = 0.00
        # Smoke:   200/4095 * 0.3 ≈ 0.015
        # IR:      35/60   * 0.2 ≈ 0.117
        # Total ≈  0.13 — well below FUSION_ALARM_THRESH (0.6)
        mock_sens = MagicMock()
        mock_sens.smoke_level = 200.0
        mock_sens.ir_temp = 35.0
        mock_sensors.return_value = mock_sens

        engine = DecisionEngine()
        engine.state = RobotState.NAVIGATE

        # Should NOT raise
        engine._on_snapshot("MIDPOINT")
        self.assertEqual(engine.state, RobotState.NAVIGATE)

    @patch("m5_navigation.navigation.NavigationController.run")
    def test_navigate_runs_nav_completely(self, mock_nav_run):
        engine = DecisionEngine()
        engine.state = RobotState.NAVIGATE

        engine._handle_state()
        mock_nav_run.assert_called_once()
        self.assertEqual(engine.state, RobotState.STOP)

    @patch("m5_navigation.navigation.NavigationController.run")
    def test_navigate_handles_threat_verification_interrupt(self, mock_nav_run):
        engine = DecisionEngine()
        engine.state = RobotState.NAVIGATE

        # Simulate snapshot triggering an interrupt
        mock_nav_run.side_effect = ThreatVerificationTriggered()

        engine._handle_state()
        self.assertEqual(engine.state, RobotState.NAVIGATE)  # State didn't abort/stop, FSM continues

    @patch("m5_navigation.navigation.NavigationController.run")
    def test_navigate_handles_obstacle_blocked_aborts(self, mock_nav_run):
        engine = DecisionEngine()
        engine.state = RobotState.NAVIGATE

        # Simulate both sides blocked error
        mock_nav_run.side_effect = ObstacleBlockedError("Both sides blocked")

        engine._handle_state()
        self.assertEqual(engine.state, RobotState.STOP)

    @patch("m2_motor.motor.motor_stop")
    @patch("m2_motor.motor.set_alarm")
    def test_verify_transitions_to_alarm_when_confirmed(self, mock_set_alarm, mock_motor_stop):
        engine = DecisionEngine()
        engine.state = RobotState.VERIFY
        # Threat is confirmed because fusion score stays high
        engine.fusion_score = 0.85

        engine._handle_state()
        mock_motor_stop.assert_called_once()
        self.assertEqual(engine.state, RobotState.ALARM)

    @patch("m2_motor.motor.motor_stop")
    def test_verify_transitions_to_navigate_when_false_alarm(self, mock_motor_stop):
        engine = DecisionEngine()
        engine.state = RobotState.VERIFY
        # Threat is not confirmed (suspicious but drops below 0.7)
        engine.fusion_score = 0.55

        engine._handle_state()
        mock_motor_stop.assert_called_once()
        self.assertEqual(engine.state, RobotState.NAVIGATE)

    @patch("m2_motor.motor.set_alarm")
    def test_alarm_state_remains_active_when_high(self, mock_set_alarm):
        engine = DecisionEngine()
        engine.state = RobotState.ALARM
        engine.fusion_score = 0.75

        engine._handle_state()
        mock_set_alarm.assert_called_once_with(led=True, buzzer=True)
        self.assertEqual(engine.state, RobotState.ALARM)

    @patch("m2_motor.motor.set_alarm")
    def test_alarm_clears_when_risk_drops_below_clear_threshold(self, mock_set_alarm):
        engine = DecisionEngine()
        engine.state = RobotState.ALARM
        # Risk drops below config.FUSION_CLEAR_THRESH (0.4)
        engine.fusion_score = 0.35

        engine._handle_state()
        # Verify that set_alarm(led=False, buzzer=False) was called to reset the alarm
        mock_set_alarm.assert_any_call(led=False, buzzer=False)
        self.assertEqual(engine.state, RobotState.NAVIGATE)


if __name__ == "__main__":
    unittest.main()

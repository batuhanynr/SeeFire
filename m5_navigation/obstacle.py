"""
M5 Obstacle avoidance.

Strategy (see navigation_modulu.md §7):
  1. Decide turn direction (camera pixel split → ultrasonic fallback).
  2. Rotate 90° toward open side.
  3. Side-pass: step forward while the LEFT ultrasonic still sees the
     obstacle's surface; the obstacle is cleared when LEFT reading exceeds
     OBSTACLE_CLEAR_CM.
  4. Return to original route line using ENCODER ONLY (no sensors): the
     accumulated side distance is replayed in reverse.
  5. Lateral fine-tune via PositionVerifier.

During side-pass and detour, sector-midpoint snapshot triggers must NOT be
skipped — the navigation loop owns that check via the shared callback.
"""
import logging
import config
import m2_motor
import m3_sensors
import m4_vision

logger = logging.getLogger(__name__)


class ObstacleAvoidance:

    def __init__(self, position_verifier, midpoint_callback=None):
        """
        midpoint_callback: callable(sector_id) → None
            Invoked on each side-pass step so the main loop can check whether
            the sector midpoint was crossed during the detour.
        """
        self._position_verifier = position_verifier
        self._midpoint_callback = midpoint_callback or (lambda _sid: None)

    def avoid(self, sector_id: int) -> None:
        # Net north-progress during bypass is zero (side out, side back).
        # Snapshot odometry so the side moves don't pollute it.
        north_distance_before = m2_motor.get_total_distance_cm()

        direction = self._decide_direction()
        logger.info("[OBSTACLE] Bypass direction: %s", direction)

        if direction == "RIGHT":
            m2_motor.turn_right_90()
            return_first_turn = m2_motor.turn_left_90
        else:
            m2_motor.turn_left_90()
            return_first_turn = m2_motor.turn_right_90

        side_distance_cm = self._side_pass(sector_id, direction)

        # Return to original heading and route line, encoder only.
        return_first_turn()                          # face north
        return_first_turn()                          # face opposite of bypass side (back toward route)
        m2_motor.drive_distance_cm(side_distance_cm)
        if direction == "RIGHT":
            m2_motor.turn_right_90()                 # face north again
        else:
            m2_motor.turn_left_90()

        # Side moves should not count as north-progress.
        m2_motor.set_total_distance_cm(north_distance_before)

        self._position_verifier.verify_and_correct()

    # ------------------------------------------------------------------

    def _decide_direction(self) -> str:
        hint = m4_vision.determine_turn_direction()
        if hint in ("LEFT", "RIGHT"):
            return hint

        reading = m3_sensors.get_navigation_sensors_filtered()
        return "RIGHT" if reading.right_cm > reading.left_cm else "LEFT"

    def _side_pass(self, sector_id: int, direction: str) -> float:
        """Step forward until the obstacle-facing side sensor reports clear.
        Returns total cm traveled sideways (encoder integral)."""
        sensor_attr = "left_cm" if direction == "RIGHT" else "right_cm"
        traveled = 0.0
        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            if getattr(reading, sensor_attr) > config.OBSTACLE_CLEAR_CM:
                logger.info("[OBSTACLE] Cleared after %.1f cm side-pass.", traveled)
                return traveled

            self._midpoint_callback(sector_id)
            m2_motor.drive_distance_cm(config.SIDE_STEP_CM)
            traveled += config.SIDE_STEP_CM

            if traveled > 200.0:  # safety cap
                logger.warning("[OBSTACLE] Side-pass exceeded 200 cm — aborting.")
                return traveled

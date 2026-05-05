"""
M5 Position verification.

Encoder is the primary distance source. The HC-SR04 left/right sensors are
used only at two boundary moments:
  1. start-of-mission: confirm we are placed within tolerance of the route.
  2. after obstacle bypass: correct lateral drift introduced by encoder slip.
"""
import logging
import config
import m3_sensors
import m2_motor

logger = logging.getLogger(__name__)


class PositionVerifier:

    def verify_start(self) -> None:
        """Raise RuntimeError if the robot is not within tolerance of the
        configured start-of-route position."""
        reading = m3_sensors.get_navigation_sensors_filtered()
        left_err = abs(reading.left_cm - config.START_LEFT_CM)
        right_err = abs(reading.right_cm - config.START_RIGHT_CM)

        if left_err > config.POSITION_TOLERANCE_CM or right_err > config.POSITION_TOLERANCE_CM:
            raise RuntimeError(
                "Start position out of tolerance. "
                f"left={reading.left_cm:.1f} (expected {config.START_LEFT_CM:.1f} "
                f"±{config.POSITION_TOLERANCE_CM:.1f}), "
                f"right={reading.right_cm:.1f} (expected {config.START_RIGHT_CM:.1f} "
                f"±{config.POSITION_TOLERANCE_CM:.1f})"
            )
        logger.info("Start position OK: left=%.1f cm, right=%.1f cm",
                    reading.left_cm, reading.right_cm)

    def verify_and_correct(self) -> None:
        """Lateral fine-tune after encoder-driven moves (e.g. obstacle bypass)."""
        reading = m3_sensors.get_navigation_sensors_filtered()
        left_err = reading.left_cm - config.START_LEFT_CM

        if abs(left_err) <= config.POSITION_TOLERANCE_CM:
            return

        if left_err > 0:
            # Drifted away from left wall → correct rightward
            m2_motor.turn_right_90()
            m2_motor.drive_distance_cm(config.FINE_TUNE_STEP_CM)
            m2_motor.turn_left_90()
        else:
            m2_motor.turn_left_90()
            m2_motor.drive_distance_cm(config.FINE_TUNE_STEP_CM)
            m2_motor.turn_right_90()
        logger.info("Lateral correction applied (left_err=%.1f cm)", left_err)

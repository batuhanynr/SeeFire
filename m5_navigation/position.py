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
        """Verify the robot is centered in the corridor.
        If the difference between left and right measurements is greater than 10 cm,
        spin in place until centered, then proceed with navigation."""
        import time
        while True:
            reading = m3_sensors.get_navigation_sensors_filtered()
            diff = abs(reading.left_cm - reading.right_cm)

            if diff <= 10.0:
                logger.info("Start position OK (centered): left=%.1f cm, right=%.1f cm (diff=%.1f cm)",
                            reading.left_cm, reading.right_cm, diff)
                break

            logger.warning(
                "Robot NOT centered! left=%.1f cm, right=%.1f cm (diff=%.1f cm > 10.0 cm). "
                "Rotating in place to align...",
                reading.left_cm, reading.right_cm, diff
            )
            # Spin 90 degrees to indicate off-center and try to find a better alignment
            m2_motor.turn_right_90()
            time.sleep(0.5)

    def verify_and_correct(self) -> None:
        """Lateral fine-tune. Called after bypass and at every waypoint.

        Two-sensor sanity gate: the corrected position is only trusted when
        left + right ≈ expected corridor width. This protects against
        structural elements (columns, recesses) that make a single-sensor
        reading misleading. If the sanity gate fails the correction is
        skipped — the next safe waypoint will retry.
        """
        reading = m3_sensors.get_navigation_sensors_filtered()

        expected_width = config.START_LEFT_CM + config.START_RIGHT_CM
        measured_width = reading.left_cm + reading.right_cm
        # Allow 2× single-sensor tolerance for the combined width.
        width_tol = 2.0 * config.POSITION_TOLERANCE_CM
        if abs(measured_width - expected_width) > width_tol:
            logger.info(
                "Lateral correction skipped: corridor width measured %.1f cm "
                "(expected %.1f ±%.1f). Column or obstacle nearby — trusting "
                "encoder until next safe waypoint.",
                measured_width, expected_width, width_tol,
            )
            return

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

    def align_to_corridor(self) -> None:
        """Align the robot parallel to the corridor walls by minimizing left_cm + right_cm."""
        import time
        logger.info("[ALIGN] Hizalama işlemi başlatılıyor...")
        
        # Get baseline reading
        reading = m3_sensors.get_navigation_sensors_filtered(samples=4)
        best_sum = reading.left_cm + reading.right_cm
        logger.info("[ALIGN] Başlangıç toplam mesafe: %.1f cm (Sol: %.1f, Sağ: %.1f)", 
                    best_sum, reading.left_cm, reading.right_cm)
        
        expected_width = config.START_LEFT_CM + config.START_RIGHT_CM
        width_tol = 2.0 * config.POSITION_TOLERANCE_CM
        if abs(best_sum - expected_width) > width_tol:
            logger.info("[ALIGN] Koridor genişlik testi başarısız: ölçülen %.1f cm (beklenen %.1f ±%.1f). "
                        "Yakında sütun veya engel var, hizalama atlanıyor.", 
                        best_sum, expected_width, width_tol)
            return
        
        # We will try nudging left/right to see if the sum decreases.
        nudge_time = 0.05  # ~4 degrees per nudge
        
        # Step 1: Try turning right slightly
        logger.info("[ALIGN] Sağa ufak dönüş deneniyor...")
        m2_motor.turn_in_place_for_time(direction=+1, duration=nudge_time)
        time.sleep(0.2)
        reading = m3_sensors.get_navigation_sensors_filtered(samples=4)
        sum_right = reading.left_cm + reading.right_cm
        logger.info("[ALIGN] Sağa dönüş sonrası toplam: %.1f cm", sum_right)
        
        if sum_right < best_sum - 0.2:  # Found a better angle turning right
            best_sum = sum_right
            while True:
                logger.info("[ALIGN] İyileşme var, sağa ufak dönüşe devam ediliyor...")
                m2_motor.turn_in_place_for_time(direction=+1, duration=nudge_time)
                time.sleep(0.2)
                reading = m3_sensors.get_navigation_sensors_filtered(samples=4)
                sum_next = reading.left_cm + reading.right_cm
                logger.info("[ALIGN] Sonraki toplam: %.1f cm", sum_next)
                if sum_next < best_sum - 0.2:
                    best_sum = sum_next
                else:
                    # It started increasing, so turn back left once to restore the minimum
                    logger.info("[ALIGN] Artış başladı veya minimumda, geri sola dönülüyor.")
                    m2_motor.turn_in_place_for_time(direction=-1, duration=nudge_time)
                    break
            logger.info("[ALIGN] Hizalama tamamlandı.")
            return
            
        # If right didn't improve, turn back left to original position
        logger.info("[ALIGN] Sağa dönüş iyileştirmedi. Orijinal konuma geri dönülüyor...")
        m2_motor.turn_in_place_for_time(direction=-1, duration=nudge_time)
        time.sleep(0.2)
        
        # Step 2: Try turning left slightly
        logger.info("[ALIGN] Sola ufak dönüş deneniyor...")
        m2_motor.turn_in_place_for_time(direction=-1, duration=nudge_time)
        time.sleep(0.2)
        reading = m3_sensors.get_navigation_sensors_filtered(samples=4)
        sum_left = reading.left_cm + reading.right_cm
        logger.info("[ALIGN] Sola dönüş sonrası toplam: %.1f cm", sum_left)
        
        if sum_left < best_sum - 0.2:  # Found a better angle turning left
            best_sum = sum_left
            while True:
                logger.info("[ALIGN] İyileşme var, sola ufak dönüşe devam ediliyor...")
                m2_motor.turn_in_place_for_time(direction=-1, duration=nudge_time)
                time.sleep(0.2)
                reading = m3_sensors.get_navigation_sensors_filtered(samples=4)
                sum_next = reading.left_cm + reading.right_cm
                logger.info("[ALIGN] Sonraki toplam: %.1f cm", sum_next)
                if sum_next < best_sum - 0.2:
                    best_sum = sum_next
                else:
                    # It started increasing, so turn back right once to restore the minimum
                    logger.info("[ALIGN] Artış başladı veya minimumda, geri sağa dönülüyor.")
                    m2_motor.turn_in_place_for_time(direction=+1, duration=nudge_time)
                    break
            logger.info("[ALIGN] Hizalama tamamlandı.")
            return
            
        # If left didn't improve either, turn back right to original position
        logger.info("[ALIGN] Sola dönüş de iyileştirmedi. Orijinal konuma dönülüyor.")
        m2_motor.turn_in_place_for_time(direction=+1, duration=nudge_time)
        time.sleep(0.2)
        logger.info("[ALIGN] Zaten en uygun açıda. Hizalama tamamlandı.")

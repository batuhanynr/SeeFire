"""
M5 Obstacle avoidance.

Bypass strategy (rectangular detour around an obstacle, RIGHT direction):

    initial state: facing N, obstacle dead ahead at D₀
    1. turn right 90°  (face E)
    2. side-pass east until left_cm > D₀ + Δ        — lateral edge cleared
    3. turn left  90°  (face N)
    4. forward-pass north until left_cm > D₀ + Δ    — obstacle now behind us
    5. turn left  90°  (face W)
    6. drive west by side-pass distance             — back on route line
    7. turn right 90°  (face N)                     — continue route

LEFT bypass is symmetric (swap left/right at every step, swap turn directions).

Wall-hit handling: during the side-pass (step 2) the new "forward" sensor is
`front`; if it drops below WALL_CLEARANCE_CM we've hit the perpendicular
wall. Robot retreats to the initial detection point, undoes the 90° turn,
and the caller retries from the opposite side. Two wall hits → abort.

The forward-pass (step 4) is *real* north progress and is preserved in the
encoder total. Lateral moves (steps 2, 6, and any retreat) roll back the
encoder per step via `_drive_lateral` so `get_total_distance_cm()` always
reflects pure north progress — even *during* a bypass. This lets the
navigation layer trigger a midpoint scan exactly when north progress hits
the sector midpoint, whether or not the robot is on the route line.

Snapshot-callback fires inside both side-pass and forward-pass loops so
sector-midpoint scans are never skipped during a detour.
"""
import logging
import time
import config
import m2_motor
import m3_sensors
import m4_vision

logger = logging.getLogger(__name__)


class ObstacleBlockedError(RuntimeError):
    """Raised when both bypass directions are blocked by walls."""


class ObstacleAvoidance:

    def __init__(self, position_verifier, midpoint_callback=None):
        self._position_verifier = position_verifier
        self._midpoint_callback = midpoint_callback or (lambda _sid: None)

    def avoid(self, sector_id: int, reference_distance: float) -> None:
        """Bypass the obstacle currently in front.

        reference_distance: front_cm at the moment the obstacle was detected.
        """
        direction = self._decide_direction()
        logger.info("[OBSTACLE] D0=%.1f cm. Bypass direction: %s",
                    reference_distance, direction)

        result = self._attempt_bypass(sector_id, direction, reference_distance)

        if result is None:
            other = "LEFT" if direction == "RIGHT" else "RIGHT"
            logger.warning(
                "[OBSTACLE] %s side blocked by wall. Retrying from %s.",
                direction, other,
            )
            result = self._attempt_bypass(sector_id, other, reference_distance)
            direction = other
            if result is None:
                m2_motor.stop()
                raise ObstacleBlockedError(
                    "Both bypass directions blocked by walls."
                )

        side_distance, _forward_distance = result
        self._return_to_route(direction, side_distance)
        # Encoder already reflects only north progress (lateral moves rolled
        # back per step via _drive_lateral). No final correction needed.
        self._position_verifier.verify_and_correct()

    # ------------------------------------------------------------------

    def _attempt_bypass(self, sector_id: int, direction: str,
                        reference_distance: float):
        """Run side-pass + forward-pass for one direction.

        Returns (side_distance, forward_distance) on success, or None if the
        side-pass hit a perpendicular wall (in which case the robot is already
        retreated to the original detection point, facing north).
        """
        logger.info("[BYPASS] Engelden kaçış başlıyor. Referans mesafe (D0): %.1f cm", reference_distance)
        time.sleep(1.0)

        # Step 1: turn toward chosen side.
        if direction == "RIGHT":
            logger.info("[BYPASS] Engelden kaçmak için SAĞA dönülüyor...")
            m2_motor.turn_right_90()
        else:
            logger.info("[BYPASS] Engelden kaçmak için SOLA dönülüyor...")
            m2_motor.turn_left_90()
        time.sleep(1.0)

        # Step 2: side-pass laterally.
        side_distance, wall_hit = self._side_pass(
            sector_id, direction, reference_distance
        )

        if wall_hit:
            self._retreat_from_wall(direction, side_distance)
            return None

        # Step 3: turn back to north.
        if direction == "RIGHT":
            logger.info("[BYPASS] Rota doğrultusuna (KUZEYE) geri dönmek için SOLA dönülüyor...")
            m2_motor.turn_left_90()
        else:
            logger.info("[BYPASS] Rota doğrultusuna (KUZEYE) geri dönmek için SAĞA dönülüyor...")
            m2_motor.turn_right_90()
        time.sleep(1.0)

        # Step 4: forward-pass north until obstacle is behind us.
        forward_distance = self._forward_pass_obstacle(
            sector_id, direction, reference_distance
        )
        return side_distance, forward_distance

    def _retreat_from_wall(self, direction: str, traveled: float) -> None:
        """Drive back along the side axis to the original spot, face north."""
        logger.info("[OBSTACLE] Retreating %.1f cm after wall hit.", traveled)
        if direction == "RIGHT":
            # Currently facing east. Reverse: face west, drive back, face north.
            m2_motor.turn_left_90()   # E → N
            m2_motor.turn_left_90()   # N → W
            if traveled > 0:
                self._drive_lateral(traveled)
            m2_motor.turn_right_90()  # W → N
        else:
            # Currently facing west.
            m2_motor.turn_right_90()  # W → N
            m2_motor.turn_right_90()  # N → E
            if traveled > 0:
                self._drive_lateral(traveled)
            m2_motor.turn_left_90()   # E → N

    def _return_to_route(self, direction: str, side_distance: float) -> None:
        """After forward-pass: face the side axis, drive back, face north."""
        logger.info("[BYPASS-GERİ] Rota çizgisine geri dönme manevrası başlıyor...")
        time.sleep(1.0)
        if direction == "RIGHT":
            logger.info("[BYPASS-GERİ] Rota çizgisine hizalanmak için SOLA dönülüyor...")
            m2_motor.turn_left_90()                       # N → W
            time.sleep(1.0)
            logger.info("[BYPASS-GERİ] %.1f cm yanal geri sürülüyor...", side_distance)
            self._drive_lateral(side_distance)
            time.sleep(1.0)
            logger.info("[BYPASS-GERİ] Rota doğrultusuna (KUZEYE) dönmek için SAĞA dönülüyor...")
            m2_motor.turn_right_90()                      # W → N
        else:
            logger.info("[BYPASS-GERİ] Rota çizgisine hizalanmak için SAĞA dönülüyor...")
            m2_motor.turn_right_90()                      # N → E
            time.sleep(1.0)
            logger.info("[BYPASS-GERİ] %.1f cm yanal geri sürülüyor...", side_distance)
            self._drive_lateral(side_distance)
            time.sleep(1.0)
            logger.info("[BYPASS-GERİ] Rota doğrultusuna (KUZEYE) dönmek için SOLA dönülüyor...")
            m2_motor.turn_left_90()                       # E → N
        time.sleep(1.0)
        logger.info("[BYPASS-GERİ] Rota çizgisine geri dönüldü.")

    @staticmethod
    def _drive_lateral(cm: float) -> None:
        """Drive without polluting the north-progress odometer.

        The encoder integrates *all* forward driving regardless of heading.
        During a bypass the robot drives east/west, which would pollute the
        "how far north have we come?" reading used for sector-midpoint
        detection. This wraps drive_distance_cm with a save-and-restore so
        the encoder ignores the lateral move.
        """
        before = m2_motor.get_total_distance_cm()
        m2_motor.drive_distance_cm(cm)
        m2_motor.set_total_distance_cm(before)

    def _decide_direction(self) -> str:
        hint = m4_vision.determine_turn_direction()
        if hint in ("LEFT", "RIGHT"):
            return hint

        reading = m3_sensors.get_navigation_sensors_filtered()
        return "RIGHT" if reading.right_cm > reading.left_cm else "LEFT"

    def _side_pass(self, sector_id: int, direction: str,
                   reference_distance: float):
        """Step sideways until lateral edge of obstacle passes the clearance
        sensor, or until the perpendicular wall is hit.

        Returns (traveled_cm, wall_hit: bool).
        """
        # After RIGHT turn (facing east): left sensor points north → clearance.
        # After LEFT  turn (facing west): right sensor points north → clearance.
        clearance_attr = "left_cm" if direction == "RIGHT" else "right_cm"
        clear_threshold = reference_distance + config.OBSTACLE_CLEARANCE_DELTA_CM
        traveled = 0.0

        logger.info("[BYPASS-YAN] Yanal geçiş başladı. '%s' sensörü izleniyor. Hedef açıklık: > %.1f cm", clearance_attr, clear_threshold)
        time.sleep(1.0)

        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            clearance = getattr(reading, clearance_attr)
            wall = reading.front_cm

            logger.info("[BYPASS-YAN] Ölçüm: Yan Engel (%s) = %.1f cm | Ön (Duvar): %.1f cm | Yanal Yol: %.1f cm",
                        clearance_attr, clearance, wall, traveled)

            if clearance > clear_threshold:
                logger.info(
                    "[BYPASS-YAN] Engel geçildi (Açıklık: %.1f cm > Eşik: %.1f cm). Ekstra güvenlik adımı atılıyor...",
                    clearance, clear_threshold,
                )
                time.sleep(1.0)
                self._drive_lateral(config.SIDE_STEP_CM)
                traveled += config.SIDE_STEP_CM
                time.sleep(1.0)
                return traveled, False

            if 0 < wall < config.WALL_CLEARANCE_CM:
                logger.warning(
                    "[BYPASS-YAN] HATA: Önümüzde duvar var! Mesafe: %.1f cm. Manevra durduruluyor.",
                    wall,
                )
                time.sleep(1.0)
                return traveled, True

            self._midpoint_callback(sector_id)
            self._drive_lateral(config.SIDE_STEP_CM)
            traveled += config.SIDE_STEP_CM
            time.sleep(0.5)  # adımlar arası yavaşlama

            if traveled > config.SIDE_PASS_SAFETY_CAP_CM:
                logger.warning(
                    "[BYPASS-YAN] Güvenlik sınırı aşıldı (%.0f cm).",
                    config.SIDE_PASS_SAFETY_CAP_CM,
                )
                return traveled, False

    def _forward_pass_obstacle(self, sector_id: int, direction: str,
                               reference_distance: float) -> float:
        """Drive north until the obstacle alongside us has been passed.

        Two-phase state machine:
          A) ACQUIRE — drive forward until the side sensor first sees the
             obstacle close (reading < D₀ + Δ). Needed because right after
             the side-pass we are still south of the obstacle's southern
             edge, so the sensor reads "far".
          B) RELEASE — keep driving until the side sensor reads "far" again
             (> D₀ + Δ), meaning the obstacle's northern edge is behind us.

        After a RIGHT side-pass + turn-back-to-north, the obstacle sits to
        our WEST → check left_cm. After LEFT → check right_cm.
        """
        side_attr = "left_cm" if direction == "RIGHT" else "right_cm"
        threshold = reference_distance + config.OBSTACLE_CLEARANCE_DELTA_CM
        traveled = 0.0
        acquired = False

        logger.info("[BYPASS-İLERİ] Düz ilerleme başladı. '%s' yan sensörü izleniyor. Hedef açıklık: > %.1f cm", side_attr, threshold)
        time.sleep(1.0)

        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            side = getattr(reading, side_attr)

            logger.info("[BYPASS-İLERİ] Ölçüm: Yan Engel (%s) = %.1f cm | Ön (Duvar): %.1f cm | İlerleme: %.1f cm | Algılandı: %s",
                        side_attr, side, reading.front_cm, traveled, acquired)

            if not acquired and side < threshold:
                acquired = True
                logger.info(
                    "[BYPASS-İLERİ] Engel yanımızda tespit edildi. Konum alındı."
                )
            elif acquired and side > threshold:
                logger.info(
                    "[BYPASS-İLERİ] Engel geride kaldı (Açıklık: %.1f cm > Eşik: %.1f cm). Ekstra güvenlik adımları atılıyor...",
                    side, threshold,
                )
                time.sleep(1.0)
                extra_steps = 3
                for step_idx in range(extra_steps):
                    logger.info("[BYPASS-İLERİ] Ekstra güvenlik adımı %d/%d...", step_idx + 1, extra_steps)
                    m2_motor.drive_distance_cm(config.STEP_DISTANCE_CM)
                    traveled += config.STEP_DISTANCE_CM
                    time.sleep(0.5)
                time.sleep(1.0)
                return traveled

            if 0 < reading.front_cm < config.WALL_CLEARANCE_CM:
                logger.warning(
                    "[BYPASS-İLERİ] Önümüzde duvar var! Mesafe: %.1f cm. Sürüş durduruluyor.",
                    reading.front_cm,
                )
                time.sleep(1.0)
                return traveled

            self._midpoint_callback(sector_id)
            m2_motor.drive_distance_cm(config.STEP_DISTANCE_CM)
            traveled += config.STEP_DISTANCE_CM
            time.sleep(0.5)  # adımlar arası yavaşlama

            if traveled > config.FORWARD_PASS_SAFETY_CAP_CM:
                logger.warning(
                    "[BYPASS-İLERİ] İlerleme güvenlik sınırı aşıldı (%.0f cm).",
                    config.FORWARD_PASS_SAFETY_CAP_CM,
                )
                return traveled

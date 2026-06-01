"""
M5 Navigation & Mapping.

Waypoint-driven south→north traversal. The route is split into sectors;
the robot stops for a snapshot at each sector midpoint and at each waypoint
(sector end). Encoder is the primary distance source. Front HC-SR04 triggers
obstacle avoidance.

Snapshot triggers MUST fire even during obstacle bypass — sector midpoints
are not skipped under any condition.
"""
import logging
import time

import config
import m2_motor
import m3_sensors
import m4_vision

from .position import PositionVerifier
from .obstacle import ObstacleAvoidance

logger = logging.getLogger(__name__)


class NavigationController:

    def __init__(self, snapshot_callback=None):
        """
        snapshot_callback: callable(label: str) → None
            Hook for M6/M7 to capture and log a snapshot. If None, vision is
            polled directly (no logging).
        """
        self._snapshot_callback = snapshot_callback or self._default_snapshot
        self._position = PositionVerifier()
        self._sector_midpoint_cm = 0.0
        self._sector_midpoint_passed = False
        self._current_sector = 0
        self._obstacle = ObstacleAvoidance(
            self._position,
            midpoint_callback=self._check_midpoint,
        )

    # ------------------------------------------------------------------

    def start(self) -> None:
        logger.info("[NAV] Verifying start position...")
        self._position.verify_start()

    def run(self, waypoints=None) -> None:
        if waypoints is None:
            waypoints = config.WAYPOINTS

        self.start()

        for target_cm, sector_id in waypoints:
            self._traverse_sector(target_cm, sector_id)

        logger.info("[NAV] All sectors complete.")
        self.shutdown()

    def shutdown(self) -> None:
        m2_motor.stop()
        m4_vision.close()

    # ------------------------------------------------------------------

    def _traverse_sector(self, target_cm: float, sector_id: int) -> None:
        current_cm = m2_motor.get_total_distance_cm()
        self._sector_midpoint_cm = current_cm + (target_cm - current_cm) / 2.0
        self._sector_midpoint_passed = False
        self._current_sector = sector_id

        logger.info("[SECTOR %d] Start. Target=%.1f cm, midpoint=%.1f cm",
                    sector_id, target_cm, self._sector_midpoint_cm)

        while m2_motor.get_total_distance_cm() < target_cm:
            self._check_midpoint(sector_id)

            # Filtered (median of 3) read: protects D₀ from a single noisy
            # HC-SR04 reading. A bad spike would otherwise distort the
            # clearance threshold inside the bypass.
            reading = m3_sensors.get_navigation_sensors_filtered()
            front = reading.front_cm

            if front <= 0:
                logger.warning("[NAV] Front sensor invalid — taking safe step.")
                m2_motor.drive_distance_cm(config.STEP_DISTANCE_CM)
                continue

            if front > config.OBSTACLE_THRESHOLD_CM:
                m2_motor.drive_distance_cm(config.STEP_DISTANCE_CM)
            else:
                logger.info("[OBSTACLE] front=%.1f cm — initiating avoidance.", front)
                self._obstacle.avoid(sector_id, reference_distance=front)

        # Sector end (waypoint)
        logger.info("[WAYPOINT] Sector %d end.", sector_id)
        self._snapshot(f"sector-{sector_id}-waypoint")
        # Periodic lateral drift correction: integrates encoder slip and
        # turn-angle error that accumulate between bypasses.
        self._position.verify_and_correct()

    def _check_midpoint(self, sector_id: int) -> None:
        if self._sector_midpoint_passed:
            return
        if m2_motor.get_total_distance_cm() >= self._sector_midpoint_cm:
            self._scan_four_directions(f"sector-{sector_id}-midpoint")
            self._sector_midpoint_passed = True

    def _snapshot(self, label: str) -> None:
        """Single-frame capture at current heading. Used at waypoints."""
        m2_motor.stop()
        time.sleep(0.3)
        self._snapshot_callback(label)
        time.sleep(0.2)

    def _scan_four_directions(self, label_prefix: str) -> None:
        """Stop, capture N/E/S/W frames, return to original heading.

        Triggered at sector midpoints. The robot is guaranteed to be facing
        north when this is called: midpoints can only be crossed during
        north-facing driving (either a normal forward step or the bypass
        forward-pass), and lateral moves roll back the north-progress
        encoder so they never trigger this check.

        Net rotation is 4 × 90° = 360° → robot ends facing north again, in
        the same position. Caller can resume whatever it was doing without
        any pose correction.
        """
        m2_motor.stop()
        time.sleep(0.3)
        for direction_label in ("N", "E", "S", "W"):
            full_label = f"{label_prefix}-{direction_label}"
            logger.info("[SCAN] %s", full_label)
            self._snapshot_callback(full_label)
            time.sleep(0.2)
            m2_motor.turn_right_90()
            time.sleep(0.1)

    @staticmethod
    def _default_snapshot(label: str) -> None:
        logger.info("[SNAPSHOT] %s", label)
        m4_vision.capture_frame()

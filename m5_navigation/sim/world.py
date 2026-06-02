"""2D ground-truth world for the M5 simulator.

Coordinate frame: x = east (cm), y = north (cm). Heading is degrees in math
convention (CCW from +x). The robot starts facing north → heading = 90°.

Sensor angles relative to heading:
  front =   0°   (along heading)
  left  = +90°   (CCW)
  right = -90°   (CW)

Obstacles and the outer map are axis-aligned rectangles. ray_cast() returns
distance from a point along a direction to the nearest segment of any
rectangle (including the outer walls).
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Obstacle:
    x: float        # left edge (cm)
    y: float        # bottom edge (cm)
    w: float        # width (cm)
    h: float        # height (cm)

    def segments(self):
        x0, y0, x1, y1 = self.x, self.y, self.x + self.w, self.y + self.h
        return [
            ((x0, y0), (x1, y0)),  # bottom
            ((x1, y0), (x1, y1)),  # right
            ((x1, y1), (x0, y1)),  # top
            ((x0, y1), (x0, y0)),  # left
        ]


@dataclass
class Frame:
    label: str
    x: float
    y: float
    heading_deg: float
    left_cm: float
    front_cm: float
    right_cm: float


@dataclass
class Robot:
    x: float
    y: float
    heading_deg: float = 90.0  # facing north


def _ray_segment_distance(ox, oy, dx, dy, ax, ay, bx, by):
    """Distance from (ox,oy) along unit (dx,dy) to segment (ax,ay)-(bx,by).

    Returns None if no forward intersection.
    """
    sx, sy = bx - ax, by - ay
    denom = dx * sy - dy * sx
    if abs(denom) < 1e-9:
        return None
    t = ((ax - ox) * sy - (ay - oy) * sx) / denom    # along ray
    u = ((ax - ox) * dy - (ay - oy) * dx) / denom    # along segment
    if t < 0 or u < 0 or u > 1:
        return None
    return t


class World:
    """Top-down map + robot + sensor model + history recorder."""

    MAX_RANGE_CM = 400.0
    FRONT_COLLISION_MARGIN_CM = 1.0

    def __init__(self, width: float, height: float,
                 obstacles: Optional[List[Obstacle]] = None,
                 robot: Optional[Robot] = None,
                 turn_hint: Optional[str] = None):
        self.width = width
        self.height = height
        self.obstacles: List[Obstacle] = obstacles or []
        self.robot = robot or Robot(x=width / 2.0, y=0.0)
        self.turn_hint = turn_hint   # forced m4_vision result, or None
        self._total_distance_cm: float = 0.0
        self.frames: List[Frame] = []
        self._record("INIT")

    # ----- ray casting & sensors -------------------------------------

    def _all_segments(self):
        # Outer walls (inward-facing rectangle).
        outer = Obstacle(0, 0, self.width, self.height).segments()
        for seg in outer:
            yield seg
        for ob in self.obstacles:
            for seg in ob.segments():
                yield seg

    def ray_cast(self, ox, oy, angle_deg) -> float:
        rad = math.radians(angle_deg)
        dx, dy = math.cos(rad), math.sin(rad)
        best = self.MAX_RANGE_CM
        for (ax, ay), (bx, by) in self._all_segments():
            d = _ray_segment_distance(ox, oy, dx, dy, ax, ay, bx, by)
            if d is not None and 0 < d < best:
                best = d
        return best

    def sensor_readings(self) -> Tuple[float, float, float]:
        """Returns (left_cm, front_cm, right_cm) using robot pose."""
        h = self.robot.heading_deg
        left  = self.ray_cast(self.robot.x, self.robot.y, h + 90.0)
        front = self.ray_cast(self.robot.x, self.robot.y, h)
        right = self.ray_cast(self.robot.x, self.robot.y, h - 90.0)
        return left, front, right

    # ----- motor primitives (used by mock_drivers) -------------------

    def drive_distance_cm(self, cm: float) -> None:
        if cm <= 0:
            return
        front = self.ray_cast(self.robot.x, self.robot.y, self.robot.heading_deg)
        # Stop just short of contact if the requested move would collide.
        max_safe = max(0.0, front - self.FRONT_COLLISION_MARGIN_CM)
        actual = min(cm, max_safe)
        rad = math.radians(self.robot.heading_deg)
        self.robot.x += actual * math.cos(rad)
        self.robot.y += actual * math.sin(rad)
        self._total_distance_cm += actual
        self._record(f"drive {actual:.1f} cm" + (" (CLIPPED)" if actual < cm else ""))

    def turn_left_90(self) -> None:
        self.robot.heading_deg = (self.robot.heading_deg + 90.0) % 360.0
        self._record("turn LEFT 90°")

    def turn_right_90(self) -> None:
        self.robot.heading_deg = (self.robot.heading_deg - 90.0) % 360.0
        self._record("turn RIGHT 90°")

    def stop(self) -> None:
        self._record("stop")

    def get_total_distance_cm(self) -> float:
        return self._total_distance_cm

    def set_total_distance_cm(self, value: float) -> None:
        self._total_distance_cm = value

    # ----- bookkeeping -----------------------------------------------

    def _record(self, label: str) -> None:
        l, f, r = self.sensor_readings()
        self.frames.append(Frame(
            label=label,
            x=self.robot.x, y=self.robot.y, heading_deg=self.robot.heading_deg,
            left_cm=l, front_cm=f, right_cm=r,
        ))

    def snapshot_event(self, label: str) -> None:
        """Called by NavigationController via snapshot_callback."""
        self._record(f"SNAPSHOT: {label}")

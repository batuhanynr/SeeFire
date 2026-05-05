"""
M4 AI & Vision

Two responsibilities:
  1. Fire/smoke classification (YOLOv8n) - to be implemented.
  2. Obstacle turn-direction hint for M5 navigation: given a frame from the
     forward camera, decide whether more free space lies to the LEFT or RIGHT
     of the obstacle in front. Pixel-based, not metric.

Mock fallback: if OpenCV/numpy unavailable, returns None so callers fall back
to ultrasonic-only logic.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    logger.warning("OpenCV/numpy not available. M4 vision running in MOCK MODE.")
    CV_AVAILABLE = False


class VisionM4:
    def __init__(self):
        self._capture = None

    def init(self) -> bool:
        if not CV_AVAILABLE:
            logger.info("[MOCK] M4 Vision initialized.")
            return True
        try:
            self._capture = cv2.VideoCapture(0)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Warm-up: discard first few frames (auto-exposure settling)
            for _ in range(5):
                self._capture.read()
            logger.info("M4 Vision camera opened.")
        except Exception as e:
            logger.error("Camera open failed: %s", e)
            self._capture = None
        return True

    def capture_frame(self):
        if not CV_AVAILABLE or self._capture is None:
            return None
        ok, frame = self._capture.read()
        return frame if ok else None

    def determine_turn_direction(self, frame=None) -> Optional[str]:
        """
        Decide which side has more free space around an obstacle ahead.

        Returns "LEFT", "RIGHT", or None if undecidable. None signals the
        caller (M5 obstacle avoidance) to fall back to ultrasonic comparison.
        """
        if not CV_AVAILABLE:
            return None
        if frame is None:
            frame = self.capture_frame()
        if frame is None:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        h, w = edges.shape
        roi = edges[h // 2:, :]  # focus on lower half (floor noise less, obstacle more)
        cols = np.where(roi.any(axis=0))[0]

        if len(cols) == 0:
            return None  # no obstacle silhouette detected

        left_gap = int(cols[0])
        right_gap = int(w - cols[-1])
        return "RIGHT" if right_gap > left_gap else "LEFT"

    def close(self) -> None:
        if CV_AVAILABLE and self._capture is not None:
            self._capture.release()
            self._capture = None


_instance = VisionM4()
init = _instance.init
capture_frame = _instance.capture_frame
determine_turn_direction = _instance.determine_turn_direction
close = _instance.close

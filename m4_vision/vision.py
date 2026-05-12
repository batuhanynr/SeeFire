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
import threading
import time
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
        self._lock = threading.Lock()
        self._current_frame = None
        self._yolo_result = {"fire_conf": 0.0, "smoke_conf": 0.0}
        self._running = False
        self._thread = None

    def init(self) -> bool:
        if not CV_AVAILABLE:
            logger.info("[MOCK] M4 Vision initialized.")
            return True
        try:
            self._capture = cv2.VideoCapture(0)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # Low res (320x240) for INT8 YOLO speed on Pi
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            # Warm-up
            for _ in range(3):
                self._capture.read()
            
            # Start background thread
            self._running = True
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()
            
            logger.info("M4 Vision camera and background thread started.")
        except Exception as e:
            logger.error("Camera open failed: %s", e)
            self._capture = None
        return True

    def _update_loop(self):
        """Background thread to capture frames and run YOLO inference."""
        while self._running:
            if self._capture is None:
                time.sleep(0.5)
                continue
                
            ok, frame = self._capture.read()
            if ok:
                # YOLOv8n inference placeholder (for Faz 1 mock)
                # In real HW, this is where we'd call the model
                mock_fire = 0.0
                mock_smoke = 0.0
                
                with self._lock:
                    self._current_frame = frame
                    self._yolo_result = {"fire_conf": mock_fire, "smoke_conf": mock_smoke}
            
            # Target ~3-5 FPS to avoid overheating Pi
            time.sleep(0.2)

    def capture_frame(self):
        """Returns the most recent frame from the background thread (thread-safe)."""
        if not CV_AVAILABLE:
            return None
        with self._lock:
            return self._current_frame.copy() if self._current_frame is not None else None

    def get_fire_confidence(self) -> float:
        """Returns the latest YOLO fire confidence (thread-safe)."""
        with self._lock:
            return self._yolo_result["fire_conf"]

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
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if CV_AVAILABLE and self._capture is not None:
            self._capture.release()
            self._capture = None


_instance = VisionM4()
init = _instance.init
capture_frame = _instance.capture_frame
get_fire_confidence = _instance.get_fire_confidence
determine_turn_direction = _instance.determine_turn_direction
close = _instance.close

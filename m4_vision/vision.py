"""
M4 AI & Vision

Two responsibilities:
  1. Fire/smoke classification (YOLOv8n) — runs in a background thread.
  2. Obstacle turn-direction hint for M5 navigation — Canny edge pixel heuristic.

Camera aspect-ratio fix:
  cv2.VideoCapture.set() is not guaranteed on Linux/V4L2; the driver may silently
  serve a different resolution.  _letterbox_crop() always produces
  CAMERA_TARGET_WIDTH × CAMERA_TARGET_HEIGHT frames regardless of what the driver
  provides, preserving aspect ratio via center-crop (no black bars, no squish).

Mock fallback:
  SEEFIRE_FORCE_MOCK=1  OR  OpenCV not installed → CV_AVAILABLE=False.
  All public methods return safe defaults (None / 0.0) without raising.
"""
import logging
import os
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler
from typing import Optional

import config

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s=%r; using %.2f", name, os.environ.get(name), default)
        return default

# ---------------------------------------------------------------------------
# Optional heavy dependencies
# ---------------------------------------------------------------------------

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = os.environ.get("SEEFIRE_FORCE_MOCK") != "1"
except ImportError:
    logger.warning("OpenCV/numpy not available — M4 running in MOCK MODE.")
    CV_AVAILABLE = False

YOLO_AVAILABLE = False
_yolo_model = None
_obstacle_model = None

if CV_AVAILABLE:
    try:
        from ultralytics import YOLO as _YOLO_cls  # type: ignore
        if os.path.exists(config.YOLO_MODEL_PATH):
            _yolo_model = _YOLO_cls(config.YOLO_MODEL_PATH)
            YOLO_AVAILABLE = True
            logger.info("YOLOv8n fire model loaded from %s", config.YOLO_MODEL_PATH)
        else:
            logger.warning(
                "YOLO model not found at %s — fire_conf will be 0.0 until model is placed there.",
                config.YOLO_MODEL_PATH,
            )
        if os.path.exists(config.OBSTACLE_MODEL_PATH):
            _obstacle_model = _YOLO_cls(config.OBSTACLE_MODEL_PATH)
            logger.info("YOLOv8n obstacle model loaded from %s", config.OBSTACLE_MODEL_PATH)
        else:
            logger.warning("Obstacle model not found at %s — falling back to Canny.", config.OBSTACLE_MODEL_PATH)
    except ImportError:
        logger.warning("ultralytics not installed — fire/obstacle detection disabled.")
    except Exception as exc:
        logger.warning("YOLO model load failed: %s", exc)


# ---------------------------------------------------------------------------
# MJPEG stream server (Pi → PC canlı görüntü)
# SEEFIRE_STREAM=1  →  http://<pi-ip>:8080/  veya  /stream
# ---------------------------------------------------------------------------

class _MjpegServer(threading.Thread):
    """Stdlib-only MJPEG HTTP server. No Flask dependency."""

    def __init__(self, get_frame_fn, port: int = 8080):
        super().__init__(daemon=True, name="mjpeg-server")
        self._get_frame = get_frame_fn
        self._port = port
        self._fps = max(1.0, _env_float("SEEFIRE_STREAM_FPS", 20.0))
        self._quality = int(max(30, min(95, _env_float("SEEFIRE_STREAM_JPEG_QUALITY", 70.0))))

    def run(self):
        get_frame = self._get_frame
        frame_interval = 1.0 / self._fps
        jpeg_quality = self._quality

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/stream", "/"):
                    if self.path == "/":
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(
                            b"<html><body style='background:#000;margin:0'>"
                            b"<img src='/stream' style='width:100%'>"
                            b"</body></html>"
                        )
                        return
                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "multipart/x-mixed-replace; boundary=frame",
                    )
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    while True:
                        loop_start = time.monotonic()
                        frame = get_frame()
                        if frame is None:
                            time.sleep(0.1)
                            continue
                        ok, buf = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
                        )
                        if not ok:
                            continue
                        data = buf.tobytes()
                        try:
                            self.wfile.write(
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                + f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
                                + data
                                + b"\r\n"
                            )
                            self.wfile.flush()
                        except Exception:
                            return
                        elapsed = time.monotonic() - loop_start
                        if elapsed < frame_interval:
                            time.sleep(frame_interval - elapsed)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *_):
                pass

        socketserver.TCPServer.allow_reuse_address = True
        class _ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        with _ThreadingTCPServer(("", self._port), _Handler) as srv:
            logger.info(
                "MJPEG stream başlatıldı → http://<pi-ip>:%d/ (%.1f FPS, JPEG q=%d)",
                self._port,
                self._fps,
                self._quality,
            )
            srv.serve_forever()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _letterbox_crop(frame: "np.ndarray", target_w: int, target_h: int) -> "np.ndarray":
    """Resize *frame* to *target_w* × *target_h* without distortion.

    Scales so the smaller dimension fills the target, then center-crops the
    larger dimension.  Result is always exactly target_w × target_h with no
    black bars and no aspect-ratio squishing.
    """
    src_h, src_w = frame.shape[:2]
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(round(src_w * scale))
    new_h = int(round(src_h * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    x0 = (new_w - target_w) // 2
    y0 = (new_h - target_h) // 2
    return resized[y0: y0 + target_h, x0: x0 + target_w]


def _run_yolo(frame: "np.ndarray") -> tuple[float, float, Optional[str]]:
    """Run YOLOv8n inference and return (fire_conf, smoke_conf, fire_side).

    fire_side: 'LEFT' | 'RIGHT' | None — frame side of highest-confidence fire box.
    Returns (0.0, 0.0, None) if the model is absent or no relevant detections.
    """
    if not YOLO_AVAILABLE or _yolo_model is None:
        return 0.0, 0.0, None

    frame_w = frame.shape[1]
    yolo_input = cv2.resize(frame, (320, 320))
    try:
        results = _yolo_model(yolo_input, verbose=False, conf=config.VISION_CONF_THRESHOLD)
    except Exception as exc:
        logger.warning("YOLO inference error: %s", exc)
        return 0.0, 0.0, None

    fire_conf = 0.0
    smoke_conf = 0.0
    best_fire_cx = None  # center-x of highest-confidence fire box (in original frame coords)
    for r in results:
        for box in r.boxes:
            cls_name = _yolo_model.names[int(box.cls[0])].lower()
            conf_val = float(box.conf[0])
            if cls_name in ("fire", "flame"):
                if conf_val > fire_conf:
                    fire_conf = conf_val
                    # xyxy coords are in 320×320 space — map back to original frame width
                    cx_320 = float((box.xyxy[0][0] + box.xyxy[0][2]) / 2)
                    best_fire_cx = cx_320 / 320.0  # normalised 0–1
            elif cls_name == "smoke":
                smoke_conf = max(smoke_conf, conf_val)

    fire_side = None
    if best_fire_cx is not None:
        fire_side = "LEFT" if best_fire_cx < 0.5 else "RIGHT"
    return fire_conf, smoke_conf, fire_side


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class VisionM4:
    def __init__(self):
        self._capture = None
        self._lock = threading.Lock()
        self._current_frame = None
        self._yolo_result = {"fire_conf": 0.0, "smoke_conf": 0.0, "fire_side": None}
        self._running = False
        self._thread: Optional[threading.Thread] = None  # backward-compatible alias
        self._capture_thread: Optional[threading.Thread] = None
        self._yolo_thread: Optional[threading.Thread] = None
        self._actual_w: int = config.CAMERA_TARGET_WIDTH
        self._actual_h: int = config.CAMERA_TARGET_HEIGHT

    def init(self) -> bool:
        if not CV_AVAILABLE:
            logger.info("[MOCK] M4 Vision initialized.")
            return True
        try:
            self._capture = cv2.VideoCapture(0)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_TARGET_WIDTH)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_TARGET_HEIGHT)

            # Verify — V4L2 may silently ignore our request
            self._actual_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._actual_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if (self._actual_w != config.CAMERA_TARGET_WIDTH
                    or self._actual_h != config.CAMERA_TARGET_HEIGHT):
                logger.warning(
                    "Camera driver served %dx%d instead of %dx%d — "
                    "frames will be letterbox-cropped to target size.",
                    self._actual_w, self._actual_h,
                    config.CAMERA_TARGET_WIDTH, config.CAMERA_TARGET_HEIGHT,
                )

            # Warm-up: discard first few frames (auto-exposure settling)
            for _ in range(5):
                self._capture.read()

            self._running = True
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="vision-capture",
            )
            self._capture_thread.start()
            self._thread = self._capture_thread

            if YOLO_AVAILABLE:
                self._yolo_thread = threading.Thread(
                    target=self._yolo_loop,
                    daemon=True,
                    name="vision-yolo",
                )
                self._yolo_thread.start()
            else:
                logger.info("M4 YOLO loop disabled; fire/smoke confidence remains 0.0.")

            logger.info(
                "M4 Vision started (driver=%dx%d, target=%dx%d, YOLO=%s)",
                self._actual_w, self._actual_h,
                config.CAMERA_TARGET_WIDTH, config.CAMERA_TARGET_HEIGHT,
                YOLO_AVAILABLE,
            )

            # Opsiyonel MJPEG stream: SEEFIRE_STREAM=1 ile etkinleştir
            if os.environ.get("SEEFIRE_STREAM") == "1":
                port = int(os.environ.get("SEEFIRE_STREAM_PORT", "8080"))
                _MjpegServer(self.capture_frame, port).start()

        except Exception as exc:
            logger.error("Camera open failed: %s", exc)
            self._capture = None
        return True

    def _capture_loop(self) -> None:
        """Read camera frames at stream-friendly FPS without blocking on YOLO."""
        tw = config.CAMERA_TARGET_WIDTH
        th = config.CAMERA_TARGET_HEIGHT
        capture_fps = max(1.0, _env_float("SEEFIRE_CAPTURE_FPS", _env_float("SEEFIRE_VISION_FPS", 20.0)))
        frame_interval = 1.0 / capture_fps
        logger.info("M4 capture loop running at %.1f FPS target", capture_fps)
        while self._running:
            loop_start = time.monotonic()
            if self._capture is None:
                time.sleep(0.5)
                continue

            ok, raw = self._capture.read()
            if not ok:
                time.sleep(0.1)
                continue

            # Fix aspect-ratio distortion from driver resolution mismatch
            if raw.shape[1] != tw or raw.shape[0] != th:
                raw = _letterbox_crop(raw, tw, th)

            with self._lock:
                self._current_frame = raw

            elapsed = time.monotonic() - loop_start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    def _yolo_loop(self) -> None:
        """Run fire/smoke YOLO on the latest frame at a lower independent FPS."""
        yolo_fps = max(0.2, _env_float("SEEFIRE_YOLO_FPS", 5.0))
        frame_interval = 1.0 / yolo_fps
        logger.info("M4 YOLO loop running at %.1f FPS target", yolo_fps)
        while self._running:
            loop_start = time.monotonic()
            with self._lock:
                frame = self._current_frame.copy() if self._current_frame is not None else None

            if frame is None:
                time.sleep(0.1)
                continue

            fire_conf, smoke_conf, fire_side = _run_yolo(frame)
            with self._lock:
                self._yolo_result = {
                    "fire_conf": fire_conf,
                    "smoke_conf": smoke_conf,
                    "fire_side": fire_side,
                }

            elapsed = time.monotonic() - loop_start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    def capture_frame(self) -> "Optional[np.ndarray]":
        """Return a copy of the latest frame (thread-safe). None in mock mode."""
        if not CV_AVAILABLE:
            return None
        with self._lock:
            return self._current_frame.copy() if self._current_frame is not None else None

    def get_fire_confidence(self) -> float:
        """Latest YOLO fire confidence score [0.0–1.0] (thread-safe)."""
        with self._lock:
            return self._yolo_result["fire_conf"]

    def get_smoke_confidence(self) -> float:
        """Latest YOLO smoke confidence score [0.0–1.0] (thread-safe)."""
        with self._lock:
            return self._yolo_result["smoke_conf"]

    def determine_turn_direction(self, frame: "Optional[np.ndarray]" = None) -> Optional[str]:
        """Return "LEFT", "RIGHT", or None (→ fall back to ultrasonic).

        Priority:
          1. YOLO obstacle detection (semantic, bounding-box area comparison)
          2. Canny edge gap heuristic (structural, works for walls)
          3. None → caller falls back to ultrasonic sensors
        """
        if not CV_AVAILABLE:
            return None
        if frame is None:
            frame = self.capture_frame()
        if frame is None:
            return None

        yolo_hint = self._yolo_obstacle_hint(frame)
        if yolo_hint is not None:
            logger.debug("[VISION] YOLO obstacle hint: %s", yolo_hint)
            return yolo_hint

        return self._pixel_count_direction_hint(frame)

    def _yolo_obstacle_hint(self, frame: "np.ndarray") -> Optional[str]:
        """YOLO-based direction: compare total obstacle bounding-box area on each side."""
        if _obstacle_model is None:
            return None

        h, w = frame.shape[:2]
        roi = frame[h // 2:, :]  # lower half — obstacles prominent here
        roi_area = float(roi.shape[0] * roi.shape[1])

        try:
            results = _obstacle_model(
                roi, verbose=False,
                conf=config.OBSTACLE_CONF_THRESHOLD,
                classes=config.OBSTACLE_CLASSES,
            )
        except Exception as exc:
            logger.warning("Obstacle YOLO error: %s", exc)
            return None

        left_area = 0.0
        right_area = 0.0
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                box_area = (x2 - x1) * (y2 - y1)
                center_x = (x1 + x2) / 2
                if center_x < w / 2:
                    left_area += box_area
                else:
                    right_area += box_area

        # Ignore detections too small to matter (< 5% of ROI)
        if (left_area + right_area) < roi_area * 0.05:
            return None

        return "RIGHT" if left_area > right_area else "LEFT"

    def _pixel_count_direction_hint(self, frame: "np.ndarray") -> Optional[str]:
        """Pixel-count obstacle heuristic.

        1. Convert to grayscale → Gaussian blur → Canny edges.
        2. Focus on lower half of frame (where close obstacles dominate).
        3. Count edge pixels in left half vs right half.
        4. Fewer edge pixels = less obstacle = more free space → go that way.

        This is more robust than the gap approach: it considers the full
        density of obstacles across each side, not just the outermost edge.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        h, w = edges.shape
        roi = edges[h // 2:, :]  # lower half — close obstacles prominent here

        left_pixels = int(roi[:, : w // 2].sum() // 255)
        right_pixels = int(roi[:, w // 2 :].sum() // 255)

        total = left_pixels + right_pixels
        if total < 20:  # too few edges → no significant obstacle, let ultrasonic decide
            return None

        logger.debug("[VISION] Pixel count — left: %d  right: %d", left_pixels, right_pixels)
        return "RIGHT" if left_pixels > right_pixels else "LEFT"

    def get_fire_side(self) -> Optional[str]:
        """'LEFT' | 'RIGHT' | None — frame side where fire was last detected (thread-safe)."""
        with self._lock:
            return self._yolo_result.get("fire_side")

    def get_heading_correction(self, frame: "Optional[np.ndarray]" = None) -> Optional[str]:
        """Detect forward-heading drift using far-field edge symmetry.

        Looks at the upper third of the frame (far horizon) where the robot is
        heading. Symmetric edge density → on course. Asymmetry → drift.

        Returns:
          "DRIFT_LEFT"  — robot veering left of target; nudge right to correct.
          "DRIFT_RIGHT" — robot veering right of target; nudge left to correct.
          None          — heading looks straight or not enough visual information.

        Designed for indoor environments with walls/furniture as reference features.
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
        # Upper third = far field — where we're actually heading
        far = edges[: h // 3, :]
        left_cnt = int(far[:, : w // 2].sum() // 255)
        right_cnt = int(far[:, w // 2 :].sum() // 255)
        total = left_cnt + right_cnt

        if total < 15:  # insufficient visual features
            return None

        # imbalance > 0 → more edges on left → robot drifting right (left wall closer)
        imbalance = (left_cnt - right_cnt) / total
        if abs(imbalance) < 0.20:  # within 20% dead band → no correction needed
            return None

        direction = "DRIFT_RIGHT" if imbalance > 0 else "DRIFT_LEFT"
        logger.debug("[VISION] Heading — left: %d  right: %d  imbalance: %.2f → %s",
                     left_cnt, right_cnt, imbalance, direction)
        return direction

    def close(self) -> None:
        self._running = False
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=1.0)
            self._capture_thread = None
            self._thread = None
        if self._yolo_thread is not None:
            self._yolo_thread.join(timeout=1.0)
            self._yolo_thread = None
        if CV_AVAILABLE and self._capture is not None:
            self._capture.release()
            self._capture = None


# ---------------------------------------------------------------------------
# Module-level singleton (matches existing __init__.py API)
# ---------------------------------------------------------------------------

_instance = VisionM4()
init = _instance.init
capture_frame = _instance.capture_frame
get_fire_confidence = _instance.get_fire_confidence
get_smoke_confidence = _instance.get_smoke_confidence
get_fire_side = _instance.get_fire_side
determine_turn_direction = _instance.determine_turn_direction
get_heading_correction = _instance.get_heading_correction
close = _instance.close

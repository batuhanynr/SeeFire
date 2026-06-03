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
# Fire alarm notification state
# ---------------------------------------------------------------------------

_alarm_active = threading.Event()
_alarm_confirmed = threading.Event()
_alarm_payload: dict = {}


def trigger_fire_alarm(data: dict) -> None:
    """Set by M6 when fire is detected. Activates alarm page on web UI."""
    global _alarm_payload
    _alarm_payload = dict(data)
    _alarm_confirmed.clear()
    _alarm_active.set()
    logger.error("[ALARM] Yangın alarmı tetiklendi: %s", data)


def is_alarm_confirmed() -> bool:
    """True after user clicks OK on the alarm web page."""
    return _alarm_confirmed.is_set()


def clear_fire_alarm() -> None:
    """Reset alarm state after acknowledgment."""
    global _alarm_payload
    _alarm_active.clear()
    _alarm_confirmed.clear()
    _alarm_payload = {}
    logger.info("[ALARM] Yangın alarmı sıfırlandı.")


# ---------------------------------------------------------------------------
# MJPEG stream + alarm notification server
# Her zaman başlar (SEEFIRE_STREAM bağımsız) — port: SEEFIRE_STREAM_PORT (def 8080)
# ---------------------------------------------------------------------------

class _MjpegServer(threading.Thread):
    """Stdlib-only HTTP server: MJPEG stream + fire alarm page."""

    def __init__(self, get_frame_fn, port: int = 8080):
        super().__init__(daemon=True, name="mjpeg-server")
        self._get_frame = get_frame_fn
        self._port = port

    def run(self):
        get_frame = self._get_frame

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if _alarm_active.is_set():
                    self._serve_alarm_page()
                    return
                if self.path == "/stream":
                    self._serve_mjpeg(get_frame)
                elif self.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body style='background:#000;margin:0;color:#0f0;font-family:monospace'>"
                        b"<img src='/stream' style='width:100%;display:block'>"
                        b"<p style='text-align:center;padding:8px'>SeeFire - Canli Kamera</p>"
                        b"</body></html>"
                    )
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path == "/ok":
                    _alarm_confirmed.set()
                    self.send_response(303)
                    self.send_header("Location", "/")
                    self.end_headers()
                    logger.info("[ALARM] Kullanici alarmi onayladi (web OK butonu).")
                else:
                    self.send_response(404)
                    self.end_headers()

            def _serve_alarm_page(self):
                p = _alarm_payload
                fire_pct  = int(p.get("fire_conf",  0.0) * 100)
                smoke_raw = p.get("smoke", 0)
                temp_c    = p.get("temp",  0.0)
                score     = p.get("score", 0.0)
                ts        = p.get("time",  "—")
                html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="3">
<title>SeeFire — YANGIN ALARMI</title>
<style>
  body{{margin:0;background:#1a0000;color:#ff4444;font-family:monospace;
       display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh}}
  h1{{font-size:2.5rem;text-shadow:0 0 20px #ff0000;animation:blink 0.8s step-end infinite}}
  @keyframes blink{{50%{{opacity:0}}}}
  .card{{background:#2a0000;border:2px solid #ff0000;border-radius:12px;
         padding:24px 48px;text-align:center;box-shadow:0 0 40px #ff000055}}
  .row{{display:flex;justify-content:space-between;gap:48px;margin:12px 0;font-size:1.1rem}}
  .label{{color:#ff8888}} .val{{color:#ffffff;font-weight:bold}}
  .btn{{margin-top:28px;padding:16px 64px;background:#ff2222;color:#fff;border:none;
        border-radius:8px;font-size:1.4rem;font-weight:bold;cursor:pointer;
        box-shadow:0 0 20px #ff000099;transition:transform .1s}}
  .btn:hover{{transform:scale(1.05)}}
  .sub{{margin-top:12px;color:#ff6666;font-size:.9rem}}
</style>
</head>
<body>
<div class="card">
  <h1>&#128293; YANGIN ALARMI &#128293;</h1>
  <div class="row">
    <div><span class="label">Yangin Guven:</span> <span class="val">{fire_pct}%</span></div>
    <div><span class="label">Duman:</span> <span class="val">{smoke_raw}/4095</span></div>
    <div><span class="label">Sicaklik:</span> <span class="val">{temp_c:.1f} °C</span></div>
    <div><span class="label">Fusion Skoru:</span> <span class="val">{score:.2f}</span></div>
  </div>
  <p class="sub">Zaman: {ts} &nbsp;|&nbsp; Robot durdu ve geri cekildi</p>
  <form method="POST" action="/ok">
    <button class="btn" type="submit">&#10003; TAMAM — Alarmi Onayla ve Devam Et</button>
  </form>
</div>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            def _serve_mjpeg(self, get_frame):
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.end_headers()
                while True:
                    if _alarm_active.is_set():
                        return
                    frame = get_frame()
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    ok, buf = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                    )
                    if not ok:
                        continue
                    data = buf.tobytes()
                    try:
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                            + data
                            + b"\r\n"
                        )
                    except Exception:
                        return

            def log_message(self, *_):
                pass

        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", self._port), _Handler) as srv:
            logger.info(
                "Web sunucusu başlatıldı → http://<pi-ip>:%d/  (stream + alarm bildirimi)",
                self._port,
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
        self._thread: Optional[threading.Thread] = None
        self._actual_w: int = config.CAMERA_TARGET_WIDTH
        self._actual_h: int = config.CAMERA_TARGET_HEIGHT

    def init(self) -> bool:
        port = int(os.environ.get("SEEFIRE_STREAM_PORT", "8080"))

        if not CV_AVAILABLE:
            logger.info("[MOCK] M4 Vision initialized.")
            if os.environ.get("SEEFIRE_STREAM") == "1":
                _MjpegServer(self.capture_frame, port).start()
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
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()

            logger.info(
                "M4 Vision started (driver=%dx%d, target=%dx%d, YOLO=%s)",
                self._actual_w, self._actual_h,
                config.CAMERA_TARGET_WIDTH, config.CAMERA_TARGET_HEIGHT,
                YOLO_AVAILABLE,
            )

        except Exception as exc:
            logger.error("Camera open failed: %s", exc)
            self._capture = None

        # Web sunucusu: gerçek Pi'de her zaman, mock modda yalnızca SEEFIRE_STREAM=1 ile
        if CV_AVAILABLE or os.environ.get("SEEFIRE_STREAM") == "1":
            _MjpegServer(self.capture_frame, port).start()
        else:
            logger.info("[MOCK] Web sunucusu başlatılmıyor (mock mod, SEEFIRE_STREAM=0).")
        return True

    def _update_loop(self) -> None:
        """Background thread: capture → resize → YOLO → store result."""
        tw = config.CAMERA_TARGET_WIDTH
        th = config.CAMERA_TARGET_HEIGHT
        while self._running:
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

            fire_conf, smoke_conf, fire_side = _run_yolo(raw)

            with self._lock:
                self._current_frame = raw
                self._yolo_result = {"fire_conf": fire_conf, "smoke_conf": smoke_conf, "fire_side": fire_side}

            time.sleep(0.2)  # ~5 FPS — avoids overheating Pi

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
        """Ağırlıklı piksel-yoğunluk engel buluşsal yöntemi.

        Kareyi iki dikey ROI'ya böler:
          - Alt 1/3 (çok yakın engel): ağırlık 3×
          - Orta 1/3 (yakın engel):    ağırlık 2×
          - Üst 1/3 (uzak alan):       ağırlık 1×

        Her bölgede Canny kenar pikselleri sol/sağ yarıya ayrılarak sayılır.
        Ağırlıklı toplamı az olan taraf → daha az engel → o tarafa dön.

        Karar için en az %20 asimetri şartı aranır (gürültü bağışıklığı).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 40, 120)

        h, w = edges.shape
        mid = w // 2
        h3  = h // 3

        # Üç yatay kuşak (aşağıdan yukarı): yakın → uzak
        bands = [
            (edges[2 * h3:,       :], 3),  # alt 1/3 — çok yakın
            (edges[h3:2 * h3,     :], 2),  # orta 1/3
            (edges[:h3,           :], 1),  # üst 1/3
        ]

        left_score  = 0.0
        right_score = 0.0
        for band, weight in bands:
            left_score  += band[:, :mid].sum() / 255.0 * weight
            right_score += band[:, mid:].sum() / 255.0 * weight

        total = left_score + right_score
        if total < 30:  # yetersiz kenar → ultrasonik'e bırak
            return None

        # %20 asimetri şartı yoksa None döndür (eşit engel → ultrasonik daha güvenilir)
        imbalance = abs(left_score - right_score) / total
        if imbalance < 0.20:
            return None

        logger.debug(
            "[VISION] Ağırlıklı piksel — sol: %.1f  sağ: %.1f  asimetri: %.2f",
            left_score, right_score, imbalance,
        )
        return "RIGHT" if left_score > right_score else "LEFT"

    def determine_turn_direction_stable(
        self, n_samples: int = 5, interval_s: float = 0.8
    ) -> Optional[str]:
        """n_samples kare üzerinde oy çokluğuyla kararlı yön kararı.

        Ucuz kameralarda tek kare yanıltıcı olabilir. Kamera zaten duraksama
        sırasında oturdu; burada sadece kararlılık için birkaç kare toplanır.
        """
        if not CV_AVAILABLE:
            return None
        votes: list[str] = []
        for _ in range(n_samples):
            d = self.determine_turn_direction()
            if d is not None:
                votes.append(d)
            time.sleep(interval_s)
        if not votes:
            return None
        left_v  = votes.count("LEFT")
        right_v = votes.count("RIGHT")
        if left_v == right_v:
            return None
        result = "LEFT" if left_v > right_v else "RIGHT"
        logger.info(
            "[VISION] Kararlı yön kararı: %s  (LEFT×%d RIGHT×%d)",
            result, left_v, right_v,
        )
        return result

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

        # imbalance > 0 → more edges on left → robot drifting left (left wall closer)
        imbalance = (left_cnt - right_cnt) / total
        if abs(imbalance) < 0.20:  # within 20% dead band → no correction needed
            return None
 
        direction = "DRIFT_LEFT" if imbalance > 0 else "DRIFT_RIGHT"
        logger.debug("[VISION] Heading — left: %d  right: %d  imbalance: %.2f → %s",
                     left_cnt, right_cnt, imbalance, direction)
        return direction

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
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
determine_turn_direction_stable = _instance.determine_turn_direction_stable
get_heading_correction = _instance.get_heading_correction
close = _instance.close

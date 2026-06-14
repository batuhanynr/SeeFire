#!/usr/bin/env python3
"""
SeeFire Web Dashboard — read-only monitoring panel.

Runs as a separate process alongside main.py. Does NOT touch GPIO or
modify any existing module. Reads the M7 SQLite database (WAL mode,
concurrent reads safe) and proxies/embeds the MJPEG camera stream from M4.

Usage on Pi:
    cd ~/SeeFire
    python3 -m web_dashboard                    # default port 5000
    python3 -m web_dashboard --port 8000        # custom port

Then open  http://<pi-ip>:5000  in a browser on your laptop.

No extra pip dependencies — uses Python stdlib only.
"""
from __future__ import annotations

import argparse
import http.server
import json
import math
import mimetypes
import os
import socketserver
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Resolve project root so we can import config without modifying sys.path
# permanently. This file lives at <project>/web_dashboard/server.py.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
import config  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = config.SQLITE_DB_PATH
SNAPSHOT_DIR = config.SNAPSHOT_DIR
STREAM_PORT = int(os.environ.get("SEEFIRE_STREAM_PORT", "8080"))
MANUAL_COMMANDS = {"STOP", "FORWARD", "BACKWARD", "LEFT", "RIGHT", "FORWARD_LEFT", "FORWARD_RIGHT"}
MANUAL_WATCHDOG_SEC = 0.45
MANUAL_LOOP_DT = 0.05
MANUAL_ARC_INNER_SCALE = 0.42
MANUAL_REVERSE_SCALE = 0.82
MANUAL_TANK_TURN_SCALE = 1.18
MANUAL_MIN_TANK_PWM = 55.0
_MANUAL_CONTROLLER: ManualMockState | ManualLiveState | None = None


class ManualMockState:
    """In-memory mock robot state for browser control UI tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.command = "STOP"
        self.left_pwm = 0.0
        self.right_pwm = 0.0
        self.distance_cm = 0.0
        self.battery_v = 7.9
        self.events: list[dict] = []
        self._last_update = time.time()
        self._event_id = 1
        self._log_event("MOCK_READY", 0.05, {"mode": "manual"})

    def apply_command(self, command: str) -> dict:
        command = command.upper()
        if command not in MANUAL_COMMANDS:
            command = "STOP"
        with self._lock:
            self._advance_locked()
            changed = command != self.command
            self.command = command
            self.left_pwm, self.right_pwm = self._pwm_for(command)
            if changed:
                self._log_event_locked(f"MANUAL_{command}", self._fusion_score_locked(), {"command": command})
            return self.status_locked()

    def status(self) -> dict:
        with self._lock:
            self._advance_locked()
            return self.status_locked()

    def event_rows(self, limit: int = 50) -> list[dict]:
        with self._lock:
            self._advance_locked()
            return list(reversed(self.events[-limit:]))

    def capture_snapshot(self) -> dict:
        with self._lock:
            self._log_event_locked("MANUAL_SNAPSHOT_MOCK", self._fusion_score_locked(), {"source": "web"})
            return {"ok": True, "mock": True, "message": "mock snapshot event recorded"}

    def status_locked(self) -> dict:
        now = time.time()
        phase = now - self.started_at
        front = 135.0 + 52.0 * math.sin(phase * 0.8)
        left = 64.0 + 18.0 * math.sin(phase * 1.3 + 0.6)
        right = 70.0 + 21.0 * math.cos(phase * 1.1)
        smoke = int(155 + 35 * math.sin(phase * 0.45))
        temp = 28.0 + 4.2 * math.sin(phase * 0.35)
        fire_conf = max(0.0, 0.08 + 0.05 * math.sin(phase * 0.7))
        fusion = self._fusion_score_locked(smoke=smoke, temp=temp, fire_conf=fire_conf)
        return {
            "connected": True,
            "manual_mock": True,
            "fsm_state": "NAVIGATE" if self.command != "STOP" else "STOP",
            "fusion_score": fusion,
            "sensors": {
                "smoke": smoke,
                "temperature": round(temp, 1),
                "distance": round(self.distance_cm, 1),
                "front_cm": round(front, 1),
                "left_cm": round(left, 1),
                "right_cm": round(right, 1),
                "battery_v": round(self.battery_v, 2),
                "fire_confidence": round(fire_conf, 3),
                "fire_side": "LEFT" if math.sin(phase) < 0 else "RIGHT",
                "left_pwm": round(self.left_pwm, 1),
                "right_pwm": round(self.right_pwm, 1),
                "command": self.command,
            },
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_count": len(self.events),
            "stream_port": STREAM_PORT,
            "robot_running": True,
        }

    def _advance_locked(self) -> None:
        now = time.time()
        dt = max(0.0, min(0.25, now - self._last_update))
        self._last_update = now
        avg_pwm = (abs(self.left_pwm) + abs(self.right_pwm)) / 2.0
        direction = -1.0 if self.command == "BACKWARD" else 1.0
        if self.command != "STOP":
            self.distance_cm += direction * (avg_pwm / 100.0) * 28.0 * dt
            self.battery_v = max(6.6, self.battery_v - 0.0008 * dt * (avg_pwm / 100.0))

    def _pwm_for(self, command: str) -> tuple[float, float]:
        return {
            "STOP": (0.0, 0.0),
            "FORWARD": (70.0, 70.0),
            "BACKWARD": (-52.0, -52.0),
            "LEFT": (-48.0, 48.0),
            "RIGHT": (48.0, -48.0),
            "FORWARD_LEFT": (32.0, 70.0),
            "FORWARD_RIGHT": (70.0, 32.0),
        }[command]

    def _fusion_score_locked(self, smoke: int | None = None, temp: float | None = None, fire_conf: float | None = None) -> float:
        smoke_val = float(smoke if smoke is not None else 155)
        temp_val = float(temp if temp is not None else 28.0)
        fire_val = float(fire_conf if fire_conf is not None else 0.08)
        return round(
            (config.W_VISION * fire_val)
            + (config.W_SMOKE * min(1.0, smoke_val / 4095.0))
            + (config.W_IR * min(1.0, temp_val / config.IR_TEMP_THRESHOLD)),
            2,
        )

    def _log_event(self, event_type: str, fusion_score: float, sensor_data: dict) -> None:
        with self._lock:
            self._log_event_locked(event_type, fusion_score, sensor_data)

    def _log_event_locked(self, event_type: str, fusion_score: float, sensor_data: dict) -> None:
        self.events.append({
            "id": self._event_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "fusion_score": fusion_score,
            "sensor_data": json.dumps(sensor_data),
            "snapshot_path": "",
        })
        self._event_id += 1
        self.events = self.events[-200:]


def _level_to_pwm(level: int) -> float:
    return float(max(1, min(25, level)) * 4)


def _clamp_pwm(value: float) -> float:
    return max(0.0, min(100.0, value))


class ManualLiveState:
    """GPIO-backed manual drive controller for the web dashboard."""

    def __init__(self, speed_level: int, turn_level: int | None = None) -> None:
        from seefire_dashboard import DriveHardware, SensorHub
        import RPi.GPIO as GPIO

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.gpio = GPIO
        self.hw = DriveHardware()
        self.hub = SensorHub(GPIO)
        self.vision = None
        self.command = "STOP"
        self.left_pwm = 0.0
        self.right_pwm = 0.0
        self.target_left = 0.0
        self.target_right = 0.0
        self.last_command_at = time.monotonic()
        self.started_at = time.time()
        self.distance_cm = 0.0
        self.battery_v = 0.0
        self.events: list[dict] = []
        self._event_id = 1
        self._last_update = time.time()
        self.drive_pwm = _level_to_pwm(speed_level)
        self.reverse_pwm = _clamp_pwm(self.drive_pwm * MANUAL_REVERSE_SCALE)
        self.tank_pwm = (
            _level_to_pwm(turn_level)
            if turn_level is not None
            else _clamp_pwm(max(MANUAL_MIN_TANK_PWM, self.drive_pwm * MANUAL_TANK_TURN_SCALE))
        )
        self.arc_inner_pwm = _clamp_pwm(self.drive_pwm * MANUAL_ARC_INNER_SCALE)
        self.accel_per_tick = max(7.0, max(self.drive_pwm, self.tank_pwm) * 0.16)
        self.decel_per_tick = max(14.0, max(self.drive_pwm, self.tank_pwm) * 0.32)

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.hw.init(GPIO)
        sensor_statuses = self.hub.probe()
        self.hub.start()
        self._init_vision_stream()
        self._log_event_locked("MANUAL_LIVE_READY", 0.0, {
            "drive_pwm": self.drive_pwm,
            "reverse_pwm": self.reverse_pwm,
            "tank_pwm": self.tank_pwm,
            "arc_inner_pwm": self.arc_inner_pwm,
            "encoder_ok": getattr(self.hw, "encoder_ok", None),
            "encoder_error": getattr(self.hw, "encoder_error", ""),
            "sensors": {item.key: item.ok for item in sensor_statuses},
        })
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def apply_command(self, command: str) -> dict:
        command = command.upper()
        if command not in MANUAL_COMMANDS:
            command = "STOP"
        with self._lock:
            changed = command != self.command
            self.command = command
            self.last_command_at = time.monotonic()
            self.target_left, self.target_right = self._pwm_for(command)
            if changed:
                self._log_event_locked(f"MANUAL_{command}", 0.0, {"command": command})
            return self.status_locked()

    def status(self) -> dict:
        with self._lock:
            self._advance_locked()
            return self.status_locked()

    def event_rows(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(reversed(self.events[-limit:]))

    def capture_snapshot(self) -> dict:
        ok, message = self._capture_vision_snapshot()
        if not ok:
            before = getattr(self.hub, "photo_count", 0)
            self.hub.capture_photo()
            after = getattr(self.hub, "photo_count", before)
            ok = after > before
            message = self.hub.photo_status
        with self._lock:
            self._log_event_locked(
                "MANUAL_SNAPSHOT" if ok else "MANUAL_SNAPSHOT_FAILED",
                0.0,
                {"photo_status": message},
            )
            return {
                "ok": ok,
                "message": message,
            }

    def close(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        try:
            if self.vision is not None:
                self.vision.close()
            self.hub.stop()
            self.hw.stop()
            self.hw.cleanup()
        finally:
            try:
                self.gpio.cleanup()
            except Exception:
                pass

    def status_locked(self) -> dict:
        age = time.monotonic() - self.last_command_at
        sensor_values = self._sensor_values()
        fire_conf = self.vision.get_fire_confidence() if self.vision is not None else 0.0
        fire_side = self.vision.get_fire_side() if self.vision is not None else None
        return {
            "connected": True,
            "manual_live": True,
            "fsm_state": "NAVIGATE" if self.command != "STOP" else "STOP",
            "fusion_score": round(float(fire_conf or 0.0), 2),
            "sensors": {
                "smoke": sensor_values["smoke"],
                "temperature": sensor_values["temperature"],
                "distance": round(self.distance_cm, 1),
                "front_cm": sensor_values["front_cm"],
                "left_cm": sensor_values["left_cm"],
                "right_cm": sensor_values["right_cm"],
                "battery_v": sensor_values["battery_v"],
                "fire_confidence": fire_conf,
                "fire_side": fire_side,
                "left_pwm": round(self.left_pwm, 1),
                "right_pwm": round(self.right_pwm, 1),
                "left_ticks": self.hw.left_ticks,
                "right_ticks": self.hw.right_ticks,
                "command": self.command,
                "command_age_ms": int(age * 1000),
                "encoder_ok": getattr(self.hw, "encoder_ok", None),
                "drive_pwm": round(self.drive_pwm, 1),
                "tank_pwm": round(self.tank_pwm, 1),
            },
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_count": len(self.events),
            "stream_port": STREAM_PORT,
            "robot_running": True,
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if time.monotonic() - self.last_command_at > MANUAL_WATCHDOG_SEC:
                    if self.command != "STOP":
                        self._log_event_locked("MANUAL_WATCHDOG_STOP", 0.0, {"age_sec": MANUAL_WATCHDOG_SEC})
                    self.command = "STOP"
                    self.target_left = 0.0
                    self.target_right = 0.0
                self._advance_locked()
                self.left_pwm = self._approach(self.left_pwm, self.target_left)
                self.right_pwm = self._approach(self.right_pwm, self.target_right)
                left, right = self.left_pwm, self.right_pwm
            self.hw.set_drive(left, right)
            self._stop_event.wait(MANUAL_LOOP_DT)

    def _advance_locked(self) -> None:
        now = time.time()
        dt = max(0.0, min(0.25, now - self._last_update))
        self._last_update = now
        avg_pwm = (abs(self.left_pwm) + abs(self.right_pwm)) / 2.0
        if self.command != "STOP":
            direction = -1.0 if self.command == "BACKWARD" else 1.0
            self.distance_cm += direction * (avg_pwm / 100.0) * 28.0 * dt

    def _approach(self, current: float, target: float) -> float:
        step = self.decel_per_tick if target == 0.0 else self.accel_per_tick
        if abs(target - current) <= step:
            return target
        return current + step if target > current else current - step

    def _pwm_for(self, command: str) -> tuple[float, float]:
        fwd = self.drive_pwm
        rev = self.reverse_pwm
        tank = self.tank_pwm
        inner = self.arc_inner_pwm
        return {
            "STOP": (0.0, 0.0),
            "FORWARD": (fwd, fwd),
            "BACKWARD": (-rev, -rev),
            # Only A/D while stopped: true tank/pivot turn.
            "LEFT": (-tank, tank),
            "RIGHT": (tank, -tank),
            # W+A/D while moving: circular differential steering, not pivot.
            "FORWARD_LEFT": (inner, fwd),
            "FORWARD_RIGHT": (fwd, inner),
        }[command]

    def _init_vision_stream(self) -> None:
        os.environ.setdefault("SEEFIRE_STREAM", "1")
        os.environ.setdefault("SEEFIRE_STREAM_PORT", str(STREAM_PORT))
        os.environ.setdefault("SEEFIRE_CAPTURE_FPS", "20")
        os.environ.setdefault("SEEFIRE_STREAM_FPS", "20")
        os.environ.setdefault("SEEFIRE_YOLO_FPS", "3")
        try:
            from m4_vision.vision import VisionM4

            self.vision = VisionM4()
            self.vision.init()
        except Exception as exc:
            self.vision = None
            self._log_event_locked("MANUAL_CAMERA_FAILED", 0.0, {"error": str(exc)})

    def _capture_vision_snapshot(self) -> tuple[bool, str]:
        if self.vision is None:
            return False, "kamera stream pasif"
        frame = self.vision.capture_frame()
        if frame is None:
            return False, "stream karesi yok"
        try:
            import cv2

            Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
            filename = f"manual_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
            path = Path(SNAPSHOT_DIR) / filename
            if cv2.imwrite(str(path), frame):
                return True, f"kayit: {filename}"
            return False, "snapshot yazma hatasi"
        except Exception as exc:
            return False, f"snapshot hata: {exc}"

    def _sensor_values(self) -> dict:
        values = self.hub.snapshot()
        return {
            "front_cm": self._parse_number(values.get("front_us")),
            "left_cm": self._parse_number(values.get("left_us")),
            "right_cm": self._parse_number(values.get("right_us")),
            "smoke": self._parse_number(values.get("mq2")),
            "temperature": self._parse_ir_temp(values.get("ir")),
            "battery_v": self._parse_number(values.get("battery")),
        }

    @staticmethod
    def _parse_number(value: str | None) -> float | None:
        if not value or value == "ERR":
            return None
        try:
            return float(str(value).split()[0])
        except (ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _parse_ir_temp(value: str | None) -> float | None:
        if not value or value == "ERR":
            return None
        try:
            # SensorHub formats as: "obj 28.1C / ortam 24.0C"
            return float(str(value).split()[1].replace("C", ""))
        except (ValueError, TypeError, IndexError):
            return None

    def _log_event_locked(self, event_type: str, fusion_score: float, sensor_data: dict) -> None:
        self.events.append({
            "id": self._event_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "fusion_score": fusion_score,
            "sensor_data": json.dumps(sensor_data),
            "snapshot_path": "",
        })
        self._event_id += 1
        self.events = self.events[-200:]


# ---------------------------------------------------------------------------
# Database helpers (read-only, WAL-safe)
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def read_events(limit: int = 50) -> list[dict]:
    """Return the *limit* most recent events, newest first."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = _get_connection()
        rows = conn.execute(
            "SELECT id, timestamp, event_type, fusion_score, sensor_data, "
            "snapshot_path FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        cols = ["id", "timestamp", "event_type", "fusion_score",
                "sensor_data", "snapshot_path"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception as exc:
        return [{"error": str(exc)}]


def get_event_count() -> int:
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = _get_connection()
        n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def _snapshot_files() -> list[Path]:
    root = Path(SNAPSHOT_DIR)
    if not root.exists():
        return []
    allowed = {".jpg", ".jpeg", ".png"}
    return sorted(
        (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in allowed),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def read_snapshots(limit: int = 200) -> list[dict]:
    events = {event.get("id"): event for event in read_events(limit=2000)}
    snapshots: list[dict] = []
    for path in _snapshot_files()[:limit]:
        event_id = None
        prefix = path.stem.split("_", 1)[0]
        if prefix.isdigit():
            event_id = int(prefix)
        event = events.get(event_id, {})
        try:
            sensor_data = json.loads(event.get("sensor_data") or "{}")
        except (json.JSONDecodeError, TypeError):
            sensor_data = {}
        snapshots.append({
            "filename": path.name,
            "url": f"/api/snapshot/{path.name}",
            "size_bytes": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "event_id": event_id,
            "timestamp": event.get("timestamp"),
            "event_type": event.get("event_type") or path.stem,
            "fusion_score": event.get("fusion_score"),
            "sensor_data": sensor_data,
        })
    return snapshots


def clear_snapshots() -> dict:
    deleted = 0
    errors: list[str] = []
    for path in _snapshot_files():
        try:
            path.unlink()
            deleted += 1
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    return {"deleted": deleted, "errors": errors}


# ---------------------------------------------------------------------------
# Status aggregation
# ---------------------------------------------------------------------------

_STATE_MAP = {
    "ALARM": "ALARM",
    "VERIFY": "VERIFY",
    "STOP": "STOP",
    "SNAPSHOT": "NAVIGATE",
}


def _infer_state(event_type: str) -> str:
    upper = event_type.upper()
    for keyword, state in _STATE_MAP.items():
        if keyword in upper:
            return state
    return "INIT"


def get_system_status() -> dict:
    if _MANUAL_CONTROLLER is not None:
        return _MANUAL_CONTROLLER.status()

    events = read_events(limit=1)

    status: dict = {
        "connected": False,
        "fsm_state": "OFFLINE",
        "fusion_score": 0.0,
        "sensors": {
            "smoke": 0,
            "temperature": 0.0,
            "distance": 0.0,
            "fire_confidence": 0.0,
            "fire_side": None,
        },
        "last_update": None,
        "event_count": get_event_count(),
        "stream_port": STREAM_PORT,
        "robot_running": _is_robot_running(),
    }

    if not events or "error" in events[0]:
        return status

    latest = events[0]
    status["connected"] = True
    status["last_update"] = latest.get("timestamp")
    status["fusion_score"] = latest.get("fusion_score", 0.0) or 0.0
    status["fsm_state"] = _infer_state(latest.get("event_type", ""))

    sensor_raw = latest.get("sensor_data") or "{}"
    try:
        sd = json.loads(sensor_raw)
        status["sensors"]["smoke"] = sd.get("smoke", 0)
        status["sensors"]["temperature"] = sd.get("temp", 0.0)
        status["sensors"]["distance"] = sd.get("distance", 0.0)
        status["sensors"]["fire_confidence"] = sd.get("fire_conf", 0.0)
        status["sensors"]["fire_side"] = sd.get("fire_side")
    except (json.JSONDecodeError, TypeError):
        pass

    return status


def get_events_for_panel(limit: int = 50) -> list[dict]:
    if _MANUAL_CONTROLLER is not None:
        return _MANUAL_CONTROLLER.event_rows(limit=limit)
    return read_events(limit=limit)


def get_snapshots_for_panel(limit: int = 200) -> dict:
    if _MANUAL_CONTROLLER is not None:
        if isinstance(_MANUAL_CONTROLLER, ManualMockState):
            return {"snapshots": []}
        return {"snapshots": read_snapshots(limit=limit)}
    return {"snapshots": read_snapshots(limit=limit)}


def _is_robot_running() -> bool:
    """Check if a main.py process is active (best-effort)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*main\\.py"],
            capture_output=True, timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_config_info() -> dict:
    return {
        "thresholds": {
            "smoke": config.SMOKE_THRESHOLD,
            "ir_temp": config.IR_TEMP_THRESHOLD,
            "vision_conf": config.VISION_CONF_THRESHOLD,
            "fusion_alarm": config.FUSION_ALARM_THRESH,
            "fusion_clear": config.FUSION_CLEAR_THRESH,
            "obstacle_cm": config.OBSTACLE_THRESHOLD_CM,
        },
        "battery": {
            "max_v": config.BATTERY_MAX_V,
            "nominal_v": config.BATTERY_NOMINAL_V,
            "low_v": config.BATTERY_LOW_V,
            "critical_v": config.BATTERY_CRIT_V,
        },
        "fusion_weights": {
            "vision": config.W_VISION,
            "smoke": config.W_SMOKE,
            "ir": config.W_IR,
        },
        "navigation": {
            "waypoints": config.WAYPOINTS,
            "step_cm": config.STEP_DISTANCE_CM,
            "drive_speed": config.DRIVE_SPEED,
        },
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """Serves the dashboard UI and JSON API endpoints."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        # ── API routes ────────────────────────────────────────────
        if path == "/api/status":
            self._json(get_system_status())

        elif path == "/api/events":
            limit = int(query.get("limit", ["50"])[0])
            self._json(get_events_for_panel(limit=limit))

        elif path == "/api/snapshots":
            limit = int(query.get("limit", ["200"])[0])
            self._json(get_snapshots_for_panel(limit=limit))

        elif path == "/api/config":
            self._json(get_config_info())

        elif path.startswith("/api/snapshot/"):
            # Serve snapshot JPEG: /api/snapshot/<filename>
            parts = path.split("/")
            if len(parts) >= 4:
                self._serve_snapshot(parts[3])
            else:
                self.send_error(404)

        # ── Static files ──────────────────────────────────────────
        elif path == "/" or path == "/index.html":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")

        elif path.startswith("/static/"):
            rel = path.removeprefix("/static/")
            fpath = STATIC_DIR / rel
            if fpath.exists() and fpath.is_file():
                ct = mimetypes.guess_type(str(fpath))[0] or "application/octet-stream"
                self._serve_file(fpath, ct)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/snapshots/clear":
            if _MANUAL_CONTROLLER is not None:
                self._json({"deleted": 0, "errors": [], "mock": True})
            else:
                self._json(clear_snapshots())
        elif path == "/api/manual/command":
            if _MANUAL_CONTROLLER is None:
                self.send_error(403, "manual mode is not enabled")
                return
            payload = self._read_json()
            self._json(_MANUAL_CONTROLLER.apply_command(str(payload.get("command", "STOP"))))
        elif path == "/api/manual/snapshot":
            if _MANUAL_CONTROLLER is None or not hasattr(_MANUAL_CONTROLLER, "capture_snapshot"):
                self.send_error(403, "manual mode is not enabled")
                return
            self._json(_MANUAL_CONTROLLER.capture_snapshot())
        else:
            self.send_error(404)

    # -- helpers ---------------------------------------------------

    def _json(self, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: Path, content_type: str) -> None:
        try:
            data = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)
        except Exception:
            self.send_error(500)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _serve_snapshot(self, filename: str) -> None:
        # Security: only allow .jpg/.jpeg/.png, no path traversal
        if ".." in filename or "/" in filename:
            self.send_error(403)
            return
        fpath = Path(SNAPSHOT_DIR) / filename
        if fpath.exists() and fpath.suffix.lower() in (".jpg", ".jpeg", ".png"):
            self._serve_file(fpath, "image/jpeg")
        else:
            self.send_error(404)

    def log_message(self, fmt, *args) -> None:
        # Suppress per-request log noise; print errors only
        if args and "404" in str(args[0]):
            return
        super().log_message(fmt, *args)


# ---------------------------------------------------------------------------
# Threaded server (handles multiple browser tabs / concurrent requests)
# ---------------------------------------------------------------------------

class _ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global _MANUAL_CONTROLLER
    parser = argparse.ArgumentParser(description="SeeFire Web Dashboard")
    parser.add_argument("--port", type=int, default=5000,
                        help="HTTP port (default: 5000)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--mock-manual", action="store_true",
                        help="Run an in-memory mock robot with browser keyboard controls. No GPIO/DB writes.")
    parser.add_argument("--manual-live", action="store_true",
                        help="Run real GPIO-backed browser manual drive mode. Do not run with main.py.")
    parser.add_argument("--manual-speed-level", type=int, default=15,
                        help="Manual drive profile level 1-25 (default: 15 = 60%% drive PWM).")
    parser.add_argument("--manual-fwd-level", type=int, default=None,
                        help="Legacy alias for --manual-speed-level.")
    parser.add_argument("--manual-turn-level", type=int, default=None,
                        help="Optional tank-turn override 1-25. Omit for auto tank profile.")
    args = parser.parse_args()

    if args.mock_manual and args.manual_live:
        parser.error("--mock-manual and --manual-live cannot be used together")

    if args.mock_manual:
        _MANUAL_CONTROLLER = ManualMockState()
    elif args.manual_live:
        speed_level = args.manual_fwd_level if args.manual_fwd_level is not None else args.manual_speed_level
        _MANUAL_CONTROLLER = ManualLiveState(speed_level, args.manual_turn_level)

    db_exists = "✓" if os.path.exists(DB_PATH) else "✗"
    stream_hint = f"http://localhost:{STREAM_PORT}/"
    if args.manual_live:
        speed_level = args.manual_fwd_level if args.manual_fwd_level is not None else args.manual_speed_level
        drive_pwm = _level_to_pwm(speed_level)
        tank_pwm = (
            _level_to_pwm(args.manual_turn_level)
            if args.manual_turn_level is not None
            else _clamp_pwm(max(MANUAL_MIN_TANK_PWM, drive_pwm * MANUAL_TANK_TURN_SCALE))
        )
        mode = (
            f"MANUAL LIVE GPIO "
            f"(drive {drive_pwm:.0f}% PWM, tank {tank_pwm:.0f}% PWM)"
        )
    elif args.mock_manual:
        mode = "MOCK MANUAL (no GPIO)"
    else:
        mode = "READ-ONLY LIVE"

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║           🔥  SeeFire Web Dashboard              ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Panel :  http://{args.host}:{args.port}/")
    print(f"║  Mode  :  {mode}")
    print(f"║  DB    :  {DB_PATH}  [{db_exists if _MANUAL_CONTROLLER is None else '-'}]")
    print(f"║  Kamera:  {stream_hint if _MANUAL_CONTROLLER is None else 'manual mode'}")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print("  Tarayıcıdan açın →  http://<pi-ip>:%d/" % args.port)
    print("  Ctrl+C ile kapatın.\n")

    server = _ThreadedServer((args.host, args.port), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🔥 Dashboard kapatılıyor...")
        server.shutdown()
    finally:
        if _MANUAL_CONTROLLER is not None and hasattr(_MANUAL_CONTROLLER, "close"):
            _MANUAL_CONTROLLER.close()


if __name__ == "__main__":
    main()

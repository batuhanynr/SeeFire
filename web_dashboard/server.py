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
import mimetypes
import os
import socketserver
import sqlite3
import subprocess
import sys
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
            self._json(read_events(limit=limit))

        elif path == "/api/snapshots":
            limit = int(query.get("limit", ["200"])[0])
            self._json({"snapshots": read_snapshots(limit=limit)})

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
            self._json(clear_snapshots())
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
    parser = argparse.ArgumentParser(description="SeeFire Web Dashboard")
    parser.add_argument("--port", type=int, default=5000,
                        help="HTTP port (default: 5000)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    db_exists = "✓" if os.path.exists(DB_PATH) else "✗"
    stream_hint = f"http://localhost:{STREAM_PORT}/"

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║           🔥  SeeFire Web Dashboard              ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Panel :  http://{args.host}:{args.port}/")
    print(f"║  DB    :  {DB_PATH}  [{db_exists}]")
    print(f"║  Kamera:  {stream_hint}")
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


if __name__ == "__main__":
    main()

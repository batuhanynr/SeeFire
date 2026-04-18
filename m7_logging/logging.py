import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

import logging

import config

logger = logging.getLogger(__name__)

__all__ = ["m7_event_t", "log_event", "get_events", "save_map", "load_map", "save_snapshot", "init"]


@dataclass
class m7_event_t:
    timestamp: str
    event_type: str
    fusion_score: float
    sensor_data: str
    snapshot_path: str


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def init() -> None:
    global _conn
    os.makedirs(os.path.dirname(config.SQLITE_DB_PATH) or ".", exist_ok=True)
    _conn = sqlite3.connect(config.SQLITE_DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            fusion_score REAL,
            sensor_data TEXT,
            snapshot_path TEXT
        )
    """)
    _conn.commit()
    logger.info("SQLite DB ready at %s (WAL mode)", config.SQLITE_DB_PATH)


def log_event(event: m7_event_t) -> int:
    with _lock:
        assert _conn is not None, "m7_logging.init() must be called before log_event()"
        cursor = _conn.execute(
            "INSERT INTO events (timestamp, event_type, fusion_score, sensor_data, snapshot_path) VALUES (?, ?, ?, ?, ?)",
            (event.timestamp, event.event_type, event.fusion_score, event.sensor_data, event.snapshot_path),
        )
        _conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def get_events(event_type: str | None = None, limit: int = 100) -> list[dict]:
    with _lock:
        assert _conn is not None, "m7_logging.init() must be called before get_events()"
        if event_type:
            rows = _conn.execute(
                "SELECT id, timestamp, event_type, fusion_score, sensor_data, snapshot_path FROM events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = _conn.execute(
                "SELECT id, timestamp, event_type, fusion_score, sensor_data, snapshot_path FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    columns = ["id", "timestamp", "event_type", "fusion_score", "sensor_data", "snapshot_path"]
    return [dict(zip(columns, row)) for row in rows]


def save_map(map_json: str) -> None:
    os.makedirs(os.path.dirname(config.MAP_JSON_PATH) or ".", exist_ok=True)
    tmp_path = config.MAP_JSON_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(map_json)
    os.replace(tmp_path, config.MAP_JSON_PATH)


def load_map() -> str | None:
    if not os.path.exists(config.MAP_JSON_PATH):
        return None
    with open(config.MAP_JSON_PATH, "r") as f:
        return f.read()


def save_snapshot(jpeg_bytes: bytes, event_id: int) -> str:
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{event_id}_{ts}.jpg"
    filepath = os.path.join(config.SNAPSHOT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(jpeg_bytes)
    return filepath

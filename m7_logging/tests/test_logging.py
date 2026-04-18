import json
import os
import shutil
import sqlite3
import tempfile
import threading

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
import m7_logging
import m7_logging.logging as _m7


TMPDIR = tempfile.mkdtemp()
DB_PATH = os.path.join(TMPDIR, "test_seefire.db")
MAP_PATH = os.path.join(TMPDIR, "test_map.json")
SNAP_DIR = os.path.join(TMPDIR, "test_snapshots")


def setup_module():
    config.SQLITE_DB_PATH = DB_PATH
    config.MAP_JSON_PATH = MAP_PATH
    config.SNAPSHOT_DIR = SNAP_DIR


def teardown_module():
    shutil.rmtree(TMPDIR, ignore_errors=True)


def _reset_db():
    if _m7._conn is not None:
        _m7._conn.close()
        _m7._conn = None
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    _m7.init()


def test_log_event_returns_id():
    _reset_db()
    event = m7_logging.m7_event_t(
        timestamp="2026-04-18T10:00:00Z",
        event_type="ALARM",
        fusion_score=0.85,
        sensor_data='{"smoke": 500}',
        snapshot_path="/data/snapshots/1.jpg",
    )
    row_id = m7_logging.log_event(event)
    assert row_id > 0
    assert isinstance(row_id, int)


def test_log_and_get_events():
    _reset_db()
    for i in range(3):
        event = m7_logging.m7_event_t(
            timestamp=f"2026-04-18T10:0{i}:00Z",
            event_type="ALARM" if i < 2 else "FALSE_ALARM",
            fusion_score=0.5 + i * 0.1,
            sensor_data='{"test": true}',
            snapshot_path="",
        )
        m7_logging.log_event(event)
    all_events = m7_logging.get_events()
    assert len(all_events) == 3
    alarm_events = m7_logging.get_events(event_type="ALARM")
    assert len(alarm_events) == 2
    assert all(e["event_type"] == "ALARM" for e in alarm_events)


def test_get_events_limit():
    _reset_db()
    for i in range(20):
        event = m7_logging.m7_event_t(
            timestamp=f"2026-04-18T10:{i:02d}:00Z",
            event_type="PATROL",
            fusion_score=0.0,
            sensor_data="",
            snapshot_path="",
        )
        m7_logging.log_event(event)
    events = m7_logging.get_events(limit=5)
    assert len(events) == 5


def test_wal_mode():
    _reset_db()
    event = m7_logging.m7_event_t("2026-04-18T10:00:00Z", "INIT", 0.0, "", "")
    m7_logging.log_event(event)
    conn = sqlite3.connect(DB_PATH)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_init_creates_db_file():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if _m7._conn is not None:
        _m7._conn.close()
        _m7._conn = None
    _m7.init()
    assert os.path.exists(DB_PATH)
    assert _m7._conn is not None


def test_log_without_init_raises():
    if _m7._conn is not None:
        _m7._conn.close()
        _m7._conn = None
    event = m7_logging.m7_event_t("2026-04-18T10:00:00Z", "INIT", 0.0, "", "")
    try:
        m7_logging.log_event(event)
        assert False, "Should have raised AssertionError"
    except AssertionError:
        pass
    finally:
        _reset_db()


def test_map_save_load_roundtrip():
    if os.path.exists(MAP_PATH):
        os.remove(MAP_PATH)
    map_data = {"grid": [[0, 1], [1, 0]], "resolution": 0.1}
    map_json = json.dumps(map_data)
    m7_logging.save_map(map_json)
    loaded = m7_logging.load_map()
    assert loaded is not None
    assert json.loads(loaded) == map_data


def test_load_map_returns_none_when_missing():
    if os.path.exists(MAP_PATH):
        os.remove(MAP_PATH)
    assert m7_logging.load_map() is None


def test_map_atomic_write():
    if os.path.exists(MAP_PATH):
        os.remove(MAP_PATH)
    m7_logging.save_map('{"a": 1}')
    m7_logging.save_map('{"a": 2}')
    loaded = m7_logging.load_map()
    assert json.loads(loaded)["a"] == 2


def test_snapshot_save_creates_file():
    if os.path.exists(SNAP_DIR):
        shutil.rmtree(SNAP_DIR)
    jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    filepath = m7_logging.save_snapshot(jpeg_data, 42)
    assert os.path.exists(filepath)
    with open(filepath, "rb") as f:
        assert f.read() == jpeg_data


def test_snapshot_dir_auto_created():
    if os.path.exists(SNAP_DIR):
        shutil.rmtree(SNAP_DIR)
    m7_logging.save_snapshot(b"\xff\xd8\xff\xe0", 1)
    assert os.path.isdir(SNAP_DIR)


def test_concurrent_log_events():
    _reset_db()
    errors = []
    barrier = threading.Barrier(5)

    def writer(thread_id):
        try:
            barrier.wait(timeout=2)
            for _ in range(10):
                event = m7_logging.m7_event_t(
                    timestamp="2026-04-18T10:00:00Z",
                    event_type=f"T{thread_id}",
                    fusion_score=0.5,
                    sensor_data="",
                    snapshot_path="",
                )
                m7_logging.log_event(event)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert len(errors) == 0, f"Thread errors: {errors}"
    all_events = m7_logging.get_events(limit=1000)
    assert len(all_events) == 50

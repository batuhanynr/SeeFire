"""
Quick demo — run on your Mac to see M7 and M3 in action.
No Raspberry Pi or hardware needed; M3 runs in fallback/mock mode.

NOTE: The M7 section follows the current persistence API. The M3 section is a
provisional local demo and may need updates from the M3 owner as sensor APIs
change.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import m7_logging
import m3_sensors

DATA_DIR = "./demo_data"
config.SQLITE_DB_PATH = os.path.join(DATA_DIR, "seefire.db")
config.MAP_JSON_PATH = os.path.join(DATA_DIR, "map.json")
config.SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")


def demo_m7():
    print("=" * 50)
    print("M7 — Data Logging Demo")
    print("=" * 50)

    m7_logging.init()

    event = m7_logging.m7_event_t(
        timestamp="2026-04-18T10:00:00Z",
        event_type="INIT",
        fusion_score=0.0,
        sensor_data="{}",
        snapshot_path="",
    )
    row_id = m7_logging.log_event(event)
    print(f"  [+] Logged INIT event → row id: {row_id}")

    for i, etype in enumerate(["EXPLORE", "PATROL", "VERIFY", "ALARM"]):
        e = m7_logging.m7_event_t(
            timestamp=f"2026-04-18T10:0{i + 1}:00Z",
            event_type=etype,
            fusion_score=round(0.3 + i * 0.15, 2),
            sensor_data=json.dumps({"smoke": 100 + i * 100, "ir_temp": 30 + i * 10}),
            snapshot_path="",
        )
        m7_logging.log_event(e)
        print(f"  [+] Logged {etype} (score={e.fusion_score})")

    print(f"\n  All events:")
    for ev in m7_logging.get_events(limit=10):
        print(f"    #{ev['id']} {ev['event_type']:12s} score={ev['fusion_score']}")

    print(f"\n  ALARM events only:")
    for ev in m7_logging.get_events(event_type="ALARM"):
        print(f"    #{ev['id']} {ev['event_type']}")

    # Map save/load
    sample_map = json.dumps({"grid_size": [40, 40], "resolution": 0.1, "cells": []})
    m7_logging.save_map(sample_map)
    loaded = m7_logging.load_map()
    print(f"\n  [+] Map saved and loaded: {len(json.loads(loaded))} keys")

    # Snapshot
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    path = m7_logging.save_snapshot(fake_jpeg, 1)
    size = os.path.getsize(path)
    print(f"  [+] Snapshot saved: {path} ({size} bytes)")

    # Missing map
    os.remove(config.MAP_JSON_PATH)
    print(f"  [+] load_map() after delete: {m7_logging.load_map()}")


def demo_m3():
    print("\n" + "=" * 50)
    print("M3 — Sensor Integration Demo (mock mode)")
    print("=" * 50)

    m3_sensors.init_sensors()

    print(f"\n  MQ-2 ready: {m3_sensors.is_mq2_ready()}")

    smoke = m3_sensors.read_mq2()
    print(f"  MQ-2 smoke level: {smoke} (mock → 0 because no SPI)")

    ir = m3_sensors.read_mlx90614()
    print(f"  MLX90614 IR temp: {ir}°C (mock → 25.0 because no I2C)")

    temp, hum = m3_sensors.read_dht22()
    print(f"  DHT22 temp: {temp}°C, humidity: {hum}% (mock → fallback)")

    dist_l = m3_sensors.read_hcsr04(config.TRIG_LEFT, config.ECHO_LEFT)
    dist_r = m3_sensors.read_hcsr04(config.TRIG_RIGHT, config.ECHO_RIGHT)
    print(f"  HC-SR04 left: {dist_l} cm, right: {dist_r} cm (mock → -1.0)")

    yaw = m3_sensors.read_mpu6050_yaw()
    print(f"  MPU6050 yaw: {yaw}° (mock → 0.0)")

    fusion = m3_sensors.get_fusion_sensors()
    print(f"\n  get_fusion_sensors() → {fusion}")

    nav = m3_sensors.get_navigation_sensors()
    print(f"  get_navigation_sensors() → {nav}")


if __name__ == "__main__":
    demo_m7()
    demo_m3()
    print("\n" + "=" * 50)
    print("Demo complete. Check ./demo_data/ for output files.")
    print("=" * 50)

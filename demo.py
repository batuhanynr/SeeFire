#!/usr/bin/env python3
"""
SeeFire Demo Script - Sunum İçin
=================================

Kullanım: python demo.py
"""
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force mock mode
os.environ['SEEFIRE_FORCE_MOCK'] = '1'

import config
import m7_logging
import m3_sensors
import m4_vision
from m2_motor import motor
from m6_decision.decision import DecisionEngine

# Demo data directory
DATA_DIR = "./demo_data"
config.DATA_DIR = DATA_DIR
config.SQLITE_DB_PATH = os.path.join(DATA_DIR, "seefire.db")
config.MAP_JSON_PATH = os.path.join(DATA_DIR, "map.json")
config.SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_subheader(title: str):
    print(f"\n▶ {title}")
    print("-" * 40)


def demo_config():
    """M1: Konfigürasyon"""
    print_header("M1: KONFİGÜRASYON")
    print(f"Data Dir: {config.DATA_DIR}")
    print(f"Waypoints: {len(config.WAYPOINTS)} nokta")
    for i, (dist, sector) in enumerate(config.WAYPOINTS, 1):
        print(f"  WP{i}: {dist} cm (Sektör {sector})")
    print(f"\nFusion Weights: V={config.W_VISION}, S={config.W_SMOKE}, IR={config.W_IR}")
    print(f"Thresholds: Smoke={config.SMOKE_THRESHOLD}, IR={config.IR_TEMP_THRESHOLD}°C")
    print(f"Fusion Alarm: {config.FUSION_ALARM_THRESH}")
    time.sleep(0.3)


def demo_logging():
    """M7: Logging"""
    print_header("M7: LOGGING & VERİTABANI")
    m7_logging.init()
    print("✓ SQLite başlatıldı")
    
    for i, etype in enumerate(["INIT", "NAVIGATE", "WAYPOINT", "VERIFY", "ALARM"]):
        event = m7_logging.m7_event_t(
            timestamp=f"2026-06-04T10:0{i}:00Z",
            event_type=etype,
            fusion_score=round(0.2 + i * 0.15, 2),
            sensor_data="{}",
            snapshot_path="",
        )
        m7_logging.log_event(event)
        print(f"  [{etype}] score={event.fusion_score:.2f}")
    
    events = m7_logging.get_events(limit=3)
    print(f"\n  Son {len(events)} event:")
    for e in events:
        print(f"    {e['event_type']}: {e['fusion_score']:.2f}")
    time.sleep(0.3)


def demo_motor():
    """M2: Motor"""
    print_header("M2: MOTOR KONTROL")
    motor.init_hardware()
    print("✓ Motor driver başlatıldı (L298N)")
    
    voltage = motor.get_battery_voltage()
    print(f"  Battery: {voltage:.2f}V")
    print(f"  Status: {'OK' if voltage >= config.BATTERY_LOW_V else 'LOW'}")
    
    print_subheader("Encoder Okuma")
    for i in range(3):
        ticks_l, ticks_r = motor.get_encoder_ticks()
        print(f"  L={ticks_l:5d}, R={ticks_r:5d} ticks")
        time.sleep(0.1)
    time.sleep(0.3)


def demo_sensors():
    """M3: Sensörler"""
    print_header("M3: SENSÖR ENTEGRASYONU")
    m3_sensors.init_sensors()
    print("✓ Sensörler başlatıldı")
    print("  - MQ-2 (Smoke), MLX90614 (IR), HC-SR04 x3")
    
    print_subheader("Fusion Sensörleri")
    fusion = m3_sensors.get_fusion_sensors()
    print(f"  Smoke: {fusion.smoke_level:.1f}, IR: {fusion.ir_temp:.1f}°C")
    print(f"  Alert: {fusion.smoke_alert}")
    
    print_subheader("Navigasyon Sensörleri")
    nav = m3_sensors.get_navigation_sensors()
    print(f"  L: {nav.left_cm:5.1f}cm, F: {nav.front_cm:5.1f}cm, R: {nav.right_cm:5.1f}cm")
    
    if nav.front_cm < config.OBSTACLE_THRESHOLD_CM:
        print(f"  ⚠️ ENGEL tespit edildi!")
    time.sleep(0.3)


def demo_vision():
    """M4: Vision"""
    print_header("M4: VISION & KAMERA")
    m4_vision.init()
    print("✓ Kamera başlatıldı")
    
    if os.path.exists(config.YOLO_MODEL_PATH):
        print(f"✓ YOLO model: {os.path.basename(config.YOLO_MODEL_PATH)}")
    
    frame = m4_vision.capture_frame()
    if frame is not None:
        h, w = frame.shape[:2]
        print(f"  Frame: {w}x{h}")
    
    hint = m4_vision.determine_turn_direction(frame)
    print(f"  Turn hint: {hint if hint else 'none'}")
    m4_vision.close()
    time.sleep(0.3)


def demo_navigation():
    """M5: Navigasyon"""
    print_header("M5: NAVIGASYON")
    total = config.WAYPOINTS[-1][0]
    print(f"  Hedef: {total} cm")
    print(f"  Sektörler: {len(config.WAYPOINTS)}")
    print("\n  Features:")
    print("    ✓ Waypoint-based seyahat")
    print("    ✓ Obstacle bypass")
    print("    ✓ 3-yönlü tarama")
    print("    ✓ Encoder odometri")
    time.sleep(0.3)


def demo_decision():
    """M6: Decision Engine"""
    print_header("M6: DECISION ENGINE")
    print("✓ Decision Engine başlatıldı")
    print("\n  FSM States:")
    print("    INIT → NAVIGATE → VERIFY → ALARM → STOP")
    
    fusion = m3_sensors.get_fusion_sensors()
    smoke_score = 1.0 if fusion.smoke_alert else 0.0
    ir_score = min(1.0, max(0.0, (fusion.ir_temp - 40) / 40))
    fusion_score = config.W_SMOKE * smoke_score + config.W_IR * ir_score
    
    print(f"\n  Fusion Score: {fusion_score:.2f}")
    if fusion_score >= config.FUSION_ALARM_THRESH:
        print(f"  🔴 ALARM!")
    time.sleep(0.3)


def cleanup():
    print_header("CLEANUP")
    motor.stop()
    motor.cleanup()
    m3_sensors.cleanup()
    m4_vision.close()
    print("✓ Kaynaklar temizlendi")


def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          SeeFire Robot Demo - Sunum Modu               ║")
    print("║           CSE 396 - Indoor Fire Detection              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    try:
        demo_config()
        demo_logging()
        demo_motor()
        demo_sensors()
        demo_vision()
        demo_navigation()
        demo_decision()
        cleanup()
        
        print_header("DEMO TAMAMLANDI ✓")
        print("\n  - MOCK modda çalıştı")
        print(f"  - Veri: {DATA_DIR}/")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        cleanup()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

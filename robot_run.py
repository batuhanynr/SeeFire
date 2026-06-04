#!/usr/bin/env python3
"""
SeeFire Robot Run Script
========================
Pi üzerinde çalıştırın: python3 robot_run.py

Özellikler:
- Robot hareketi (ileri, geri, dönüş)
- Engelden kaçınma (45cm threshold)
- Tüm sensörler (MQ-2 duman, MLX90614 IR sıcaklık, HC-SR04 x3)
- Süre bazlı otomatik durdurma (5 dakika)
"""
import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import m3_sensors
from m2_motor import motor

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    print("\n" + "="*50)
    print("  SeeFire Robot - Başlatılıyor...")
    print("="*50)

    # Initialize hardware
    logger.info("Motorlar başlatılıyor...")
    motor.init_hardware()

    logger.info("Sensörler başlatılıyor...")
    m3_sensors.init_sensors()

    time.sleep(1)

    # Çalışma süresi (5 dakika)
    MAX_RUNTIME_MINUTES = 5
    MAX_RUNTIME_SECONDS = MAX_RUNTIME_MINUTES * 60

    print(f"\n✓ Hazır! Robot {MAX_RUNTIME_MINUTES} dakika çalışacak.")
    print("Başlamak için ENTER tuşuna basın...")
    print("(Çıkmak için Ctrl+C)\n")
    input()

    start_time = time.time()
    logger.info("Robot başlatıldı! %d dakika süre başladı...", MAX_RUNTIME_MINUTES)

    try:
        while time.time() - start_time < MAX_RUNTIME_SECONDS:
            elapsed = time.time() - start_time
            remaining = MAX_RUNTIME_SECONDS - elapsed
            # Navigasyon sensörleri (ultrasonik)
            nav = m3_sensors.get_navigation_sensors_filtered(samples=3)
            left_cm = nav.left_cm
            front_cm = nav.front_cm
            right_cm = nav.right_cm
            
            # Fusion sensörleri (ısı, duman)
            fusion = m3_sensors.get_fusion_sensors()

            # Kalan süre (dakika)
            remaining_min = (MAX_RUNTIME_SECONDS - elapsed) / 60

            # Log both
            logger.info("[SENSÖR] Sol: %.1fcm | Ön: %.1fcm | Sağ: %.1fcm | Kalan: %.1fdk",
                       left_cm, front_cm, right_cm, remaining_min)
            logger.info("[FUSION] Duman: %.0f | IR: %.1f°C | Alert: %s",
                       fusion.smoke_level, fusion.ir_temp,
                       "⚠️ EVET" if fusion.smoke_alert else "hayır")

            # Engel kontrolü (45cm threshold)
            if 0 < front_cm < 45.0:
                logger.warning("⚠️ ENGEL tespit edildi! (%.1f cm)", front_cm)
                motor.stop()
                
                # En geniş tarafa dön
                if right_cm > left_cm:
                    logger.info("→ Sağa dönülüyor...")
                    motor.turn_right_90()
                else:
                    logger.info("← Sola dönülüyor...")
                    motor.turn_left_90()
                
                time.sleep(0.5)
                logger.info("İleri devam...")
                motor.motor_drive("forward", config.DRIVE_SPEED)
            else:
                # Engel yok, ileri devam
                if not motor.is_moving:
                    logger.info("İleri gidiyor...")
                    motor.motor_drive("forward", config.DRIVE_SPEED)
            
            time.sleep(0.1)

        # Süre doldu
        logger.info("⏱️ Süre doldu! (%d dakika bitti)", MAX_RUNTIME_MINUTES)
        logger.info("Robot durduruluyor...")

    except KeyboardInterrupt:
        logger.info("Ctrl+C - Duruduruluyor...")
    finally:
        logger.info("Temizleniyor...")
        motor.stop()
        motor.cleanup()
        m3_sensors.cleanup()
        logger.info("✓ Bitti")


if __name__ == "__main__":
    main()

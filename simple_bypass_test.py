#!/usr/bin/env python3
"""
SeeFire — Basit Engel Geçme Testi
===================================
1. Karşısında engel görene kadar düz sür.
2. Engel görünce dur ve sağa 90° dön.
3. Sol sensör engeli aşana kadar (mesafe ilk değerden 45cm artana kadar) düz sür.
4. Dur ve sola 90° dön.
5. 3 saniye boyunca düz sür ve dur.
"""
from __future__ import annotations

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import m2_motor
    import m3_sensors
except ImportError as e:
    print(f"HATA: Modül yüklenemedi: {e}")
    sys.exit(1)


# Engele çarpmayı önlemek için durma eşiği (cm)
# Robotun hızı ve eylemsizliği (braking lag) nedeniyle varsayılan 30cm yetersiz kalabiliyor.
OBSTACLE_STOP_THRESHOLD_CM = 60.0


def main():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     SeeFire — Basit Engel Geçme Testi                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    # RPi.GPIO kontrolü
    if not os.getenv("SEEFIRE_FORCE_MOCK"):
        try:
            import RPi.GPIO
        except ImportError:
            print("UYARI: RPi.GPIO yok — mock modda çalışacak.")

    print("Donanım başlatılıyor...")
    m2_motor.init_hardware()
    m3_sensors.init_sensors()
    time.sleep(0.5)

    input("Robot hazır. ENTER ile testi başlatın... ")
    print()

    try:
        # 1. Engel görene kadar düz sür
        print(f"[TEST] Düz sürüş başladı. Engel aranıyor (Eşik: {OBSTACLE_STOP_THRESHOLD_CM} cm)...")
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)

        while True:
            # Filtreli ön okuma yap
            reading = m3_sensors.get_navigation_sensors_filtered(samples=3)
            front_cm = reading.front_cm
            print(f"  Ölçüm - Ön: {front_cm:.1f} cm | Sol: {reading.left_cm:.1f} cm | Sağ: {reading.right_cm:.1f} cm")

            # Eşikten yakın bir değer algılandığında dur
            if 0 < front_cm < OBSTACLE_STOP_THRESHOLD_CM:
                print(f"[TEST] Engel algılandı: {front_cm:.1f} cm (Eşik: {OBSTACLE_STOP_THRESHOLD_CM} cm). Duruluyor...")
                m2_motor.stop()
                time.sleep(1.0)
                break
            time.sleep(0.1)

        # 2. Sağa 90 derece dön
        print("[TEST] Sağa 90° dönülüyor...")
        m2_motor.turn_right_90()
        time.sleep(1.0)

        # Dönüş sonrası sol sensörün ilk mesafesini al (engele bakan taraf)
        reading = m3_sensors.get_navigation_sensors_filtered(samples=3)
        start_left = reading.left_cm
        target_left = start_left + 45.0
        print(f"[TEST] Sol sensör başlangıç mesafesi: {start_left:.1f} cm, Eşik: {target_left:.1f} cm")

        # 3. Sol sensör engeli aşana kadar ilerle
        print("[TEST] Yanal geçiş başladı...")
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)

        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            left_cm = reading.left_cm
            print(f"  Yanal Sürüş - Sol: {left_cm:.1f} cm (Hedef: > {target_left:.1f} cm)")

            # Sol sensörün boşaldığını (engeli geçtiğimizi) doğrula
            if left_cm > target_left:
                print(f"[TEST] Engel aşıldı (Sol: {left_cm:.1f} cm > Eşik: {target_left:.1f} cm). Duruluyor...")
                m2_motor.stop()
                time.sleep(1.0)
                break
            time.sleep(0.1)

        # 4. Tekrar sola 90 derece dön
        print("[TEST] Sola 90° dönülüyor...")
        m2_motor.turn_left_90()
        time.sleep(1.0)

        # 5. 3 saniye daha düz ilerle
        print("[TEST] 3 saniye düz ilerleme başladı...")
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)
        time.sleep(3.0)

        print("[TEST] Süre doldu. Durduruluyor...")
        m2_motor.stop()
        print()
        print("Test başarıyla tamamlandı!")

    except KeyboardInterrupt:
        print("\n\nCtrl+C ile kesildi.")
    except Exception as e:
        print(f"\nHATA: {e}")
    finally:
        print("\nTemizleniyor...")
        m2_motor.cleanup()
        m3_sensors.cleanup()
        print("Bitti.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SeeFire - Encoder Tanılama Aracı (Diagnostic Tool)

Bu araç motorları 5 saniye boyunca ileri sürer ve bu sırada 
encoder'lardan gelen tick verilerini gerçek zamanlı olarak ekrana yazar.
Böylece encoder'ların çalışıp çalışmadığını, gürültü olup olmadığını anlarız.
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import config
    import m2_motor
except ImportError:
    print("Hata: SeeFire modülleri yüklenemedi.")
    sys.exit(1)

def main():
    print("====================================================")
    print("         SeeFire Encoder Tanılama Aracı             ")
    print("====================================================")
    print("Bu araç tekerlek encoder'larının çalışmasını test eder.")
    print("Robotu tekerlekleri havada kalacak şekilde (örneğin bir kutu üzerine)")
    print("yerleştirin, böylece robot gitmeden tekerlekler dönebilir.")
    print("Başlamak için ENTER'a basın...")
    input()

    print("[DIAG] Donanım başlatılıyor...")
    if not m2_motor.init_hardware():
        print("Hata: Donanım başlatılamadı!")
        sys.exit(1)

    print("[DIAG] Motorlar 5 saniye boyunca ileri sürülecek...")
    time.sleep(1.0)

    # Sıfırla ve motoru sür
    m2_motor.reset_encoder_window()
    m2_motor.motor_drive("forward", config.DRIVE_SPEED)

    start_time = time.time()
    last_print = 0.0

    try:
        while time.time() - start_time < 5.0:
            elapsed = time.time() - start_time
            if elapsed - last_print >= 0.2:  # Her 200 ms'de bir yazdır
                left_ticks, right_ticks = m2_motor.get_encoder_ticks()
                dist = m2_motor.get_measured_distance_cm()
                print(f"Süre: {elapsed:.1f}s | Sol Ticks: {left_ticks} | Sağ Ticks: {right_ticks} | Hesaplanan Mesafe: {dist:.1f} cm")
                last_print = elapsed
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n[DIAG] Kullanıcı tarafından kesildi.")
    finally:
        print("[DIAG] Motorlar durduruluyor...")
        m2_motor.stop()
        m2_motor.cleanup()
        print("[DIAG] Test tamamlandı.")

if __name__ == "__main__":
    main()

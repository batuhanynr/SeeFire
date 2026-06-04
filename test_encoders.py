#!/usr/bin/env python3
"""
SeeFire — Encoder Tanılama ve İzleme Aracı
============================================
Tekerlek encoder'larının çalışmasını test eder. İki mod vardır:

1. Dinamik Test (--drive, varsayılan):
   Motorları 5 saniye ileri sürer, encoder tick'lerini gerçek zamanlı gösterir.
   Encoder'ın düzgün pulse üretip üretmediğini doğrular.
   → Tekerlekleri havaya koyarak çalıştırın.

2. Pasif İzleme (--monitor):
   Motor çalıştırmadan encoder pinlerinin dijital durumunu okur.
   Tekerleği elle çevirerek pulse gelip gelmediğini kontrol edin.
   → Güç kapalıyken bile çalışır.

Kullanım:
    python3 test_encoders.py              → dinamik test (motor sürer)
    python3 test_encoders.py --monitor    → pasif izleme (sadece okur)

Donanım:
    Sol enkoder: BCM 6 (Motor 1 / FL)  — interrupt tabanlı sayım
    Sağ enkoder: BCM 7 (Motor 2 / FR)  — interrupt tabanlı sayım

Gerekli:
    Pi üzerinde çalıştırılmalı (RPi.GPIO gerekli).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def _require_gpio():
    """RPi.GPIO'nun mevcut olduğunu kontrol et, yoksa çık."""
    try:
        import RPi.GPIO as GPIO
        return GPIO
    except ImportError:
        print("HATA: RPi.GPIO bulunamadı. Bu araç Raspberry Pi üzerinde çalıştırılmalı.")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────
# Mod 1: Dinamik Test — motor sür + encoder oku
# ──────────────────────────────────────────────────────────────
def run_drive_test():
    """Motorları 5 sn ileri sür, encoder tick'lerini canlı göster."""
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        import m2_motor
    except ImportError:
        print("HATA: SeeFire m2_motor modülü yüklenemedi.")
        sys.exit(1)

    GPIO = _require_gpio()

    print("=" * 56)
    print("     SeeFire Encoder Dinamik Test")
    print("=" * 56)
    print("Motorları 5 saniye ileri sürecek ve encoder tick'lerini")
    print("gösterecek. Tekerlekleri YERDEN KESİN.")
    print("Başlamak için ENTER...")
    input()

    print("[TEST] Donanım başlatılıyor...")
    if not m2_motor.init_hardware():
        print("HATA: Donanım başlatılamadı!")
        sys.exit(1)

    print("[TEST] Motorlar 5 saniye ileri sürülecek...")
    time.sleep(1.0)

    m2_motor.reset_encoder_window()
    m2_motor.motor_drive("forward", config.DRIVE_SPEED)

    start_time = time.time()
    last_print = 0.0

    try:
        while time.time() - start_time < 5.0:
            elapsed = time.time() - start_time
            if elapsed - last_print >= 0.2:
                left_ticks, right_ticks = m2_motor.get_encoder_ticks()
                dist = m2_motor.get_measured_distance_cm()
                print(
                    f"Süre: {elapsed:.1f}s | "
                    f"Sol Tick: {left_ticks} | Sağ Tick: {right_ticks} | "
                    f"Mesafe: {dist:.1f} cm"
                )
                last_print = elapsed
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n[TEST] Kullanıcı kesti.")
    finally:
        print("[TEST] Motorlar durduruluyor...")
        m2_motor.stop()
        m2_motor.cleanup()
        print("[TEST] Dinamik test tamamlandı.")


# ──────────────────────────────────────────────────────────────
# Mod 2: Pasif İzleme — motor yok, sadece pin oku
# ──────────────────────────────────────────────────────────────
def run_monitor():
    """Encoder pinlerinin ham dijital durumunu sürekli oku.

    Tekerleği elle çevirerek HIGH/LOW geçişlerini görün.
    Hiç değişim yoksa kablo bağlantısını kontrol edin.
    """
    GPIO = _require_gpio()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    print("=" * 56)
    print("     SeeFire Encoder Pasif İzleme")
    print("=" * 56)
    print(f"Sol Encoder: BCM {config.ENCODER_LEFT_PIN} (Pin 31)")
    print(f"Sağ Encoder: BCM {config.ENCODER_RIGHT_PIN} (Pin 26)")
    print("Tekerlekleri ELLE çevirerek pulse'ları gözlemleyin.")
    print("Çıkmak için Ctrl+C.")
    print("-" * 56)

    left_count = 0
    right_count = 0
    last_left = 0
    last_right = 0

    try:
        while True:
            lv = GPIO.input(config.ENCODER_LEFT_PIN)
            rv = GPIO.input(config.ENCODER_RIGHT_PIN)

            # Kenar sayacı (rising edge)
            if lv == 1 and last_left == 0:
                left_count += 1
            if rv == 1 and last_right == 0:
                right_count += 1
            last_left = lv
            last_right = rv

            sys.stdout.write(
                f"\rSol: {lv} (pulse: {left_count}) | "
                f"Sağ: {rv} (pulse: {right_count})    "
            )
            sys.stdout.flush()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print(f"\nToplam — Sol pulse: {left_count} | Sağ pulse: {right_count}")
    finally:
        GPIO.cleanup()
        print("GPIO temizlendi.")


def main():
    if "--monitor" in sys.argv:
        run_monitor()
    else:
        run_drive_test()


if __name__ == "__main__":
    main()

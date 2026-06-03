#!/usr/bin/env python3
"""
SeeFire — Encoder Test + Mesafe Kalibrasyon Aracı
===================================================
Robotun gittiği mesafeyi enkoder ve zaman bazlı olarak ölçer,
kullanıcı fiziksel (mezura) ölçümünü girer. Sonuçları karşılaştırarak
ENCODER_TICKS_PER_CM ve MOCK_CM_PER_SEC için en doğru değeri hesaplar.

Kullanım (Pi üzerinde):
    python3 calibrate_all.py

Akış:
    1. Encoder bağlantı testi (pulse geliyor mu?)
    2. [1]-[8] tuşlarıyla farklı mesafelerde sürüş
    3. Her sürüşte: enkoder tick, enkoder mesafe, süre, hız kaydedilir
    4. Kullanıcı mezura ile gerçek mesafeyi girer
    5. Sonuç tablosu + önerilen kalibrasyon değerleri

Donanım:
    Tekerlekleri yerden keserek veya düz zeminde çalıştırın.
    Her testten önce robotu başlangıç noktasına geri koyun.
"""
from __future__ import annotations

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    print("UYARI: RPi.GPIO bulunamadı. MOCK MODDA çalışıyor.")
    print("Gerçek kalibrasyon için Raspberry Pi üzerinde çalıştırın.")
    MOCK_MODE = True


# ── Sabitler ───────────────────────────────────────────────────
BASE_CM = 50.0            # 1x = 50 cm
LEVELS = 8                # 1-8 arası seçenek
ENCODER_CHECK_SEC = 3.0   # Encoder testi süresi


# ── Encoder doğrulama ──────────────────────────────────────────
def test_encoder_alive() -> bool:
    """Motor çalıştırmadan encoder pulse gelip gelmediğini kontrol et.

    Kullanıcı tekerlekleri elle çevirir, ekranda tick sayısı artar.
    """
    if MOCK_MODE:
        print("[MOCK] Encoder testi atlanıyor.")
        return True

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    left_ticks = 0
    right_ticks = 0
    lock = threading.Lock()

    def _on_left(_ch):
        nonlocal left_ticks
        with lock:
            left_ticks += 1

    def _on_right(_ch):
        nonlocal right_ticks
        with lock:
            right_ticks += 1

    GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(config.ENCODER_LEFT_PIN, GPIO.RISING,
                          callback=_on_left, bouncetime=2)
    GPIO.add_event_detect(config.ENCODER_RIGHT_PIN, GPIO.RISING,
                          callback=_on_right, bouncetime=2)

    print()
    print("=" * 56)
    print("  ENCODER CANLILIK TESTİ")
    print("=" * 56)
    print(f"  Sol encoder: BCM {config.ENCODER_LEFT_PIN}")
    print(f"  Sağ encoder: BCM {config.ENCODER_RIGHT_PIN}")
    print()
    print("  Tekerlekleri ELLE ÇEVİRİN.")
    print(f"  {ENCODER_CHECK_SEC:.0f} saniye boyunca pulse sayılacak...")
    print()

    start = time.time()
    last_print = 0.0
    try:
        while time.time() - start < ENCODER_CHECK_SEC:
            now = time.time()
            if now - last_print >= 0.3:
                with lock:
                    sys.stdout.write(
                        f"\r  Süre: {now - start:.1f}s | "
                        f"Sol pulse: {left_ticks} | Sağ pulse: {right_ticks}    "
                    )
                    sys.stdout.flush()
                last_print = now
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    GPIO.remove_event_detect(config.ENCODER_LEFT_PIN)
    GPIO.remove_event_detect(config.ENCODER_RIGHT_PIN)
    # Don't cleanup — main calibration will re-init

    print()
    print(f"  Sonuç: Sol = {left_ticks} pulse | Sağ = {right_ticks} pulse")

    if left_ticks == 0 and right_ticks == 0:
        print()
        print("  ❌ HİÇ PULSE GELMEDİ!")
        print("     → Enkoder kablolarını kontrol edin.")
        print("     → 3.3V, GND ve sinyal pinleri bağlı mı?")
        return False

    if left_ticks == 0:
        print("  ⚠️  Sol encoder pulse almıyor — kablo kontrol edin.")
    if right_ticks == 0:
        print("  ⚠️  Sağ encoder pulse almıyor — kablo kontrol edin.")

    if left_ticks > 0 and right_ticks > 0:
        print("  ✅ Her iki encoder da çalışıyor!")

    print()
    return True


# ── M2 modülü ile sürüş ────────────────────────────────────────
def run_calibration():
    """Ana kalibrasyon döngüsü. Kullanıcı 1-8 arası seçim yapar."""
    try:
        import m2_motor
    except ImportError:
        print("HATA: m2_motor modülü yüklenemedi.")
        sys.exit(1)

    if not MOCK_MODE:
        print("Donanım başlatılıyor...")
    m2_motor.init_hardware()
    time.sleep(0.5)

    # ── Sonuç depolama ──
    results: list[dict] = []

    print()
    print("=" * 56)
    print("  ENCODER + MESAFE KALİBRASYONU")
    print("=" * 56)
    print()
    print("  Seçenekler:")
    for i in range(1, LEVELS + 1):
        target = BASE_CM * i
        print(f"    [{i}]  {target:6.0f} cm  ({target/100:.1f} m) ileri")
    print()
    print("    [T]  Encoder tekrar test et")
    print("    [S]  Sonuçları göster")
    print("    [Q]  Çık")
    print()
    print("  Her testten önce robotu BAŞLANGIÇ noktasına koyun.")
    print()

    while True:
        choice = input("  Seçim: ").strip().upper()

        if choice == "Q":
            break

        if choice == "T":
            test_encoder_alive()
            continue

        if choice == "S":
            _print_results(results)
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= LEVELS):
            print(f"  Geçersiz. 1-{LEVELS} arası, T, S veya Q girin.")
            continue

        level = int(choice)
        target_cm = BASE_CM * level

        print()
        print(f"  ── Test: {target_cm:.0f} cm ({level}x) ──")
        print(f"  Robotu başlangıç noktasına koyun. ENTER ile başlat...")
        input()

        # Sıfırla
        m2_motor.reset_encoder_window()
        ticks_before_left, ticks_before_right = m2_motor.get_encoder_ticks()
        odo_before = m2_motor.get_total_distance_cm()

        # Sür
        print(f"  Sürüş başlıyor: {target_cm:.0f} cm...")
        t_start = time.monotonic()
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)

        # Encoder'ı canlı izle
        deadline = t_start + (target_cm / max(config.MOCK_CM_PER_SEC, 5.0)) * 15.0
        last_print = 0.0
        try:
            while True:
                now = time.monotonic()
                elapsed = now - t_start
                window_cm = m2_motor.get_measured_distance_cm()
                traveled = odo_before + window_cm

                if now - last_print >= 0.3:
                    tl, tr = m2_motor.get_encoder_ticks()
                    sys.stdout.write(
                        f"\r  {elapsed:5.1f}s | "
                        f"Enkoder: {window_cm:7.1f} cm | "
                        f"Hedef: {target_cm:.0f} cm | "
                        f"Tick L:{tl} R:{tr}   "
                    )
                    sys.stdout.flush()
                    last_print = now

                if window_cm >= target_cm:
                    break
                if now > deadline:
                    print(f"\n  ⚠️ Zaman aşımı ({elapsed:.1f}s)")
                    break
                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n  Kullanıcı kesti.")
        finally:
            m2_motor.stop()

        t_end = time.monotonic()
        elapsed = t_end - t_start

        # Son enkoder okuması
        ticks_after_left, ticks_after_right = m2_motor.get_encoder_ticks()
        window_cm = m2_motor.get_measured_distance_cm()
        odo_after = m2_motor.get_total_distance_cm()

        delta_ticks_left = ticks_after_left - ticks_before_left
        delta_ticks_right = ticks_after_right - ticks_before_right
        avg_ticks = (delta_ticks_left + delta_ticks_right) / 2.0

        # Zaman bazlı tahmin
        time_estimate_cm = elapsed * config.MOCK_CM_PER_SEC

        # Enkoder hesaplanan hız
        if elapsed > 0.1:
            encoder_speed_cm_s = window_cm / elapsed
        else:
            encoder_speed_cm_s = 0.0

        print()
        print(f"  ── Sonuçlar ──")
        print(f"  Süre:             {elapsed:.2f} s")
        print(f"  Sol tick:         {delta_ticks_left}")
        print(f"  Sağ tick:         {delta_ticks_right}")
        print(f"  Ortalama tick:    {avg_ticks:.1f}")
        print(f"  Enkoder mesafe:   {window_cm:.1f} cm")
        print(f"  Zaman tahmini:    {time_estimate_cm:.1f} cm")
        print(f"  Enkoder hız:      {encoder_speed_cm_s:.1f} cm/s")
        print()

        # Kullanıcıdan fiziksel ölçüm
        actual_str = input("  Mezura ile gerçek mesafe (cm, boş=bilmiyorum): ").strip()
        if actual_str:
            try:
                actual_cm = float(actual_str)
            except ValueError:
                actual_cm = None
        else:
            actual_cm = None

        results.append({
            "level": level,
            "target_cm": target_cm,
            "elapsed_s": round(elapsed, 2),
            "ticks_left": delta_ticks_left,
            "ticks_right": delta_ticks_right,
            "avg_ticks": avg_ticks,
            "encoder_cm": round(window_cm, 1),
            "time_cm": round(time_estimate_cm, 1),
            "actual_cm": actual_cm,
            "encoder_speed_cm_s": round(encoder_speed_cm_s, 1),
        })

        # Anlık kalibrasyon hesapla
        if actual_cm and avg_ticks > 0:
            measured_tpcm = avg_ticks / actual_cm
            print()
            print(f"  Bu ölçüme göre TICKS_PER_CM = {measured_tpcm:.4f}")
            print(f"  Config'deki mevcut değer     = {config.ENCODER_TICKS_PER_CM:.4f}")
            error_pct = abs(measured_tpcm - config.ENCODER_TICKS_PER_CM) / config.ENCODER_TICKS_PER_CM * 100
            print(f"  Sapma:                       %{error_pct:.1f}")

        print()
        print("  ────────────────────────────────────")
        print()

    # Cleanup
    m2_motor.cleanup()

    # Sonuç tablosu
    if results:
        _print_results(results)


def _print_results(results: list[dict]) -> None:
    """Tüm ölçüm sonuçlarını tablo olarak göster ve kalibrasyon öner."""
    if not results:
        print("  Henüz ölçüm yok.")
        return

    print()
    print("=" * 90)
    print("  KALİBRASYON SONUÇLARI")
    print("=" * 90)
    print()
    print(f"  {'Seviye':>6} | {'Hedef':>7} | {'Süre':>6} | {'Tick L':>7} | {'Tick R':>7} | "
          f"{'Enkoder':>8} | {'Zaman':>7} | {'Gerçek':>8} | {'Hata':>7}")
    print(f"  {'':>6} | {'cm':>7} | {'s':>6} | {'':>7} | {'':>7} | "
          f"{'cm':>8} | {'cm':>7} | {'cm':>8} | {'%':>7}")
    print("  " + "-" * 86)

    for r in results:
        actual = f"{r['actual_cm']:.1f}" if r["actual_cm"] else "---"
        if r["actual_cm"] and r["target_cm"] > 0:
            error = abs(r["actual_cm"] - r["target_cm"]) / r["target_cm"] * 100
            err_str = f"%{error:.1f}"
        else:
            err_str = "---"

        print(f"  {r['level']:>6} | {r['target_cm']:>7.0f} | {r['elapsed_s']:>6.2f} | "
              f"{r['ticks_left']:>7} | {r['ticks_right']:>7} | "
              f"{r['encoder_cm']:>8.1f} | {r['time_cm']:>7.1f} | "
              f"{actual:>8} | {err_str:>7}")

    # Kalibrasyon hesapla
    calibrated = [(r["avg_ticks"], r["actual_cm"])
                  for r in results if r["actual_cm"] and r["avg_ticks"] > 0]

    print()
    if len(calibrated) >= 1:
        total_ticks = sum(t for t, _ in calibrated)
        total_actual = sum(a for _, a in calibrated)
        recommended_tpcm = total_ticks / total_actual

        print(f"  Mevcut ENCODER_TICKS_PER_CM  = {config.ENCODER_TICKS_PER_CM:.4f}")
        print(f"  Önerilen ENCODER_TICKS_PER_CM = {recommended_tpcm:.4f}")

        # Hız hesapla
        speed_entries = [(r["actual_cm"], r["elapsed_s"])
                         for r in results if r["actual_cm"] and r["elapsed_s"] > 0.1]
        if speed_entries:
            total_cm = sum(c for c, _ in speed_entries)
            total_s = sum(s for _, s in speed_entries)
            recommended_speed = total_cm / total_s
            print()
            print(f"  Mevcut MOCK_CM_PER_SEC     = {config.MOCK_CM_PER_SEC:.1f}")
            print(f"  Önerilen MOCK_CM_PER_SEC    = {recommended_speed:.1f}")

        print()
        print("  config.py'de bu değerleri güncelleyin:")
        print(f'    ENCODER_TICKS_PER_CM = {recommended_tpcm:.4f}')
        if speed_entries:
            print(f'    MOCK_CM_PER_SEC      = {recommended_speed:.1f}')
    else:
        print("  Gerçek mesafe girilmediği için kalibrasyon hesaplanamadı.")
        print("  Ölçümlerinizi tekrarlayıp gerçek mesafeleri girin.")

    print()


def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   SeeFire Encoder Test + Mesafe Kalibrasyon Aracı   ║")
    print("╚══════════════════════════════════════════════════════╝")

    # Adım 1: Encoder canlılık testi
    if not MOCK_MODE:
        print()
        print("ADIM 1: Encoder bağlantı testi")
        print("────────────────────────────────")
        alive = test_encoder_alive()
        if not alive:
            print()
            resp = input("  Encoder çalışmıyor. Yine de devam edilsin mi? (e/H): ").strip().lower()
            if resp != "e":
                print("İptal edildi.")
                return

    # Adım 2: Kalibrasyon
    print()
    print("ADIM 2: Mesafe kalibrasyonu")
    print("────────────────────────────")
    run_calibration()


if __name__ == "__main__":
    main()

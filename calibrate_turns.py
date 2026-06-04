#!/usr/bin/env python3
"""
SeeFire — Tank Dönüş Kalibrasyon Aracı
========================================
Robotun tank dönüşlerini (pivot) farklı açılarda test eder.
Her dönüşten sonra kullanıcı gerçek açıyı girer, sonuçlara göre
MOCK_TURN_90_SECONDS değeri kalibre edilir.

Kullanım (Pi üzerinde):
    python3 calibrate_turns.py

Akış:
    1. [1]-[4] sağa dönüş: 90°, 180°, 270°, 360°
    2. [5]-[8] sola dönüş: 90°, 180°, 270°, 360°
    3. Her dönüşte: süre, enkoder tick, tahmini açı kaydedilir
    4. Kullanıcı gerçek açıyı girer (pusula/protraktör ile)
    5. Sonuç tablosu + önerilen MOCK_TURN_90_SECONDS değeri

Donanım:
    Düz zeminde çalıştırın. Robota bir yön referansı koyun
    (bant çizgi, pusula, veya protraktör).
    Tekerlekleri yerden keserek de test edilebilir.

Dönüş mekanizması:
    Tank dönüşü (pivot) — bir taraf ileri, diğer taraf geri.
    Süre: hedef_açı / 90° × MOCK_TURN_90_SECONDS
"""
from __future__ import annotations

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    print("UYARI: RPi.GPIO bulunamadı. MOCK MODDA çalışıyor.")
    MOCK_MODE = True


# ── Dönüş tanımları ───────────────────────────────────────────
TURNS = [
    {"id": 1, "angle": 90,  "dir": "right", "label": "90°  sağa"},
    {"id": 2, "angle": 180, "dir": "right", "label": "180° sağa"},
    {"id": 3, "angle": 270, "dir": "right", "label": "270° sağa"},
    {"id": 4, "angle": 360, "dir": "right", "label": "360° sağa"},
    {"id": 5, "angle": 90,  "dir": "left",  "label": "90°  sola"},
    {"id": 6, "angle": 180, "dir": "left",  "label": "180° sola"},
    {"id": 7, "angle": 270, "dir": "left",  "label": "270° sola"},
    {"id": 8, "angle": 360, "dir": "left",  "label": "360° sola"},
]


def run_calibration():
    """Ana kalibrasyon döngüsü."""
    try:
        import m2_motor
    except ImportError:
        print("HATA: m2_motor modülü yüklenemedi.")
        sys.exit(1)

    if not MOCK_MODE:
        print("Donanım başlatılıyor...")
    m2_motor.init_hardware()
    time.sleep(0.5)

    results: list[dict] = []

    while True:
        print()
        print("=" * 56)
        print("  TANK DÖNÜŞ KALİBRASYONU")
        print("=" * 56)
        print()
        print("  Sağa dönüşler:")
        for t in TURNS[:4]:
            turn_time = t["angle"] / 90.0 * config.MOCK_TURN_90_SECONDS
            print(f"    [{t['id']}]  {t['label']:<12} ({turn_time:.2f}sn)")
        print()
        print("  Sola dönüşler:")
        for t in TURNS[4:]:
            turn_time = t["angle"] / 90.0 * config.MOCK_TURN_90_SECONDS
            print(f"    [{t['id']}]  {t['label']:<12} ({turn_time:.2f}sn)")
        print()
        print("    [S]  Sonuçları göster")
        print("    [Q]  Çık")
        print()
        print(f"  Mevcut MOCK_TURN_90_SECONDS = {config.MOCK_TURN_90_SECONDS:.3f} sn")
        print(f"  TURN_SPEED = %{config.TURN_SPEED}  |  KICK = %{config.TURN_KICK_SPEED} × {config.TURN_KICK_SECONDS:.2f}sn")
        print()

        choice = input("  Seçim: ").strip().upper()

        if choice == "Q":
            break

        if choice == "S":
            _print_results(results)
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= 8):
            print("  Geçersiz. 1-8 arası, S veya Q girin.")
            continue

        turn_def = TURNS[int(choice) - 1]
        target_angle = turn_def["angle"]
        direction = turn_def["dir"]
        label = turn_def["label"]

        # Zaman bazlı süre hesapla
        turn_time = target_angle / 90.0 * config.MOCK_TURN_90_SECONDS

        print()
        print(f"  ── Test: {label} ──")
        print(f"  Tahmini süre: {turn_time:.2f} saniye")
        print(f"  Robota yön referansı koyun (bant/çizgi). ENTER ile başlat...")
        input()

        # Enkoder sıfırla
        m2_motor.reset_encoder_window()
        ticks_before_left, ticks_before_right = m2_motor.get_encoder_ticks()

        print(f"  Dönüş başlıyor: {direction} {turn_time:.2f}sn @ %{config.TURN_SPEED} PWM...")
        t_start = time.monotonic()

        # motor_turn: sağa = + açı, sola = - açı
        turn_angle = target_angle if direction == "right" else -target_angle

        try:
            m2_motor.motor_turn(turn_angle, config.TURN_SPEED)

            # Canlı durum
            last_print = 0.0
            while True:
                elapsed = time.monotonic() - t_start
                if elapsed >= turn_time:
                    break
                if elapsed - last_print >= 0.2:
                    tl, tr = m2_motor.get_encoder_ticks()
                    sys.stdout.write(
                        f"\r  {elapsed:5.2f}/{turn_time:.2f}s | "
                        f"Tick L:{tl} R:{tr}   "
                    )
                    sys.stdout.flush()
                    last_print = elapsed
                time.sleep(0.02)

        except KeyboardInterrupt:
            print("\n  Kullanıcı kesti.")
        finally:
            m2_motor.stop()

        t_end = time.monotonic()
        elapsed = t_end - t_start

        # Son enkoder okuması
        ticks_after_left, ticks_after_right = m2_motor.get_encoder_ticks()
        delta_left = ticks_after_left - ticks_before_left
        delta_right = ticks_after_right - ticks_before_right

        print()
        print(f"  ── Sonuçlar ──")
        print(f"  Süre:           {elapsed:.3f} s")
        print(f"  Hedef açı:      {target_angle}° ({direction})")
        print(f"  Sol tick:       {delta_left}")
        print(f"  Sağ tick:       {delta_right}")
        print()

        # Kullanıcıdan gerçek açı
        actual_str = input("  Gerçek dönen açı (derece, boş=bilmiyorum): ").strip()
        if actual_str:
            try:
                actual_angle = float(actual_str)
            except ValueError:
                actual_angle = None
        else:
            actual_angle = None

        results.append({
            "id": turn_def["id"],
            "label": label,
            "direction": direction,
            "target_angle": target_angle,
            "elapsed_s": round(elapsed, 3),
            "ticks_left": delta_left,
            "ticks_right": delta_right,
            "actual_angle": actual_angle,
        })

        # Anlık kalibrasyon hesapla
        if actual_angle and elapsed > 0.05:
            measured_t90 = elapsed / (actual_angle / 90.0)
            print()
            print(f"  Bu ölçüme göre TURN_90_SEC = {measured_t90:.4f} sn")
            print(f"  Config'deki mevcut değer    = {config.MOCK_TURN_90_SECONDS:.4f} sn")
            error_pct = abs(measured_t90 - config.MOCK_TURN_90_SECONDS) / config.MOCK_TURN_90_SECONDS * 100
            print(f"  Sapma:                      %{error_pct:.1f}")

        print()
        print("  ────────────────────────────────────")

    # Cleanup
    m2_motor.cleanup()

    if results:
        _print_results(results)


def _print_results(results: list[dict]) -> None:
    """Tüm ölçüm sonuçlarını tablo olarak göster ve kalibrasyon öner."""
    if not results:
        print("  Henüz ölçüm yok.")
        return

    print()
    print("=" * 80)
    print("  DÖNÜŞ KALİBRASYON SONUÇLARI")
    print("=" * 80)
    print()
    print(f"  {'#':>2} | {'Dönüş':<12} | {'Süre':>6} | {'Tick L':>7} | {'Tick R':>7} | "
          f"{'Gerçek':>8} | {'Hata':>7}")
    print(f"  {'':>2} | {'':>12} | {'s':>6} | {'':>7} | {'':>7} | "
          f"{'derece':>8} | {'%':>7}")
    print("  " + "-" * 76)

    for r in results:
        actual = f"{r['actual_angle']:.0f}°" if r["actual_angle"] else "---"
        if r["actual_angle"] and r["target_angle"] > 0:
            error = abs(r["actual_angle"] - r["target_angle"]) / r["target_angle"] * 100
            err_str = f"%{error:.1f}"
        else:
            err_str = "---"

        print(f"  {r['id']:>2} | {r['label']:<12} | {r['elapsed_s']:>6.3f} | "
              f"{r['ticks_left']:>7} | {r['ticks_right']:>7} | "
              f"{actual:>8} | {err_str:>7}")

    # Kalibrasyon hesapla — ağırlıklı ortalama
    calibrated = [(r["target_angle"], r["actual_angle"], r["elapsed_s"])
                  for r in results if r["actual_angle"]]

    print()
    if len(calibrated) >= 1:
        # Her ölçümden TURN_90_SECONDS hesapla, ağırlıklı ortalama
        total_weight = 0.0
        weighted_t90 = 0.0
        for target, actual, elapsed in calibrated:
            if actual > 0 and elapsed > 0:
                t90 = elapsed / (actual / 90.0)
                weight = actual  # büyük açılar daha güvenilir
                weighted_t90 += t90 * weight
                total_weight += weight

        if total_weight > 0:
            recommended_t90 = weighted_t90 / total_weight

            print(f"  Mevcut MOCK_TURN_90_SECONDS  = {config.MOCK_TURN_90_SECONDS:.4f} sn")
            print(f"  Önerilen MOCK_TURN_90_SECONDS = {recommended_t90:.4f} sn")
            print()
            print("  config.py'de bu değeri güncelleyin:")
            print(f'    MOCK_TURN_90_SECONDS = {recommended_t90:.4f}')
    else:
        print("  Gerçek açı girilmediği için kalibrasyon hesaplanamadı.")

    # Sağ/sol karşılaştırma
    right_results = [r for r in results if r["direction"] == "right" and r["actual_angle"]]
    left_results = [r for r in results if r["direction"] == "left" and r["actual_angle"]]

    if right_results and left_results:
        print()
        print("  ── Sağ/Sol Karşılaştırma ──")
        for r_side, label in [(right_results, "Sağa"), (left_results, "Sola")]:
            for r in r_side:
                if r["actual_angle"] and r["elapsed_s"] > 0:
                    t90 = r["elapsed_s"] / (r["actual_angle"] / 90.0)
                    print(f"    {label} {r['target_angle']}° → TURN_90 = {t90:.4f} sn")

    print()


def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     SeeFire Tank Dönüş Kalibrasyon Aracı            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("  Robota bir yön referansı koyun:")
    print("  → Zemine bantla çizgi çizin")
    print("  → Veya pusula/protraktör kullanın")
    print("  → Robota ok işareti yapıştırın")
    print()
    run_calibration()


if __name__ == "__main__":
    main()

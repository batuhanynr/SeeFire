#!/usr/bin/env python3
"""
SeeFire - Pivot Dönüş + Batarya Voltaj İzleme Testi
=====================================================
Pivot dönüş (kendi etrafında) sırasında batarya voltajını 10Hz'de okuyup
hem ekrana basar hem de CSV dosyasına kaydeder.

TEŞHIS YORUMU:
  - Voltaj 6.0V altına düşerse → AKÜ yetersiz (zayıf pil veya ince kablo)
  - Voltaj 6.0V üzerinde kalıyorsa → L298N yetersiz (sürücü kaybı)

Çalıştırma (Pi'de):
  python3 test_pivot_voltage.py          # sağa pivot dönüş (varsayılan)
  python3 test_pivot_voltage.py --left   # sola pivot dönüş
  python3 test_pivot_voltage.py --speed 80  # PWM hızını ayarla (varsayılan: 100)
  python3 test_pivot_voltage.py --duration 5  # süreyi ayarla (varsayılan: 4 sn)
"""

import sys
import os
import time
import argparse
import csv
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# ── GPIO / Mock algılama ─────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    print("[UYARI] RPi.GPIO bulunamadı → MOCK modunda çalışıyor.")
    MOCK_MODE = True

# ── Voltaj okuma fonksiyonu ──────────────────────────────────────────────────
def read_voltage() -> float:
    """MCP3208 ADC üzerinden gerçek batarya voltajını döner."""
    if MOCK_MODE:
        import random
        return round(7.4 - random.uniform(0, 0.8), 2)  # mock: 6.6-7.4V arası
    try:
        from m3_sensors import sensors as s3
        adc_val = s3.read_battery_adc()
        pin_v   = (adc_val / 4095.0) * 3.3
        real_v  = pin_v * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)
        return round(real_v, 2)
    except Exception as e:
        print(f"[HATA] Voltaj okunamadı: {e}")
        return -1.0

# ── Motor kontrolü (ham GPIO) ────────────────────────────────────────────────
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [config.MOTOR_IN1, config.MOTOR_IN2,
                config.MOTOR_IN3, config.MOTOR_IN4,
                config.MOTOR_ENA, config.MOTOR_ENB]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def start_pivot(direction: str, speed: int):
    """
    direction='right' → Sol ileri, Sağ geri  (araç sağa döner)
    direction='left'  → Sol geri,  Sağ ileri (araç sola döner)
    """
    pwm_a = GPIO.PWM(config.MOTOR_ENA, 1000)
    pwm_b = GPIO.PWM(config.MOTOR_ENB, 1000)
    pwm_a.start(speed)
    pwm_b.start(speed)

    if direction == 'right':
        # Sol motorlar İLERİ, Sağ motorlar GERİ
        GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN2, GPIO.LOW)
        GPIO.output(config.MOTOR_IN3, GPIO.LOW)
        GPIO.output(config.MOTOR_IN4, GPIO.HIGH)
        print(f"▶ Sağa pivot dönüş başladı (PWM={speed}%)")
    else:
        # Sol motorlar GERİ, Sağ motorlar İLERİ
        GPIO.output(config.MOTOR_IN1, GPIO.LOW)
        GPIO.output(config.MOTOR_IN2, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN4, GPIO.LOW)
        print(f"▶ Sola pivot dönüş başladı (PWM={speed}%)")

    return pwm_a, pwm_b

def stop_motors(pwm_a, pwm_b):
    pwm_a.stop()
    pwm_b.stop()
    for pin in [config.MOTOR_IN1, config.MOTOR_IN2,
                config.MOTOR_IN3, config.MOTOR_IN4]:
        GPIO.output(pin, GPIO.LOW)
    print("■ Motorlar durduruldu.")

# ── Ana test döngüsü ─────────────────────────────────────────────────────────
def run_test(direction: str, speed: int, duration: float, csv_path: str):
    print("=" * 60)
    print("  SeeFire - Pivot Dönüş + Voltaj İzleme Testi")
    print("=" * 60)
    print(f"  Yön      : {'SAĞA' if direction == 'right' else 'SOLA'} pivot")
    print(f"  PWM Hızı : %{speed}")
    print(f"  Süre     : {duration} saniye")
    print(f"  CSV Çıktı: {csv_path}")
    print(f"  UYARI EŞİĞİ: {config.BATTERY_CRIT_V}V (kritik)")
    print("=" * 60)

    # Başlangıç voltajı
    v_start = read_voltage()
    print(f"\n[t=0.00s] Başlangıç voltajı: {v_start}V")
    print("Motorlar 2 saniye sonra başlıyor... Hazır olun!\n")
    time.sleep(2)

    data = []   # (zaman, voltaj) log

    if MOCK_MODE:
        print("[MOCK] Pivot simülasyonu çalışıyor...")
        t0 = time.time()
        while time.time() - t0 < duration:
            elapsed = time.time() - t0
            v = read_voltage()
            data.append((round(elapsed, 2), v))
            status = "⚠️  DÜŞÜK!" if v < config.BATTERY_CRIT_V else "OK"
            print(f"  [t={elapsed:5.2f}s] Voltaj: {v:.2f}V  {status}")
            time.sleep(0.1)
    else:
        setup_gpio()
        pwm_a, pwm_b = start_pivot(direction, speed)
        t0 = time.time()
        v_min = v_start
        try:
            while time.time() - t0 < duration:
                elapsed = time.time() - t0
                v = read_voltage()
                if v > 0:
                    v_min = min(v_min, v)
                data.append((round(elapsed, 2), v))
                drop = v_start - v if v > 0 else 0
                status = "⚠️  DÜŞÜK!" if v < config.BATTERY_CRIT_V else "OK"
                print(f"  [t={elapsed:5.2f}s] Voltaj: {v:.2f}V  (düşüş: -{drop:.2f}V)  {status}")
                time.sleep(0.1)   # 10 Hz örnekleme
        finally:
            stop_motors(pwm_a, pwm_b)
            GPIO.cleanup()

    # ── Sonuç özeti ─────────────────────────────────────────────────────────
    v_end = read_voltage()
    v_min_all = min(v for _, v in data if v > 0) if data else v_start
    max_drop  = v_start - v_min_all

    print("\n" + "=" * 60)
    print("  TEST SONUCU")
    print("=" * 60)
    print(f"  Başlangıç voltajı : {v_start:.2f}V")
    print(f"  Minimum voltaj    : {v_min_all:.2f}V")
    print(f"  Maksimum düşüş   : -{max_drop:.2f}V")
    print(f"  Bitiş voltajı     : {v_end:.2f}V")
    print()

    if v_min_all < config.BATTERY_CRIT_V:
        print("  🔴 TANI: Voltaj kritik seviyenin altına düştü!")
        print("     → AKÜ yetersiz veya iç direnç yüksek.")
        print("     → Çözüm: Yeni/dolu akü veya daha kalın kablo.")
    elif max_drop > 0.5:
        print("  🟡 TANI: Voltaj düştü ama kritik seviyenin üstünde kaldı.")
        print("     → L298N'de voltaj kaybı yaşanıyor.")
        print("     → Çözüm: BTS7960 veya 2x L298N ile değiştir.")
    else:
        print("  🟢 TANI: Voltaj kararlı kaldı.")
        print("     → Güç sorunu değil, mekanik sürtünme olabilir.")
        print("     → Tekerlek ve şasi bağlantılarını kontrol et.")
    print("=" * 60)

    # ── CSV kaydet ──────────────────────────────────────────────────────────
    try:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['zaman_s', 'voltaj_V'])
            writer.writerows(data)
        print(f"\n  📁 Veriler kaydedildi: {csv_path}")
    except Exception as e:
        print(f"  [HATA] CSV kaydedilemedi: {e}")

# ── CLI arayüzü ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Pivot dönüş sırasında batarya voltajını izle'
    )
    parser.add_argument('--left',     action='store_true',
                        help='Sola pivot dönüş yap (varsayılan: sağa)')
    parser.add_argument('--speed',    type=int, default=100,
                        help='PWM hız yüzdesi 0-100 (varsayılan: 100)')
    parser.add_argument('--duration', type=float, default=4.0,
                        help='Test süresi saniye (varsayılan: 4.0)')
    parser.add_argument('--output',   type=str,
                        default='pivot_voltage_log.csv',
                        help='CSV çıktı dosyası adı')
    args = parser.parse_args()

    direction = 'left' if args.left else 'right'
    run_test(
        direction=direction,
        speed=max(0, min(100, args.speed)),
        duration=args.duration,
        csv_path=args.output
    )

if __name__ == '__main__':
    main()

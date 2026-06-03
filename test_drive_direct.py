#!/usr/bin/env python3
"""
SeeFire — Doğrudan Motor Sürüş Testi
====================================
SSH klavye gecikmesinden etkilenmeyen, doğrudan GPIO tabanlı motor testi.
M2 motor modülünü kullanmaz — ham GPIO sinyali gönderir.

Kullanım:
    python3 test_drive_direct.py forward    → 3 sn ileri (%50 PWM)
    python3 test_drive_direct.py turn       → 3 sn tank sağa dönüş (%50 PWM)
    python3 test_drive_direct.py both       → önce ileri, sonra dönüş

Donanım:
    L298N ×2 (ön + arka, paralel GPIO). Motor polaritesi wiring plan ile uyumlu:
      Sol ileri:  IN1=LOW,  IN2=HIGH
      Sağ ileri:  IN3=HIGH, IN4=LOW
      Tank sağ:   Sol ileri + Sağ geri

Güvenlik:
    Tekerlekleri yerden keserek veya geniş alanda çalıştırın.
    3 saniye sonra otomatik durur.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    print("RPi.GPIO bulunamadı. MOCK MODDA çalışıyor.")
    MOCK_MODE = True


def _init_gpio():
    """GPIO pinlerini yapılandır, PWM nesnelerini döndür."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    pins = [
        config.MOTOR_IN1, config.MOTOR_IN2,
        config.MOTOR_IN3, config.MOTOR_IN4,
        config.MOTOR_ENA, config.MOTOR_ENB,
    ]
    for pin in pins:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    pwm_a = GPIO.PWM(config.MOTOR_ENA, 1000)
    pwm_b = GPIO.PWM(config.MOTOR_ENB, 1000)
    return pwm_a, pwm_b


def _set_forward(gpio):
    """Düz ileri — sol ve sağ motorlar ileri yönde."""
    # Sol ileri: IN1=LOW, IN2=HIGH  (polarite ters — wiring plan)
    gpio.output(config.MOTOR_IN1, gpio.LOW)
    gpio.output(config.MOTOR_IN2, gpio.HIGH)
    # Sağ ileri: IN3=HIGH, IN4=LOW
    gpio.output(config.MOTOR_IN3, gpio.HIGH)
    gpio.output(config.MOTOR_IN4, gpio.LOW)


def _set_tank_right(gpio):
    """Tank sağa dönüş — sol ileri, sağ geri."""
    # Sol ileri
    gpio.output(config.MOTOR_IN1, gpio.LOW)
    gpio.output(config.MOTOR_IN2, gpio.HIGH)
    # Sağ geri
    gpio.output(config.MOTOR_IN3, gpio.LOW)
    gpio.output(config.MOTOR_IN4, gpio.HIGH)


def _stop(pwm_a, pwm_b):
    """Motorları durdur ve GPIO'yu temizle."""
    pwm_a.stop()
    pwm_b.stop()
    GPIO.cleanup()


def run_test(mode: str, pwm_pct: int = 50, duration: float = 3.0):
    """Belirtilen modda motor testi çalıştır.

    Args:
        mode: "forward" | "turn" | "both"
        pwm_pct: PWM görev döngüsü (0-100)
        duration: her test adımının süresi (saniye)
    """
    if MOCK_MODE:
        label = {"forward": "ileri", "turn": "tank sağa dönüş", "both": "ileri + dönüş"}
        print(f"[MOCK] {label[mode]} — {duration}s @ %{pwm_pct} PWM")
        time.sleep(duration if mode != "both" else duration * 2)
        print("[MOCK] Test tamamlandı.")
        return

    pwm_a, pwm_b = _init_gpio()
    pwm_a.start(pwm_pct)
    pwm_b.start(pwm_pct)

    try:
        if mode in ("forward", "both"):
            _set_forward(GPIO)
            print(f"İLERİ — %{pwm_pct} PWM, {duration}s...")
            time.sleep(duration)

        if mode in ("turn", "both"):
            _set_tank_right(GPIO)
            print(f"TANK SAĞ — %{pwm_pct} PWM, {duration}s...")
            time.sleep(duration)

    except KeyboardInterrupt:
        print("\nKullanıcı kesti.")
    finally:
        print("Motorlar durduruluyor...")
        _stop(pwm_a, pwm_b)
        print("GPIO temizlendi. Test tamamlandı.")


def main():
    modes = {"forward", "turn", "both"}
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    if mode not in modes:
        print(f"Kullanım: python3 {sys.argv[0]} [forward|turn|both]")
        print("  forward → sadece ileri sürüş")
        print("  turn    → sadece tank sağa dönüş")
        print("  both    → önce ileri, sonra dönüş (varsayılan)")
        sys.exit(1)

    print("=== SeeFire Doğrudan Motor Testi ===")
    print(f"Mod: {mode} | Tekerlekleri yerden kesin veya geniş alan!")
    print("Başlamak için ENTER...")
    input()
    run_test(mode)


if __name__ == "__main__":
    main()

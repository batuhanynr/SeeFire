#!/usr/bin/env python3
"""
SeeFire Navigasyon Test Betiği
==============================
Navigasyonu adım adım test eder:

  ADIM 1: Motor ileri/geri → ekranda encoder tick'lerini göster
  ADIM 2: Yerinde sağa dönüş (90°) testi
  ADIM 3: Yerinde sola dönüş (90°) testi
  ADIM 4: Kısa rota testi — 50 cm ileri git, dur (enkoder bazlı)

Her adım kullanıcı onayı bekler (ENTER). Ctrl+C ile çık.

Pi'de çalıştır:
    sudo /home/raspberry/SeeFire/.venv/bin/python3 test_navigation.py
"""
from __future__ import annotations

import sys
import time

import config

# ── GPIO / Mock ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    MOCK = False
except ImportError:
    print("[UYARI] RPi.GPIO yok — MOCK modda çalışıyor.")
    MOCK = True

PWM_HZ   = 1000
DRIVE_DC = config.DRIVE_SPEED   # % duty cycle ileri için
TURN_DC  = config.TURN_SPEED    # % duty cycle dönüş için
TURN_T   = config.MOCK_TURN_90_SECONDS  # saniye


# ── Donanım kurulumu ─────────────────────────────────────────────────────────
def hw_init():
    if MOCK:
        return None, None
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    pins = [config.MOTOR_IN1, config.MOTOR_IN2,
            config.MOTOR_IN3, config.MOTOR_IN4,
            config.MOTOR_ENA, config.MOTOR_ENB]
    for p in pins:
        GPIO.setup(p, GPIO.OUT)
        GPIO.output(p, GPIO.LOW)

    pwm_a = GPIO.PWM(config.MOTOR_ENA, PWM_HZ)
    pwm_b = GPIO.PWM(config.MOTOR_ENB, PWM_HZ)
    pwm_a.start(0)
    pwm_b.start(0)
    return pwm_a, pwm_b


_ticks_l = 0
_ticks_r = 0


def setup_encoders():
    if MOCK:
        return
    GPIO.setup(config.ENCODER_LEFT_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def _on_l(_ch):
        global _ticks_l
        _ticks_l += 1

    def _on_r(_ch):
        global _ticks_r
        _ticks_r += 1

    GPIO.add_event_detect(config.ENCODER_LEFT_PIN,  GPIO.RISING, callback=_on_l, bouncetime=2)
    GPIO.add_event_detect(config.ENCODER_RIGHT_PIN, GPIO.RISING, callback=_on_r, bouncetime=2)


def hw_cleanup(pwm_a, pwm_b):
    if MOCK:
        return
    _set_all_low()
    if pwm_a: pwm_a.stop()
    if pwm_b: pwm_b.stop()
    GPIO.cleanup()


# ── Düşük seviye motor fonksiyonları (dashboard ile aynı polarite) ───────────
def _set_all_low():
    if MOCK:
        return
    for p in [config.MOTOR_IN1, config.MOTOR_IN2,
              config.MOTOR_IN3, config.MOTOR_IN4]:
        GPIO.output(p, GPIO.LOW)


def drive_forward(pwm_a, pwm_b, dc=DRIVE_DC):
    if MOCK:
        print(f"  [MOCK] İleri — dc={dc}%")
        return
    # Left: IN1=LOW, IN2=HIGH for forward (physically inverted vs right)
    # Right: IN3=HIGH, IN4=LOW for forward
    GPIO.output(config.MOTOR_IN1, GPIO.LOW)
    GPIO.output(config.MOTOR_IN2, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(dc)
    pwm_b.ChangeDutyCycle(dc)


def drive_stop(pwm_a, pwm_b):
    if MOCK:
        print("  [MOCK] Dur")
        return
    _set_all_low()
    pwm_a.ChangeDutyCycle(0)
    pwm_b.ChangeDutyCycle(0)


def turn_right(pwm_a, pwm_b, secs=TURN_T, dc=TURN_DC):
    """Sağa pivot: sol geri + sağ ileri."""
    if MOCK:
        print(f"  [MOCK] Sağa dönüş — {secs}s")
        time.sleep(secs)
        return
    # Left backward: IN1=HIGH, IN2=LOW
    # Right forward: IN3=HIGH, IN4=LOW
    GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN2, GPIO.LOW)
    GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(dc)
    pwm_b.ChangeDutyCycle(dc)
    time.sleep(secs)
    drive_stop(pwm_a, pwm_b)


def turn_left(pwm_a, pwm_b, secs=TURN_T, dc=TURN_DC):
    """Sola pivot: sol ileri + sağ geri."""
    if MOCK:
        print(f"  [MOCK] Sola dönüş — {secs}s")
        time.sleep(secs)
        return
    # Left forward: IN1=LOW, IN2=HIGH
    # Right backward: IN3=LOW, IN4=HIGH
    GPIO.output(config.MOTOR_IN1, GPIO.LOW)
    GPIO.output(config.MOTOR_IN2, GPIO.HIGH)
    GPIO.output(config.MOTOR_IN3, GPIO.LOW)
    GPIO.output(config.MOTOR_IN4, GPIO.HIGH)
    pwm_a.ChangeDutyCycle(dc)
    pwm_b.ChangeDutyCycle(dc)
    time.sleep(secs)
    drive_stop(pwm_a, pwm_b)


# ── Yardımcı ─────────────────────────────────────────────────────────────────
def wait_enter(msg: str):
    try:
        input(f"\n[ENTER] {msg} (Ctrl+C → çıkış): ")
    except KeyboardInterrupt:
        print("\nÇıkılıyor…")
        sys.exit(0)


def tick_snapshot():
    return _ticks_l, _ticks_r


# ── TEST ADIMLARI ─────────────────────────────────────────────────────────────
def test_forward_backward(pwm_a, pwm_b):
    print("\n" + "="*55)
    print("ADIM 1: 2 saniye İLERİ → dur → 2 saniye GERİ → dur")
    print("="*55)
    wait_enter("Robotu serbest bırak, 2s ileri gidecek.")

    before_l, before_r = tick_snapshot()
    drive_forward(pwm_a, pwm_b)
    time.sleep(2.0)
    drive_stop(pwm_a, pwm_b)
    after_l, after_r = tick_snapshot()

    dl = after_l - before_l
    dr = after_r - before_r
    if dl + dr > 0:
        dist_cm = ((dl + dr) / 2.0) / config.ENCODER_TICKS_PER_CM
        print(f"  Encoder: Sol={dl} tik, Sağ={dr} tik  ≈ {dist_cm:.1f} cm")
    else:
        print("  Encoder tiki algılanmadı (bağlantıyı kontrol et).")

    wait_enter("Şimdi 2s GERİ gidecek.")
    if not MOCK:
        # Left backward: IN1=HIGH, IN2=LOW
        # Right backward: IN3=LOW, IN4=HIGH
        GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN2, GPIO.LOW)
        GPIO.output(config.MOTOR_IN3, GPIO.LOW)
        GPIO.output(config.MOTOR_IN4, GPIO.HIGH)
        pwm_a.ChangeDutyCycle(DRIVE_DC)
        pwm_b.ChangeDutyCycle(DRIVE_DC)
        time.sleep(2.0)
        drive_stop(pwm_a, pwm_b)
    else:
        print("  [MOCK] Geri — 2s")
        time.sleep(2.0)

    print("  Geri testi tamam.")


def test_turn_right(pwm_a, pwm_b):
    print("\n" + "="*55)
    print(f"ADIM 2: Sağa 90° pivot dönüş  ({TURN_T}s @ {TURN_DC}%)")
    print("="*55)
    wait_enter("Robot yerinde sağa dönecek.")
    turn_right(pwm_a, pwm_b)
    print("  Sağa dönüş tamam.")


def test_turn_left(pwm_a, pwm_b):
    print("\n" + "="*55)
    print(f"ADIM 3: Sola 90° pivot dönüş  ({TURN_T}s @ {TURN_DC}%)")
    print("="*55)
    wait_enter("Robot yerinde sola dönecek.")
    turn_left(pwm_a, pwm_b)
    print("  Sola dönüş tamam.")


def test_short_route(pwm_a, pwm_b):
    """50 cm encoder bazlı sürüş — navigasyonun temeli."""
    print("\n" + "="*55)
    print("ADIM 4: 50 cm ileri git (encoder bazlı)")
    print("="*55)
    target_cm = 50.0
    wait_enter(f"Robot {target_cm:.0f} cm ileri gidecek.")

    global _ticks_l, _ticks_r
    _ticks_l = 0
    _ticks_r = 0

    drive_forward(pwm_a, pwm_b)
    deadline = time.time() + 15.0   # güvenlik timeout

    while True:
        avg_ticks = (_ticks_l + _ticks_r) / 2.0
        traveled  = avg_ticks / config.ENCODER_TICKS_PER_CM
        print(f"\r  Sol={_ticks_l} Sağ={_ticks_r} → {traveled:.1f}/{target_cm:.0f} cm   ", end="", flush=True)

        if MOCK:
            time.sleep(0.2)
            _ticks_l += 10
            _ticks_r += 10

        if traveled >= target_cm:
            break
        if time.time() > deadline:
            print("\n  [UYARI] Timeout — encoder tiki gelmedi, manuel dur.")
            break
        time.sleep(0.05)

    drive_stop(pwm_a, pwm_b)
    avg_ticks = (_ticks_l + _ticks_r) / 2.0
    final_cm  = avg_ticks / config.ENCODER_TICKS_PER_CM
    print(f"\n  Durum: Sol={_ticks_l} Sağ={_ticks_r} → {final_cm:.1f} cm kat edildi.")

    if abs(final_cm - target_cm) < 5.0:
        print("  ✓ Encoder kalibrasyonu uygun.")
    else:
        print(f"  ✗ Hedef {target_cm:.0f} cm, gerçek {final_cm:.1f} cm.")
        print(f"    config.py → ENCODER_TICKS_PER_CM = {config.ENCODER_TICKS_PER_CM:.4f} değerini güncelle.")


# ── ANA PROGRAM ───────────────────────────────────────────────────────────────
def main():
    print("SeeFire Navigasyon Test Betiği")
    print(f"  config: DRIVE_SPEED={config.DRIVE_SPEED}% | TURN_SPEED={config.TURN_SPEED}%")
    print(f"          MOCK_TURN_90_SECONDS={config.MOCK_TURN_90_SECONDS}s")
    print(f"          ENCODER_TICKS_PER_CM={config.ENCODER_TICKS_PER_CM}")
    print(f"  GPIO: IN1={config.MOTOR_IN1} IN2={config.MOTOR_IN2} "
          f"IN3={config.MOTOR_IN3} IN4={config.MOTOR_IN4} "
          f"ENA={config.MOTOR_ENA} ENB={config.MOTOR_ENB}")
    print(f"  Encoder: L={config.ENCODER_LEFT_PIN} R={config.ENCODER_RIGHT_PIN}")
    if MOCK:
        print("  [MOCK MOD — Pi değil]")

    pwm_a, pwm_b = hw_init()
    setup_encoders()

    try:
        test_forward_backward(pwm_a, pwm_b)
        test_turn_right(pwm_a, pwm_b)
        test_turn_left(pwm_a, pwm_b)
        test_short_route(pwm_a, pwm_b)

        print("\n" + "="*55)
        print("TÜM TESTLER TAMAMLANDI")
        print("Sonuçlar yeterliyse navigasyon testine geçebilirsiniz:")
        print("  sudo /home/raspberry/SeeFire/.venv/bin/python3 main.py")
        print("="*55)

    except KeyboardInterrupt:
        print("\nKullanıcı çıkışı.")
    finally:
        hw_cleanup(pwm_a, pwm_b)


if __name__ == "__main__":
    main()

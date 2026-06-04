#!/usr/bin/env python3
"""
SeeFire — Akıllı Engel Geçme
=============================

1. Engel yoksa → 15sn ilerle → dur → sağa 90° bak 2sn → 180° sola bak 2sn → sağa 90° dön → tekrarla
2. Engel varsa (< 60cm) → dur → en geniş tarafa 90° dön → ilerle
Ters sensör (dönmeden önceki mesafe + 45cm) geçerse → tersine 90° dön → rota devam
3. Ön 600+cm → ufak ilerle → sol/sağ değişimine göre çaprazlık tespiti → düzelt
4. Yan duvar < 20cm → mikro düzeltme
5. Engel tespiti HER ZAMAN en üst öncelikte

Kullanım (Pi üzerinde):
python3 nav_no_cam.py
"""
from __future__ import annotations

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
import m2_motor
import m3_sensors
except ImportError as e:
print(f"HATA: Modül yüklenemedi: {e}")
sys.exit(1)

# ── Logging ayarı ─────────────────────────────────────────────────────
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s [%(levelname)s] %(message)s',
datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Sabitler ─────────────────────────────────────────────────────────────
OBSTACLE_THRESHOLD_CM = 60.0 # Engel algılama eşiği
EXTRA_CLEARANCE_CM = 45.0 # Ters sensör için ek mesafe (ilk mesafe + 45cm)
SCAN_INTERVAL_SEC = 15.0 # Tarama sürüş süresi
LOOK_DURATION_SEC = 2.0 # Bakış süresi
OPEN_FRONT_CM = 600.0 # Ön sensör bu değer üstü → çaprazlık kontrolü

WALL_TOO_CLOSE_CM = 20.0 # Duvar bu mesafeden yakınsa düzelt
WALL_NUDGE_DEG = 8 # Duvardan kaçınma mikro dönüş açısı
DIAGONAL_CHECK_CM = 10.0 # Çaprazlık kontrolü için ilerleme mesafesi
DIAGONAL_DELTA_THRESHOLD_CM = 5.0 # Sol/sağ değişim eşiği (çaprazlık tespiti)
DIAGONAL_NUDGE_DEG = 10 # Çaprazlık düzeltme açısı


class NavigationBot:
"""Akıllı engel geçme robotu."""

def __init__(self):
self.last_scan_time = 0.0
self.start_time = 0.0
self.is_bypassing = False
self.bypass_direction = None
self.turn_start_distance = 0.0 # Dönmeden önce ters sensör mesafesi

def run(self):
"""Ana döngü."""
logger.info("=" * 60)
logger.info(" AKILLI ENGEL GEÇME BAŞLIYOR")
logger.info(" Ctrl+C ile durdur")
logger.info("=" * 60)

self.start_time = time.time()
self.last_scan_time = time.time()

self._drive_with_acceleration(config.DRIVE_SPEED)

try:
while True:
# Sensörleri oku
reading = m3_sensors.get_navigation_sensors_filtered(samples=3)
left_cm, front_cm, right_cm = reading.left_cm, reading.front_cm, reading.right_cm

logger.info("[SENSÖR] Sol: %.1f | Ön: %.1f | Sağ: %.1f | Bypass: %s",
left_cm, front_cm, right_cm, self.is_bypassing)

		# Fusion sensörlerini de oku (ısı, duman)
		fusion = m3_sensors.get_fusion_sensors()
		logger.info("[FUSION] Smoke: %.0f | IR: %.1f°C | Alert: %s",
			fusion.smoke_level, fusion.ir_temp, "⚠️" if fusion.smoke_alert else "✓")

# ── ÖNCELİK 1: Engel kaçınma (HER DURUMDA, bypass dahil) ──
if 0 < front_cm < OBSTACLE_THRESHOLD_CM:
self._handle_immediate_obstacle(reading)
continue

# ── ÖNCELİK 2: Yan duvar çok yakın ──
if self._wall_too_close(left_cm, right_cm):
self._handle_wall_correction(left_cm, right_cm)
continue

# ── ÖNCELİK 3: Bypass modu → ters sensör kontrolü ──
if self.is_bypassing:
self._handle_bypassing(reading)
time.sleep(0.02)
continue

# ── ÖNCELİK 4: Ön 600+cm → çaprazlık kontrolü ──
if front_cm >= OPEN_FRONT_CM or front_cm <= 0:
self._handle_diagonal_check(reading)
continue

# ── ÖNCELİK 5: 15sn tarama ──
if time.time() - self.last_scan_time >= SCAN_INTERVAL_SEC:
self._perform_scan()
self.last_scan_time = time.time()

time.sleep(0.02)

except KeyboardInterrupt:
logger.info("\nCtrl+C ile durduruldu.")
finally:
m2_motor.stop()

# ────────────────────────────────────────────────────────────────
# ENGEL KAÇINMA
# ────────────────────────────────────────────────────────────────
def _handle_immediate_obstacle(self, reading):
"""Engel algılandı → dur → yön seç → 90° dön → ilerle."""
logger.warning("[ENGEL] Ön: %.1f cm. DURDURULUYOR...", reading.front_cm)

m2_motor.stop()
time.sleep(1.0)

# Yeniden ölçüm
reading = m3_sensors.get_navigation_sensors_filtered(samples=3)

if not (0 < reading.front_cm < OBSTACLE_THRESHOLD_CM):
logger.info("[ENGEL] Yanlış alarm (%.1f cm). Devam.", reading.front_cm)
self._drive_with_acceleration(config.DRIVE_SPEED)
return

left_cm = reading.left_cm
right_cm = reading.right_cm

# En geniş tarafı seç
direction = self._choose_direction(left_cm, right_cm)
logger.warning("[ENGEL] Teyit edildi. Bypass yönü: %s", direction)

# 90° dön
if direction == "RIGHT":
m2_motor.turn_right_90()
opposite_sensor = left_cm # Sağa döndük → ters sensör = sol
else:
m2_motor.turn_left_90()
opposite_sensor = right_cm # Sola döndük → ters sensör = sağ

# Dönmeden önceki ters sensör mesafesini kaydet
self.turn_start_distance = opposite_sensor
self.is_bypassing = True
self.bypass_direction = direction

logger.info("[ENGEL] Bypass başladı. Yön: %s, İlk ters mesafe: %.1f cm",
direction, self.turn_start_distance)

# Timer sıfırla
self.last_scan_time = time.time()

# İvmeli kalkış
self._drive_with_acceleration(config.DRIVE_SPEED)

# ────────────────────────────────────────────────────────────────
# BYPASS KONTROL
# ────────────────────────────────────────────────────────────────
def _handle_bypassing(self, reading):
"""Bypass sırasında: ters sensör (ilk mesafe + 45cm) geçti mi?"""
if self.bypass_direction == "RIGHT":
opposite_sensor = reading.left_cm
else:
opposite_sensor = reading.right_cm

target_distance = self.turn_start_distance + EXTRA_CLEARANCE_CM

logger.info("[BYPASS] Ters sensör: %.1f cm (Hedef: > %.1f cm)",
opposite_sensor, target_distance)

if opposite_sensor > target_distance:
# Engel geçildi! Tersine 90° dön
logger.info("[BYPASS] Engel geçildi! %.1f cm > %.1f cm. Geri dön...",
opposite_sensor, target_distance)

m2_motor.stop()
time.sleep(0.5)

if self.bypass_direction == "RIGHT":
m2_motor.turn_left_90()
else:
m2_motor.turn_right_90()

# Bypass bitti
self.is_bypassing = False
self.bypass_direction = None

self.last_scan_time = time.time()
logger.info("[BYPASS] Tamamlandı. DRIVING mod.")

self._drive_with_acceleration(config.DRIVE_SPEED)

# ────────────────────────────────────────────────────────────────
# YAN DUVAR KONTROL
# ────────────────────────────────────────────────────────────────
def _wall_too_close(self, left_cm: float, right_cm: float) -> bool:
"""Sol veya sağ duvar 20cm'den yakın mı?"""
return (0 < left_cm < WALL_TOO_CLOSE_CM) or (0 < right_cm < WALL_TOO_CLOSE_CM)

def _handle_wall_correction(self, left_cm: float, right_cm: float):
"""Duvara çok yakınsa → dur → mikro dön → devam."""
left_close = 0 < left_cm < WALL_TOO_CLOSE_CM
right_close = 0 < right_cm < WALL_TOO_CLOSE_CM

m2_motor.stop()
time.sleep(0.2)

if left_close and not right_close:
logger.warning("[DUVAR] Sol yakın: %.1f cm → sağa kaydır", left_cm)
m2_motor.motor_turn(WALL_NUDGE_DEG, config.TURN_SPEED)
elif right_close and not left_close:
logger.warning("[DUVAR] Sağ yakın: %.1f cm → sola kaydır", right_cm)
m2_motor.motor_turn(-WALL_NUDGE_DEG, config.TURN_SPEED)
elif left_close and right_close:
if left_cm < right_cm:
logger.warning("[DUVAR] İki taraf yakın. Sol daha yakın → sağa kaydır")
m2_motor.motor_turn(WALL_NUDGE_DEG, config.TURN_SPEED)
else:
logger.warning("[DUVAR] İki taraf yakın. Sağ daha yakın → sola kaydır")
m2_motor.motor_turn(-WALL_NUDGE_DEG, config.TURN_SPEED)

time.sleep(0.2)
self._drive_with_acceleration(config.DRIVE_SPEED)

# ────────────────────────────────────────────────────────────────
# ÇAPRAZLIK KONTROL (ön 600+cm)
# ────────────────────────────────────────────────────────────────
def _handle_diagonal_check(self, reading):
"""
Ön sensör 600+cm veya geçersiz → çaprazlık tespiti.
Ufak ilerle → sol/sağ değişimine bak → çaprazsa düzelt.
Makul mesafelerde (200 vs 180 gibi) düzeltme yapma.
"""
logger.info("[ÇAPRAZ] Ön: %.1f cm. Çaprazlık kontrolü...", reading.front_cm)

m2_motor.stop()
time.sleep(0.3)

# Mevcut sol/sağ kaydet
before_left = reading.left_cm if reading.left_cm > 0 else 999.0
before_right = reading.right_cm if reading.right_cm > 0 else 999.0

# Ufak ilerle
m2_motor.drive_distance_cm(DIAGONAL_CHECK_CM)
time.sleep(0.3)

# Sonra ölç
after = m3_sensors.get_navigation_sensors_filtered(samples=3)
after_left = after.left_cm if after.left_cm > 0 else 999.0
after_right = after.right_cm if after.right_cm > 0 else 999.0

delta_left = before_left - after_left # Pozitif = sol daralıyor
delta_right = before_right - after_right # Pozitif = sağ daralıyor

logger.info("[ÇAPRAZ] Önce Sol: %.1f Sağ: %.1f → Sonra Sol: %.1f Sağ: %.1f",
before_left, before_right, after_left, after_right)
logger.info("[ÇAPRAZ] Delta Sol: %.1f | Delta Sağ: %.1f", delta_left, delta_right)

# Makul mesafe kontrolü: 200 vs 180 gibi → düzeltme gereksiz
both_reasonable = (before_left > WALL_TOO_CLOSE_CM and before_right > WALL_TOO_CLOSE_CM)
close_side = min(before_left, before_right)
far_side = max(before_left, before_right)
ratio_ok = (far_side < close_side * 1.5) if close_side > 0 else True

if both_reasonable and ratio_ok:
logger.info("[ÇAPRAZ] Mesafeler makul. Düzeltme gereksiz. Devam.")
self._drive_with_acceleration(config.DRIVE_SPEED)
return

# Çaprazlık tespiti
corrected = False

# Sol daralıyor → sağa doğru gidiyoruz → sola dön
if delta_left > DIAGONAL_DELTA_THRESHOLD_CM:
logger.warning("[ÇAPRAZ] Sol duvar daralıyor (%.1f cm). Sola düzelt...",
delta_left)
m2_motor.motor_turn(-DIAGONAL_NUDGE_DEG, config.TURN_SPEED)
corrected = True

# Sağ daralıyor → sola doğru gidiyoruz → sağa dön
elif delta_right > DIAGONAL_DELTA_THRESHOLD_CM:
logger.warning("[ÇAPRAZ] Sağ duvar daralıyor (%.1f cm). Sağa düzelt...",
delta_right)
m2_motor.motor_turn(DIAGONAL_NUDGE_DEG, config.TURN_SPEED)
corrected = True

if corrected:
time.sleep(0.3)
# Düzelttikten sonra tekrar kontrol etmek için ufak ilerle
m2_motor.drive_distance_cm(DIAGONAL_CHECK_CM)
time.sleep(0.3)

recheck = m3_sensors.get_navigation_sensors_filtered(samples=3)
logger.info("[ÇAPRAZ] Düzeltme sonrası Sol: %.1f | Sağ: %.1f",
recheck.left_cm, recheck.right_cm)

self._drive_with_acceleration(config.DRIVE_SPEED)

# ────────────────────────────────────────────────────────────────
# TARAMA (15sn sürüş → sağ 90° 2sn → sol 180° 2sn → sağ 90°)
# ────────────────────────────────────────────────────────────────
def _perform_scan(self):
"""15sn sürüş sonrası: dur → sağa 90° bak 2sn → 180° sola bak 2sn → sağa 90° dön."""
logger.info("[TARAMA] Duruluyor...")

m2_motor.stop()

# Sağa 90° dön
logger.info("[TARAMA] Sağa 90° bak...")
m2_motor.turn_right_90()
time.sleep(LOOK_DURATION_SEC)
reading_right = m3_sensors.get_navigation_sensors_filtered()
logger.info("[TARAMA] Sağ yön: Sol=%.1f Ön=%.1f Sağ=%.1f",
reading_right.left_cm, reading_right.front_cm, reading_right.right_cm)

# 180° sola dön (sağ bakış pozisyonundan → tam sola bak)
logger.info("[TARAMA] 180° sola bak...")
m2_motor.turn_left_90()
m2_motor.turn_left_90()
time.sleep(LOOK_DURATION_SEC)
reading_left = m3_sensors.get_navigation_sensors_filtered()
logger.info("[TARAMA] Sol yön: Sol=%.1f Ön=%.1f Sağ=%.1f",
reading_left.left_cm, reading_left.front_cm, reading_left.right_cm)

# Sağa 90° dön (tekrar kuzeye bak)
logger.info("[TARAMA] Sağa 90° dön (kuzeye)...")
m2_motor.turn_right_90()

self._drive_with_acceleration(config.DRIVE_SPEED)
logger.info("[TARAMA] Bitti, sürüşe devam.")

# ────────────────────────────────────────────────────────────────
# YARDIMCILAR
# ────────────────────────────────────────────────────────────────
def _choose_direction(self, left_cm: float, right_cm: float) -> str:
"""En geniş tarafı seç."""
left_ok = left_cm if left_cm > 0 else 999.0
right_ok = right_cm if right_cm > 0 else 999.0
return "RIGHT" if right_ok > left_ok else "LEFT"

def _drive_with_acceleration(self, target_speed: int):
"""İvme ile kalkış."""
logger.info("[KALKIŞ] İvme ile → %%%d PWM", target_speed)
steps = 10
for i in range(1, steps + 1):
speed = int(target_speed * i / steps)
m2_motor.motor_drive("forward", speed)
time.sleep(0.2)
logger.info("[KALKIŞ] Tam hız.")


def main():
print()
print("╔════════════════════════════════════════════════════════════╗")
print("║ SeeFire — Akıllı Engel Geçme ║")
print("╚════════════════════════════════════════════════════════════╝")
print()
print("Akış:")
print(" 1. 15sn ilerle → sağ 90° bak 2sn → 180° sol bak 2sn → sağ 90° → tekrar")
print(" 2. Engel (< 60cm) → dur → geniş tarafa 90° → ilerle")
print(" 3. Ters sensör (ilk + 45cm) geçerse → ters 90° → rota devam")
print(" 4. Ön 600+ → çaprazlık kontrolü")
print(" 5. Yan < 20cm → mikro düzeltme")
print()

if not os.getenv("SEEFIRE_FORCE_MOCK"):
try:
import RPi.GPIO
except ImportError:
print("UYARI: RPi.GPIO yok — mock modda çalışacak.")

print("Donanım başlatılıyor...")
m2_motor.init_hardware()
m3_sensors.init_sensors()
time.sleep(0.5)

print()
input("Robot hazır. ENTER ile başlat... ")
print()

try:
bot = NavigationBot()
bot.run()
except KeyboardInterrupt:
print("\n\nCtrl+C ile durduruldu.")
except Exception as e:
print(f"\n\nHATA: {e}")
import traceback
traceback.print_exc()
finally:
print("\nTemizleniyor...")
m2_motor.cleanup()
m3_sensors.cleanup()
print("Bitti.")


if __name__ == "__main__":
main()

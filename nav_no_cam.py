#!/usr/bin/env python3
"""
SeeFire — Akıllı Engel Geçme (Basit Mantık)
==============================================

Robot engeli tespit eder → en geniş tarafa 90° dön → sürekli ileri
Ters sensör ilk mesafeden +45cm geçince → 90° geri dön → devam

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
MIN_CLEARANCE_CM = 45.0              # Min boşluk
OBSTACLE_THRESHOLD_CM = 60.0        # Engel algılama eşiği
EXTRA_CLEARANCE_CM = 45.0           # Ters sensör için ek mesafe (ilk dönüş + 45cm)
SCAN_INTERVAL_SEC = 15.0            # Tarama aralığı
LOOK_DURATION_SEC = 2.0             # Bakış süresi
OPEN_FRONT_CM = 600.0               # Ön sensör bu değer üstü → açık koridor / sensör hatası
CENTER_TOLERANCE_CM = 15.0          # Sol-sağ fark toleransı (ortalamada)
CENTER_NUDGE_DEG = 10               # Ortalama için mikro dönüş açısı
WALL_TOO_CLOSE_CM = 20.0            # Duvar bu mesafeden yakınsa düzelt
WALL_NUDGE_DEG = 8                  # Duvardan kaçınma mikro dönüş açısı


class NavigationBot:
    """Akıllı engel geçme robotu."""

    def __init__(self):
        self.turn_start_distance = 0.0  # İlk dönüşteki ters sensör mesafesi
        self.is_bypassing = False          # Bypass modunda mı?
        self.bypass_direction = None      # Bypass yönü
        self.last_scan_time = 0.0        # Son tarama zamanı
        self.start_time = 0.0           # Başlangıç zamanı

    def run(self):
        """Ana döngü (sonsuz, Ctrl+C ile dur)."""
        logger.info("=" * 60)
        logger.info("  AKILLI ENGEL GEÇME BAŞLIYOR")
        logger.info("  Ctrl+C ile durdur")
        logger.info("=" * 60)

        self.start_time = time.time()
        self.last_scan_time = self.start_time

        self._drive_with_acceleration(config.DRIVE_SPEED)

        try:
            while True:
                elapsed = time.time() - self.start_time

                # Sensörleri oku
                reading = m3_sensors.get_navigation_sensors_filtered(samples=3)
                left_cm, front_cm, right_cm = reading.left_cm, reading.front_cm, reading.right_cm

                logger.info("[SENSÖR] Sol: %.1f | Ön: %.1f | Sağ: %.1f | Bypass: %s",
                           left_cm, front_cm, right_cm, self.is_bypassing)

                # ── ÖNCELİK 1: Engel kaçınma (HER DURUMDA, bypass dahil) ──
                if 0 < front_cm < OBSTACLE_THRESHOLD_CM:
                    self._handle_immediate_obstacle(reading)
                    continue

                # ── ÖNCELİK 2: Yan duvar çok yakın → ufak manevrayla uzaklaş ──
                if self._wall_too_close(left_cm, right_cm):
                    self._handle_wall_correction(left_cm, right_cm)
                    continue

                # ── ÖNCELİK 3: Ön açık koridor / sensör hatası → ortala ──
                if front_cm >= OPEN_FRONT_CM or front_cm <= 0:
                    self._handle_center_correction(reading)
                    continue

                # Bypass modundaysak
                if self.is_bypassing:
                    self._handle_bypassing(reading)

                # Normal sürüş: tarama zamanlaması
                if elapsed - self.last_scan_time >= SCAN_INTERVAL_SEC:
                    self._perform_scan()
                    self.last_scan_time = elapsed

                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("\nCtrl+C ile durduruldu.")
        finally:
            m2_motor.stop()

    def _handle_immediate_obstacle(self, reading):
        """Engel algılandı → dur → yön seç → dön → ileri."""
        logger.warning("[ENGEL] Ön: %.1f cm. DURDURULUYOR...", reading.front_cm)

        # Dur + 2sn bekle
        m2_motor.stop()
        time.sleep(2.0)

        # Yeniden ölçüm al
        reading = m3_sensors.get_navigation_sensors_filtered(samples=3)

        if 0 < reading.front_cm < OBSTACLE_THRESHOLD_CM:
            # Hâlâ engel var → manevra başlat
            left_cm, front_cm, right_cm = reading.left_cm, reading.front_cm, reading.right_cm

            logger.warning("[ENGEL] Hâlâ engel: %.1f cm. Bypass başlatılıyor...", front_cm)

            # En geniş tarafı seç
            direction = self._choose_direction(left_cm, right_cm)
            logger.info("[ENGEL] Karar: %s tarafına dönlüyor.", direction)

            if direction == "RIGHT":
                m2_motor.turn_right_90()
                opposite_sensor = reading.left_cm
            else:
                m2_motor.turn_left_90()
                opposite_sensor = reading.right_cm

            # İlk dönüşteki ters sensör mesafesini kaydet
            self.turn_start_distance = opposite_sensor
            self.is_bypassing = True
            self.bypass_direction = direction

            # Timer'ı sıfırla (engel tespit edildi, 15sn geri sayım başlat)
            self.last_scan_time = time.time()
            logger.info("[ENGEL] Bypass başladı. Timer sıfırlandı. İlk ters mesafe: %.1f cm",
                       self.turn_start_distance)

            # Motor başlat (sürekli ileri)
            self._drive_with_acceleration(config.DRIVE_SPEED)

        else:
            # Yanlış alarm → sürüşe devam
            logger.info("[ENGEL] Yanlış alarm (%.1f cm). Sürüşe devam.", reading.front_cm)
            self._drive_with_acceleration(config.DRIVE_SPEED)

    def _wall_too_close(self, left_cm: float, right_cm: float) -> bool:
        """Sol veya sağ duvar 20cm'den yakın mı?"""
        return (0 < left_cm < WALL_TOO_CLOSE_CM) or (0 < right_cm < WALL_TOO_CLOSE_CM)

    def _handle_wall_correction(self, left_cm: float, right_cm: float):
        """Duvara çok yakınsa → dur → ufak mikro dön → devam et."""
        # Hangi taraf yakın?
        left_close = 0 < left_cm < WALL_TOO_CLOSE_CM
        right_close = 0 < right_cm < WALL_TOO_CLOSE_CM

        if left_close and not right_close:
            # Sol duvar yakın → sağa kaydır (duvardan uzaklaş)
            logger.warning("[DUVAR] Sol çok yakın: %.1f cm. Sağa kaydırılıyor...", left_cm)
            m2_motor.stop()
            time.sleep(0.2)
            m2_motor.motor_turn(WALL_NUDGE_DEG, config.TURN_SPEED)
            time.sleep(0.2)

        elif right_close and not left_close:
            # Sağ duvar yakın → sola kaydır (duvardan uzaklaş)
            logger.warning("[DUVAR] Sağ çok yakın: %.1f cm. Sola kaydırılıyor...", right_cm)
            m2_motor.stop()
            time.sleep(0.2)
            m2_motor.motor_turn(-WALL_NUDGE_DEG, config.TURN_SPEED)
            time.sleep(0.2)

        elif left_close and right_close:
            # İki taraf da yakın → dar geçit, hangisi daha yakınsa ondan uzaklaş
            if left_cm < right_cm:
                logger.warning("[DUVAR] İki taraf yakın (Sol: %.1f, Sağ: %.1f). Sağa kaydır...",
                              left_cm, right_cm)
                m2_motor.stop()
                time.sleep(0.2)
                m2_motor.motor_turn(WALL_NUDGE_DEG, config.TURN_SPEED)
                time.sleep(0.2)
            else:
                logger.warning("[DUVAR] İki taraf yakın (Sol: %.1f, Sağ: %.1f). Sola kaydır...",
                              left_cm, right_cm)
                m2_motor.stop()
                time.sleep(0.2)
                m2_motor.motor_turn(-WALL_NUDGE_DEG, config.TURN_SPEED)
                time.sleep(0.2)

        # Manevradan sonra sürüşe devam
        self._drive_with_acceleration(config.DRIVE_SPEED)

    def _handle_center_correction(self, reading):
        """Ön sensör 600+ cm veya geçersiz → dur → sol/sağ ortala."""
        logger.info("[MERKEZ] Ön: %.1f cm (açık/geçersiz). Sol/sağ kontrol...",
                   reading.front_cm)

        m2_motor.stop()
        time.sleep(0.5)

        left_cm = reading.left_cm
        right_cm = reading.right_cm

        # İki sensör de geçersizse → devam
        if left_cm <= 0 and right_cm <= 0:
            logger.info("[MERKEZ] Sol/sağ geçersiz. Devam.")
            self._drive_with_acceleration(config.DRIVE_SPEED)
            return

        # Geçerli olanları kullan
        left_ok = left_cm if left_cm > 0 else right_cm
        right_ok = right_cm if right_cm > 0 else left_cm

        diff = left_ok - right_ok

        logger.info("[MERKEZ] Sol: %.1f | Sağ: %.1f | Fark: %.1f cm",
                   left_ok, right_ok, diff)

        if abs(diff) > CENTER_TOLERANCE_CM:
            # Merkezde değil → küçük düzeltme
            if diff > 0:
                # Sol uzak, sağ yakın → sağa kaydır
                logger.info("[MERKEZ] Sağa kaydır (%.0f°)...", CENTER_NUDGE_DEG)
                m2_motor.motor_turn(CENTER_NUDGE_DEG, config.TURN_SPEED)
            else:
                # Sağ uzak, sol yakın → sola kaydır
                logger.info("[MERKEZ] Sola kaydır (%.0f°)...", CENTER_NUDGE_DEG)
                m2_motor.motor_turn(-CENTER_NUDGE_DEG, config.TURN_SPEED)

            time.sleep(0.3)
        else:
            logger.info("[MERKEZ] Merkezde ✓")

        # Devam et
        self._drive_with_acceleration(config.DRIVE_SPEED)

    def _handle_bypassing(self, reading):
        """Bypass modundayken: ters sensör kontrol → geçti mi?"""
        if self.bypass_direction == "RIGHT":
            opposite_sensor = reading.left_cm
        else:
            opposite_sensor = reading.right_cm

        target_distance = self.turn_start_distance + EXTRA_CLEARANCE_CM

        logger.info("[BYPASS] Ters sensör: %.1f cm (Hedef: > %.1f cm)",
                   opposite_sensor, target_distance)

        if opposite_sensor > target_distance:
            # Engel geçildi! Geri dön
            logger.info("[BYPASS] Ters sensör temiz! %.1f cm > %.1f cm. Geri dön...",
                       opposite_sensor, target_distance)

            m2_motor.stop()
            time.sleep(0.5)

            # Geri dön
            if self.bypass_direction == "RIGHT":
                m2_motor.turn_left_90()
            else:
                m2_motor.turn_right_90()

            # Bypass bitti
            self.is_bypassing = False
            self.bypass_direction = None

            # Timer'ı sıfırla (engel geçme bitti, 15sn geri sayım)
            self.last_scan_time = time.time()
            logger.info("[BYPASS] Engel geçildi. Timer sıfırlandı. DRIVING mod.")

            # Motor başlat
            self._drive_with_acceleration(config.DRIVE_SPEED)

    def _perform_scan(self):
        """Tarama: dur → sağa bak → sola bak → ileri."""
        logger.info("[TARAMA] Tarama başlıyor...")

        # Dur
        m2_motor.stop()

        # Sağa bak
        logger.info("[TARAMA] Sağa bak...")
        m2_motor.turn_right_90()
        time.sleep(LOOK_DURATION_SEC)
        reading_right = m3_sensors.get_navigation_sensors_filtered()
        logger.info("[TARAMA] Sağ yön: Sol=%.1f Ön=%.1f Sağ=%.1f",
                   reading_right.left_cm, reading_right.front_cm, reading_right.right_cm)

        # Sola bak (180° toplam)
        logger.info("[TARAMA] Sola bak...")
        m2_motor.turn_left_90()
        m2_motor.turn_left_90()
        time.sleep(LOOK_DURATION_SEC)
        reading_left = m3_sensors.get_navigation_sensors_filtered()
        logger.info("[TARAMA] Sol yön: Sol=%.1f Ön=%.1f Sağ=%.1f",
                   reading_left.left_cm, reading_left.front_cm, reading_left.right_cm)

        # Öne dön
        m2_motor.turn_right_90()

        # Sürüşe devam
        self._drive_with_acceleration(config.DRIVE_SPEED)
        logger.info("[TARAMA] Tarama bitti, sürüşe devam.")

    def _choose_direction(self, left_cm: float, right_cm: float) -> str:
        """En geniş tarafı seç."""
        left_ok = left_cm if left_cm > 0 else 999.0
        right_ok = right_cm if right_cm > 0 else 999.0

        if right_ok > left_ok:
            return "RIGHT"
        else:
            return "LEFT"

    def _drive_with_acceleration(self, target_speed: int):
        """İvme ile kalkış (yavaş)."""
        logger.info("[KALKIŞ] İvme ile kalkış → %%%d PWM", target_speed)
        steps = 10          # Daha fazla adım
        for i in range(1, steps + 1):
            speed = int(target_speed * i / steps)
            m2_motor.motor_drive("forward", speed)
            time.sleep(0.2)   # Daha uzun bekleme (yavaş ivme)
        logger.info("[KALKIŞ] Tam hıza ulaşıldı.")


def main():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     SeeFire — Akıllı Engel Geçme (Basit)              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("Algoritma:")
    print("  1. Engel tespit → dur → yön seç → 90° dön")
    print("  2. Sürekli ileri (adım adım değil)")
    print("  3. Ters sensör > ilk_mesafe + 45cm → 90° geri dön")
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
        bot.run()  # Sonsuz döngü

        print()
        print("=" * 60)
        print("  BİTTİ!")
        print("=" * 60)

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

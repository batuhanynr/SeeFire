#!/usr/bin/env python3
"""
SeeFire — Engel Geçme Testi
============================

Bağımsız engel geçme testi. Robotun engeli nasıl aştığını test etmek için.

Kullanım (Pi üzerinde):
    python3 obstacle_test.py

Akış:
    Robot engelin önüne koy → ENTER → bypass'ı izle
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
OBSTACLE_THRESHOLD_CM = 40.0        # Engel eşiği
OBSTACLE_CLOSE_CM = 20.0            # Çok yakın engel
OBSTACLE_BACKUP_CM = 15.0           # Geri gitme mesafesi
OBSTACLE_CLEARANCE_DELTA_CM = 15.0  # Engel temizleme payı
WALL_CLEARANCE_CM = 15.0            # Duvar çarpma eşiği
SIDE_STEP_CM = 5.0                  # Yanal adım boyutu
STEP_DISTANCE_CM = 5.0               # İleri adım boyutu
SIDE_PASS_SAFETY_CAP_CM = 200.0     # Yanal max
FORWARD_PASS_SAFETY_CAP_CM = 100.0  # İleri max
SIDE_DECISION_MARGIN_CM = 20.0      # Sol/sağ fark marjı


class ObstacleAvoidance:
    """Kamerasyız engel geçme."""

    def __init__(self):
        pass

    def avoid(self, reference_distance: float) -> None:
        """Engelden kaçınma manevrası."""
        direction = self._choose_open_side()
        logger.info("[OBSTACLE] D0=%.1f cm. Bypass: %s", reference_distance, direction)

        result = self._attempt_bypass(direction, reference_distance)

        if result is None:
            other = "LEFT" if direction == "RIGHT" else "RIGHT"
            logger.warning("[OBSTACLE] %s tarafı duvar. Tekrar: %s", direction, other)
            result = self._attempt_bypass(other, reference_distance)
            if result is None:
                m2_motor.stop()
                raise RuntimeError("İki taraf da kapalı — durduruldu.")

        side_distance, forward_distance = result
        self._return_to_route(direction, side_distance)
        logger.info("[OBSTACLE] Rotaya dönüldü. Yanal: %.1f cm, İleri: %.1f cm",
                   side_distance, forward_distance)

    def _choose_open_side(self) -> str:
        """Daha açık tarafı seç (kamera ipucu YOK)."""
        reading = m3_sensors.get_navigation_sensors_filtered(samples=3)
        left, right = reading.left_cm, reading.right_cm

        logger.info("[OBSTACLE] Sol: %.1f cm | Sağ: %.1f cm", left, right)

        left_ok = left if left > 0 else 999.0
        right_ok = right if right > 0 else 999.0

        if abs(left_ok - right_ok) >= SIDE_DECISION_MARGIN_CM:
            chosen = "RIGHT" if right_ok > left_ok else "LEFT"
            logger.info("[OBSTACLE] Açık taraf (ultrasonik): %s", chosen)
            return chosen

        logger.info("[OBSTACLE] Yanlar benzer → varsayılan SAĞ")
        return "RIGHT"

    def _attempt_bypass(self, direction: str, reference_distance: float):
        """Taraf seçili bypass."""
        logger.info("[BYPASS] Başlıyor. D0: %.1f cm", reference_distance)
        time.sleep(1.0)

        # 1. Yana dön
        if direction == "RIGHT":
            logger.info("[BYPASS] Sağa dön...")
            m2_motor.turn_right_90()
        else:
            logger.info("[BYPASS] Sola dön...")
            m2_motor.turn_left_90()
        time.sleep(1.0)

        # 2. Yanal geçiş
        side_distance, wall_hit = self._side_pass(direction, reference_distance)

        if wall_hit:
            self._retreat_from_wall(direction, side_distance)
            return None

        # 3. Kuzeye dön
        if direction == "RIGHT":
            logger.info("[BYPASS] Sola dön (kuzeye)...")
            m2_motor.turn_left_90()
        else:
            logger.info("[BYPASS] Sağa dön (kuzeye)...")
            m2_motor.turn_right_90()
        time.sleep(1.0)

        # 4. Yan sensör engeli tamamen geçene kadar ilerle
        forward_distance = self._drive_until_side_clear(direction, reference_distance)

        return side_distance, forward_distance

    def _retreat_from_wall(self, direction: str, traveled: float) -> None:
        """Duvar çarpınca geri çekil."""
        logger.info("[OBSTACLE] Duvar! %.1f cm geri çekil...", traveled)
        if direction == "RIGHT":
            m2_motor.turn_left_90()
            m2_motor.turn_left_90()
            if traveled > 0:
                self._drive_lateral(traveled)
            m2_motor.turn_right_90()
        else:
            m2_motor.turn_right_90()
            m2_motor.turn_right_90()
            if traveled > 0:
                self._drive_lateral(traveled)
            m2_motor.turn_left_90()

    def _return_to_route(self, direction: str, side_distance: float) -> None:
        """Rotaya dön."""
        logger.info("[BYPASS-GERI] Rotaya dön...")
        time.sleep(1.0)
        if direction == "RIGHT":
            logger.info("[BYPASS-GERI] Sola dön (west'e)...")
            m2_motor.turn_left_90()
            logger.info("[BYPASS-GERI] %.1f cm yanal geri...", side_distance)
            self._drive_lateral(side_distance)
            logger.info("[BYPASS-GERI] Sağa dön (kuzeye)...")
            m2_motor.turn_right_90()
        else:
            logger.info("[BYPASS-GERI] Sağa dön (east'e)...")
            m2_motor.turn_right_90()
            logger.info("[BYPASS-GERI] %.1f cm yanal geri...", side_distance)
            self._drive_lateral(side_distance)
            logger.info("[BYPASS-GERI] Sola dön (kuzeye)...")
            m2_motor.turn_left_90()
        time.sleep(1.0)
        logger.info("[BYPASS-GERI] Rotaya dönüldü.")

    @staticmethod
    def _drive_lateral(cm: float) -> None:
        """Yanal sürüş (odometer'ı kirletmez)."""
        before = m2_motor.get_total_distance_cm()
        m2_motor.drive_distance_cm(cm)
        m2_motor.set_total_distance_cm(before)

    def _side_pass(self, direction: str, reference_distance: float):
        """Yanal geçiş döngüsü."""
        clearance_attr = "left_cm" if direction == "RIGHT" else "right_cm"
        clear_threshold = reference_distance + OBSTACLE_CLEARANCE_DELTA_CM
        traveled = 0.0

        logger.info("[YAN] Başlıyor. Hedef: > %.1f cm", clear_threshold)
        time.sleep(1.0)

        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            clearance = getattr(reading, clearance_attr)
            wall = reading.front_cm

            logger.info("[YAN] Yan: %.1f cm | Ön: %.1f cm | Yol: %.1f cm",
                       clearance, wall, traveled)

            if clearance > clear_threshold:
                logger.info("[YAN] ENGEL GEÇİLDİ! Ekstra adımlar...")
                for i in range(3):
                    logger.info("[YAN] Ekstra %d/3", i + 1)
                    self._drive_lateral(SIDE_STEP_CM)
                    traveled += SIDE_STEP_CM
                    time.sleep(0.5)
                time.sleep(1.0)
                return traveled, False

            if 0 < wall < WALL_CLEARANCE_CM:
                logger.warning("[YAN] DUVAR! %.1f cm", wall)
                time.sleep(1.0)
                return traveled, True

            self._drive_lateral(SIDE_STEP_CM)
            traveled += SIDE_STEP_CM
            time.sleep(0.5)

            if traveled > SIDE_PASS_SAFETY_CAP_CM:
                logger.warning("[YAN] Güvenlik sınırı!")
                return traveled, False

    def _drive_until_side_clear(self, direction: str, reference_distance: float) -> float:
        """Kuzeye dönükken yan sensör engeli tamamen geçene kadar ilerle."""
        side_attr = "left_cm" if direction == "RIGHT" else "right_cm"
        threshold = reference_distance + OBSTACLE_CLEARANCE_DELTA_CM
        traveled = 0.0

        logger.info("[ILERI-GECIS] Yan sensör temizlenene kadar ileri. Hedef: > %.1f cm", threshold)
        time.sleep(1.0)

        while True:
            reading = m3_sensors.get_navigation_sensors_filtered(samples=2)
            side = getattr(reading, side_attr)

            logger.info("[ILERI-GECIS] Yan: %.1f cm | Ön: %.1f cm | Yol: %.1f cm",
                       side, reading.front_cm, traveled)

            if side > threshold:
                logger.info("[ILERI-GECIS] ENGEL TAMAMEN GERIDE! Ekstra adımlar...")
                for i in range(3):
                    logger.info("[ILERI-GECIS] Ekstra %d/3", i + 1)
                    m2_motor.drive_distance_cm(STEP_DISTANCE_CM)
                    traveled += STEP_DISTANCE_CM
                    time.sleep(0.5)
                time.sleep(1.0)
                return traveled

            if 0 < reading.front_cm < WALL_CLEARANCE_CM:
                logger.warning("[ILERI-GECIS] Ön duvar! %.1f cm", reading.front_cm)
                time.sleep(1.0)
                return traveled

            m2_motor.drive_distance_cm(STEP_DISTANCE_CM)
            traveled += STEP_DISTANCE_CM
            time.sleep(0.5)

            if traveled > FORWARD_PASS_SAFETY_CAP_CM:
                logger.warning("[ILERI-GECIS] Güvenlik sınırı!")
                return traveled


def main():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     SeeFire — Engel Geçme Testi                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("Talimat:")
    print("  1. Robotu engelin 30-40cm önüne koy")
    print("  2. Robot kuzeye (engel doğru) baksın")
    print("  3. ENTER'a bas")
    print("  4. Bypass'ı izle")
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
        # Önce engel mesafesini al
        reading = m3_sensors.get_navigation_sensors_filtered(samples=5)
        front_cm = reading.front_cm

        if not (0 < front_cm < OBSTACLE_THRESHOLD_CM):
            print(f"UYARI: Önde engel algılanamadı! Ön: {front_cm:.1f} cm")
            print("Robotu engelin önüne koy ve tekrar dene.")
            return

        print(f"Engel algılandı: {front_cm:.1f} cm")
        print("Bypass başlıyor...")
        print()

        # Bypass'ı çalıştır
        ObstacleAvoidance().avoid(front_cm)

        print()
        print("=" * 60)
        print("  BYPASS TAMAMLANDI!")
        print("=" * 60)
        print()
        print("Robot şimdi:")
        print("  - Rotasına döndü")
        print("  - Kuzeye (başlangıç yönüne) bakıyor")
        print()
        print("Test başarılı!")

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

"""
M5 Navigation - Koridor Traversal (Yeniden Yazıldı)

Davranış:
  1. BAŞLANGIÇ: Sol/sağ ultrasonik ile merkez kontrolü.
     - Merkezde değilse → sağa/sola yatay düzeltme hareketi yapıp merkeze gel.
     - Merkezde ise → navigasyona başla.

  2. SÜRÜŞ: 5'er metre (SEGMENT_CM) segmentler halinde ileri git.
     - Her CENTERING_INTERVAL_CM'de sol/sağ sensör oku,
       merkeze dönmeye çalış (küçük düzeltme hareketi).
     - Önde engel varsa dur (ObstacleBlockedError fırlat).

  3. SEGMENT SONU (her 5 metre): 360° tarama yap.
     - 4 × (90° sağa dön → bekle → snapshot al)
     - 4 × 90° = tam tur → robot orijinal yönüne geri döner.
     - Görüntü işleme her yön için fırsat bulur.
     - Ardından sürüşe devam.

Sabitler (aşağıda, ihtiyaca göre değiştirilebilir):
  SEGMENT_CM          = 500     # Her segment: 5 metre
  SCAN_WAIT_S         = 1.0     # Her 90° sonrası görüntü işleme bekleme süresi
  CENTER_TOLERANCE_CM = 25      # Bu farkın altında merkezde sayılır
  CENTERING_INTERVAL_CM = 150   # Kaç cm'de bir merkez kontrolü
  MAX_SEGMENTS        = 20      # Güvenlik: max segment sayısı
  NUDGE_CM            = 15      # Merkeze alma için yatay hareket mesafesi
"""
from __future__ import annotations

import logging
import time

import config
import m2_motor
import m3_sensors
import m4_vision

logger = logging.getLogger(__name__)

# ── Navigasyon sabitleri ────────────────────────────────────────────────────
SEGMENT_CM            = 500.0   # 5 metre segment uzunluğu
SCAN_WAIT_S           = 1.0     # 360° taramada her yön sonrası bekleme (s)
CENTER_TOLERANCE_CM   = 25.0    # Sol-sağ fark toleransı (cm) — bu altı "merkez"
CENTERING_INTERVAL_CM = 150.0   # Kaç cm'de bir merkez kontrolü yapılır
MAX_SEGMENTS          = 20      # Azami segment sayısı (güvenlik)
NUDGE_CM              = 15.0    # Merkeze alırken yatay hareket mesafesi (cm)
MAX_NUDGE_ATTEMPTS    = 4       # Tek merkez oturumunda en fazla düzeltme denemesi


class ObstacleBlockedError(RuntimeError):
    """Önde duvar/engel, aşılamadı."""


class NavigationController:

    def __init__(self, snapshot_callback=None):
        """
        snapshot_callback: callable(label: str) → None
            M6/M7 entegrasyonu için fotoğraf/veri kayıt hook'u.
            None ise varsayılan (sadece log) kullanılır.
        """
        self._snapshot_cb = snapshot_callback or self._default_snapshot

    # ──────────────────────────────────────────────────────────────────────
    # Dışarıdan çağrılan ana API
    # ──────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Başlangıç merkez kontrolü. Merkezde değilse düzelt."""
        logger.info("[NAV] Başlangıç merkez kontrolü başlıyor...")
        self._initial_center_check()
        logger.info("[NAV] Merkez kontrolü tamam. Navigasyon başlıyor.")

    def run(self, waypoints=None) -> None:
        """Ana navigasyon döngüsü. waypoints parametresi artık kullanılmaz
        (geriye dönük uyumluluk için bırakıldı)."""
        self.start()

        segment_number = 0
        while segment_number < MAX_SEGMENTS:
            segment_number += 1
            logger.info("[NAV] === SEGMENT %d başlıyor (%.0f cm) ===",
                        segment_number, SEGMENT_CM)
            self._drive_segment(segment_number)
            logger.info("[NAV] Segment %d tamamlandı. 360° tarama başlıyor.",
                        segment_number)
            self._scan_360(segment_number)

        logger.info("[NAV] Maksimum segment sayısına (%d) ulaşıldı. Duruyorum.",
                    MAX_SEGMENTS)
        self.shutdown()

    def shutdown(self) -> None:
        m2_motor.stop()

    # ──────────────────────────────────────────────────────────────────────
    # Başlangıç merkez kontrolü
    # ──────────────────────────────────────────────────────────────────────

    def _initial_center_check(self) -> None:
        """Başlangıçta sol/sağ duvarları ölç. Merkezde değilse düzelt."""
        for attempt in range(1, MAX_NUDGE_ATTEMPTS + 1):
            reading = m3_sensors.get_navigation_sensors_filtered()
            left_cm  = reading.left_cm
            right_cm = reading.right_cm

            if left_cm <= 0 and right_cm <= 0:
                logger.warning(
                    "[CENTER] Her iki sensör geçersiz — merkez kontrolü atlanıyor.")
                return

            diff = left_cm - right_cm
            logger.info(
                "[CENTER] Başlangıç: sol=%.1f cm, sağ=%.1f cm, fark=%.1f cm",
                left_cm, right_cm, diff)

            if abs(diff) <= CENTER_TOLERANCE_CM:
                logger.info("[CENTER] Robot merkezde. ✓")
                return

            # Merkeze al
            logger.info("[CENTER] Deneme %d/%d: %.1f cm düzeltme gerekiyor.",
                        attempt, MAX_NUDGE_ATTEMPTS, diff / 2.0)
            if diff > 0:
                # Sol duvar uzak, sağ duvar yakın → robot sola çekik → sağa kaydır
                self._nudge("RIGHT", NUDGE_CM)
            else:
                # Sağ duvar uzak, sol duvar yakın → robot sağa çekik → sola kaydır
                self._nudge("LEFT", NUDGE_CM)

            time.sleep(0.3)

        logger.warning("[CENTER] %d denemede tam merkez sağlanamadı, devam ediliyor.",
                       MAX_NUDGE_ATTEMPTS)

    # ──────────────────────────────────────────────────────────────────────
    # Segment sürüşü (SEGMENT_CM kadar ileri git)
    # ──────────────────────────────────────────────────────────────────────

    def _drive_segment(self, segment_id: int) -> None:
        """SEGMENT_CM kadar ileri sürer. Yol boyunca:
        - Engel varsa dur (ObstacleBlockedError fırlat).
        - Her CENTERING_INTERVAL_CM'de merkez kontrolü yap.
        """
        m2_motor.reset_encoder_window()
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)
        is_driving = True

        traveled   = 0.0
        next_center_at = CENTERING_INTERVAL_CM  # İlk merkez kontrolü km'si

        try:
            while True:
                traveled = m2_motor.get_measured_distance_cm()

                # 1. Hedef mesafeye ulaşıldı mı?
                if traveled >= SEGMENT_CM:
                    logger.info(
                        "[NAV] Segment %d tamamlandı (%.1f cm).",
                        segment_id, traveled)
                    break

                # 2. Batarya kontrolü
                try:
                    from m6_decision.decision import check_battery_health
                    if not check_battery_health():
                        raise RuntimeError("Kritik batarya — navigasyon durduruluyor.")
                except ImportError:
                    pass

                # 3. Engel kontrolü
                reading = m3_sensors.get_navigation_sensors_filtered()
                front_cm = reading.front_cm
                if 0 < front_cm <= config.OBSTACLE_THRESHOLD_CM:
                    logger.warning(
                        "[ENGEL] Önde engel: %.1f cm — segment durduruluyor.",
                        front_cm)
                    m2_motor.stop()
                    is_driving = False
                    raise ObstacleBlockedError(
                        f"Engel: {front_cm:.1f} cm (eşik: {config.OBSTACLE_THRESHOLD_CM})")

                # 4. Periyodik merkez kontrolü
                if traveled >= next_center_at:
                    m2_motor.stop()
                    is_driving = False
                    logger.info("[CENTER] %.0f cm'de merkez kontrolü.", traveled)
                    self._periodic_center_correction()
                    next_center_at += CENTERING_INTERVAL_CM
                    # Sürüşe devam
                    m2_motor.reset_encoder_window()
                    m2_motor.set_total_distance_cm(traveled)
                    m2_motor.motor_drive("forward", config.DRIVE_SPEED)
                    is_driving = True

                time.sleep(0.05)

        finally:
            if is_driving:
                m2_motor.stop()

        # Toplam mesafeyi güncelle
        current_total = m2_motor.get_total_distance_cm()
        m2_motor.set_total_distance_cm(current_total + traveled)

    # ──────────────────────────────────────────────────────────────────────
    # 360° tarama
    # ──────────────────────────────────────────────────────────────────────

    def _scan_360(self, segment_id: int) -> None:
        """Robot durur, 4 × (90° sağa dön + bekleme + snapshot).
        Net dönüş = 360° → robot orijinal yönüne geri döner.
        """
        m2_motor.stop()
        time.sleep(0.3)
        logger.info("[SCAN] 360° tarama başlıyor (segment %d).", segment_id)

        directions = ["K", "D", "G", "B"]  # Kuzey, Doğu, Güney, Batı
        for i, direction in enumerate(directions):
            label = f"seg{segment_id}-{direction}"
            logger.info("[SCAN] Yön: %s — snapshot: %s", direction, label)
            self._snapshot_cb(label)
            time.sleep(SCAN_WAIT_S)          # Görüntü işleme için bekle
            m2_motor.turn_right_90()         # Bir sonraki yöne dön
            time.sleep(0.2)                  # Dönüş sonrası stabilizasyon

        logger.info("[SCAN] 360° tarama tamamlandı. Robot orijinal yönde.")

    # ──────────────────────────────────────────────────────────────────────
    # Periyodik merkez düzeltme (sürüş içinde)
    # ──────────────────────────────────────────────────────────────────────

    def _periodic_center_correction(self) -> None:
        """Tek ölçüm yapıp, eğer merkez toleransı aşılmışsa bir nudge uygular."""
        reading = m3_sensors.get_navigation_sensors_filtered()
        left_cm  = reading.left_cm
        right_cm = reading.right_cm

        if left_cm <= 0 or right_cm <= 0:
            logger.warning("[CENTER] Sensör geçersiz — atlıyorum.")
            return

        diff = left_cm - right_cm
        logger.info("[CENTER] sol=%.1f cm, sağ=%.1f cm, fark=%.1f cm",
                    left_cm, right_cm, diff)

        if abs(diff) <= CENTER_TOLERANCE_CM:
            logger.info("[CENTER] Merkezdeyiz. ✓")
            return

        nudge_distance = min(abs(diff) / 2.0, NUDGE_CM)
        direction = "RIGHT" if diff > 0 else "LEFT"
        logger.info("[CENTER] Düzeltme: %s yönüne %.1f cm.", direction, nudge_distance)
        self._nudge(direction, nudge_distance)

    # ──────────────────────────────────────────────────────────────────────
    # Yatay kaydırma (nudge): dön-ilerle-geri dön
    # ──────────────────────────────────────────────────────────────────────

    def _nudge(self, direction: str, cm: float) -> None:
        """Robotu yatay olarak `cm` kadar kaydırır.
        Algoritma: 90° dön → cm ilerle → 90° geri dön (orijinal yöne bak).
        direction: "RIGHT" → sağa kaydır, "LEFT" → sola kaydır.
        """
        logger.info("[NUDGE] %s yönüne %.1f cm kaydırılıyor.", direction, cm)
        saved_dist = m2_motor.get_total_distance_cm()

        if direction == "RIGHT":
            m2_motor.turn_right_90()
            m2_motor.drive_distance_cm(cm)
            m2_motor.turn_left_90()
        else:
            m2_motor.turn_left_90()
            m2_motor.drive_distance_cm(cm)
            m2_motor.turn_right_90()

        # Yatay hareket kuzey ilerlemesini kirletmemeli
        m2_motor.set_total_distance_cm(saved_dist)
        time.sleep(0.2)

    # ──────────────────────────────────────────────────────────────────────
    # Varsayılan snapshot (M4 bağlantısı yoksa)
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _default_snapshot(label: str) -> None:
        logger.info("[SNAPSHOT] %s", label)
        try:
            m4_vision.capture_frame()
        except Exception as exc:
            logger.warning("[SNAPSHOT] Çerçeve alınamadı (%s): %s", label, exc)

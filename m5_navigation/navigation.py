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

logger = logging.getLogger(__name__)

# ── Navigasyon sabitleri ────────────────────────────────────────────────────
SEGMENT_CM            = 500.0   # 5 metre segment uzunluğu
SCAN_WAIT_S           = 3.0     # 360° taramada her yön sonrası bekleme (s)
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
        """Başlangıç merkez kontrolü (Bypass edildi)."""
        logger.info("[NAV] Başlangıç merkez kontrolü bypass edildi. Navigasyon doğrudan başlıyor.")

    def run(self, waypoints=None) -> None:
        """Ana navigasyon döngüsü (20 metreye ulaşana kadar 5'er metrelik segmentler halinde sürer ve tarar)."""
        self.start()

        total_target_distance = 2000.0  # 20 meters (2000 cm)
        segment_number = 1
        max_segments = 4  # 4 segments of 5m = 20m
        
        # Reset or get initial odometer reading
        start_odo = m2_motor.get_total_distance_cm()
        
        while segment_number <= max_segments:
            current_odo = m2_motor.get_total_distance_cm()
            traveled_total = current_odo - start_odo
            
            logger.info("[NAV] === SEGMENT %d/%d başlıyor (Şu ana kadar kat edilen: %.1f cm, Toplam Hedef: %.0f cm) ===",
                        segment_number, max_segments, traveled_total, total_target_distance)
            
            self._drive_segment(segment_number)
            
            logger.info("[NAV] Segment %d tamamlandı. 360° tarama başlıyor.",
                        segment_number)
            self._scan_360(segment_number)
            
            segment_number += 1

        final_odo = m2_motor.get_total_distance_cm()
        logger.info("[NAV] Navigasyon tamamlandı. Toplam kat edilen mesafe: %.1f cm. Duruyorum.", final_odo - start_odo)
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
        """SEGMENT_CM kadar ileri sürer. Yol boyunca engel kontrolü ve güvenlik kontrolleri yapar."""
        m2_motor.reset_encoder_window()
        m2_motor.motor_drive("forward", config.DRIVE_SPEED)
        is_driving = True

        segment_start_dist = m2_motor.get_total_distance_cm()

        start_time = time.time()
        timeout = 60.0  # 5 metre için 60 saniye aşım süresi

        last_ticks = m2_motor.get_encoder_ticks()
        last_ticks_time = time.time()

        try:
            while True:
                current_total = m2_motor.get_total_distance_cm()
                traveled = (current_total - segment_start_dist) + m2_motor.get_measured_distance_cm()

                # 1. Hedef mesafeye ulaşıldı mı?
                if traveled >= SEGMENT_CM:
                    logger.info(
                        "[NAV] Segment %d tamamlandı (%.1f cm).",
                        segment_id, traveled)
                    break

                # 2. Güvenlik: Maksimum süre aşımı (Zaman aşımı)
                if time.time() - start_time > timeout:
                    logger.warning("[NAV] HATA: Sürüş zaman aşımına uğradı! (60 sn limit)")
                    break

                # 3. Güvenlik: Fiziksel encoder kontrolü (Tick alınıyor mu?)
                current_ticks = m2_motor.get_encoder_ticks()
                if current_ticks != last_ticks:
                    last_ticks = current_ticks
                    last_ticks_time = time.time()
                elif time.time() - last_ticks_time > 3.0:
                    from m2_motor.motor import MOCK_MODE
                    if not MOCK_MODE:
                        logger.error("[NAV] KRİTİK GÜVENLİK UYARISI: Motor çalışmasına rağmen encoder tickleri gelmiyor! Kablo bağlantılarını kontrol edin.")
                        break

                # 4. Batarya kontrolü
                try:
                    from m6_decision.decision import check_battery_health
                    if not check_battery_health():
                        raise RuntimeError("Kritik batarya — navigasyon durduruluyor.")
                except ImportError:
                    pass

                # 5. Engel kontrolü
                reading = m3_sensors.get_navigation_sensors_filtered()
                front_cm = reading.front_cm
                logger.info("[ULTRASONIC] Sol: %.1f cm | Ön: %.1f cm | Sağ: %.1f cm", 
                            reading.left_cm, front_cm, reading.right_cm)

                if 0 < front_cm <= config.OBSTACLE_THRESHOLD_CM:
                    logger.warning(
                        "[ENGEL] Önde engel: %.1f cm. DURUYORUM.", front_cm)
                    m2_motor.stop()
                    is_driving = False

                    # Güncel penceredeki mesafeyi odometer'a kaydet
                    current_window = m2_motor.get_measured_distance_cm()
                    m2_motor.set_total_distance_cm(current_total + current_window)

                    # Kamera görüntüsü oturana kadar bekle (ucuz kamerada gecikme var)
                    settle = config.OBSTACLE_CAMERA_SETTLE_S
                    logger.info(
                        "[ENGEL] Kamera görüntüsü oturuyor, %.0f sn bekleniyor...", settle)
                    time.sleep(settle)
                    logger.info("[ENGEL] Bekleme tamamlandı, bypass manevrası başlıyor.")

                    # Kaçınma manevrasını başlat
                    from m5_navigation.position import PositionVerifier
                    from m5_navigation.obstacle import ObstacleAvoidance
                    pv = PositionVerifier()
                    oa = ObstacleAvoidance(pv)
                    oa.avoid(segment_id, front_cm)

                    # Sürüşe devam et
                    m2_motor.reset_encoder_window()
                    m2_motor.motor_drive("forward", config.DRIVE_SPEED)
                    is_driving = True
                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("[NAV] Kullanıcı tarafından durduruldu (Ctrl+C).")
            m2_motor.stop()
            is_driving = False
            raise
        finally:
            if is_driving:
                m2_motor.stop()

        # Son penceredeki mesafeyi odometer'a kalıcı olarak ekle
        current_total = m2_motor.get_total_distance_cm()
        final_window = m2_motor.get_measured_distance_cm()
        m2_motor.set_total_distance_cm(current_total + final_window)

    # ──────────────────────────────────────────────────────────────────────
    # 360° tarama (Sağ ve Sol yönleri tarar ve doğrular)
    # ──────────────────────────────────────────────────────────────────────
 
    def _scan_360(self, segment_id: int) -> None:
        """Robot durur. 
        1. Sağa 90° döner, fotoğraf çeker/arama yapar, sola 90° dönüp kuzeye bakar.
        2. Sola 90° döner, fotoğraf çeker/arama yapar, sağa 90° dönüp kuzeye bakar.
        """
        m2_motor.stop()
        logger.info("[SCAN] Tarama başlıyor (segment %d). Durma stabilizasyonu için bekleniyor...", segment_id)
        time.sleep(1.5)
 
        # 1. Sağa dön ve tara
        logger.info("[SCAN] Sağa (DOĞU) dönülüyor...")
        m2_motor.turn_right_90()
        logger.info("[SCAN] Dönüş sonrası duruluyor ve bekleniyor...")
        time.sleep(1.0)
        
        logger.info("[SCAN] Yön: D — snapshot alınıyor...")
        self._snapshot_cb(f"seg{segment_id}-D")
        time.sleep(SCAN_WAIT_S)
        
        logger.info("[SCAN] Sola dönmeden önce duruluyor ve bekleniyor...")
        time.sleep(1.0)
        logger.info("[SCAN] Sola dönüp tekrar Kuzey yönüne bakılıyor...")
        m2_motor.turn_left_90()
        logger.info("[SCAN] Kuzeye dönüş sonrası duruluyor ve bekleniyor...")
        time.sleep(1.5)
 
        # 2. Sola dön ve tara
        logger.info("[SCAN] Sola (BATI) dönülüyor...")
        m2_motor.turn_left_90()
        logger.info("[SCAN] Dönüş sonrası duruluyor ve bekleniyor...")
        time.sleep(1.0)
        
        logger.info("[SCAN] Yön: B — snapshot alınıyor...")
        self._snapshot_cb(f"seg{segment_id}-B")
        time.sleep(SCAN_WAIT_S)
        
        logger.info("[SCAN] Sağa dönmeden önce duruluyor ve bekleniyor...")
        time.sleep(1.0)
        logger.info("[SCAN] Sağa dönüp tekrar Kuzey yönüne bakılıyor...")
        m2_motor.turn_right_90()
        logger.info("[SCAN] Kuzeye dönüş sonrası duruluyor ve bekleniyor...")
        time.sleep(1.5)
 
        logger.info("[SCAN] Tarama tamamlandı.")
        time.sleep(1.5)

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
        logger.info("[SNAPSHOT] %s (Kameradan navigasyon için veri alma kaldırıldı)", label)

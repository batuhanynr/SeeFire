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
SCAN_WAIT_S           = 0.8     # taramada her yön sonrası kamera bekleme (s)
CENTER_TOLERANCE_CM   = 25.0    # Sol-sağ fark toleransı (cm) — bu altı "merkez"
CENTERING_INTERVAL_CM = 150.0   # Kaç cm'de bir merkez kontrolü yapılır
MAX_SEGMENTS          = 20      # Azami segment sayısı (güvenlik)
NUDGE_CM              = 15.0    # Merkeze alırken yatay hareket mesafesi (cm)
MAX_NUDGE_ATTEMPTS    = 4       # Tek merkez oturumunda en fazla düzeltme denemesi

HEADING_CHECK_INTERVAL_S = 2.0  # Sürüş sırasında yön kontrolü periyodu (saniye)
HEADING_MICRO_TURN_DEG   = 10   # Görsel yön düzeltmesi için mikro dönüş açısı


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
            
            logger.info("[NAV] Segment %d tamamlandı. 3 yönlü tarama başlıyor.",
                        segment_number)
            self._scan_three_directions(segment_number)
            
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
        _heading_last_check = time.time()

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

                # 5. Engel kontrolü — HIZLI ön okuma (düşük gecikme → erken tepki)
                front_fast = m3_sensors.get_front_distance(samples=2)

                if 0 < front_fast <= config.OBSTACLE_THRESHOLD_CM:
                    # Önce DUR, sonra teyit et (hareket halindeyken kör ilerlemeyi kes)
                    m2_motor.stop()
                    is_driving = False

                    # Median ile teyit: yanlış yansıma/gürültü mü, gerçek engel mi?
                    confirm = m3_sensors.get_navigation_sensors_filtered(samples=3)
                    front_cm = confirm.front_cm
                    logger.info("[ULTRASONIC] Sol: %.1f | Ön: %.1f (hızlı:%.1f) | Sağ: %.1f cm",
                                confirm.left_cm, front_cm, front_fast, confirm.right_cm)

                    if not (0 < front_cm <= config.OBSTACLE_THRESHOLD_CM):
                        # Yanlış alarm — sürüşe devam
                        logger.info("[ENGEL] Teyit edilemedi (%.1f cm) — sürüşe devam.", front_cm)
                        m2_motor.reset_encoder_window()
                        m2_motor.motor_drive("forward", config.DRIVE_SPEED)
                        is_driving = True
                        time.sleep(0.05)
                        continue

                    logger.warning("[ENGEL] Önde engel: %.1f cm. Bypass başlatılıyor.", front_cm)

                    # Güncel penceredeki mesafeyi odometer'a kaydet
                    current_window = m2_motor.get_measured_distance_cm()
                    m2_motor.set_total_distance_cm(current_total + current_window)

                    # Snapshot al
                    fire_conf = m4_vision.get_fire_confidence()
                    logger.info("[ENGEL] Snapshot alınıyor. Fire: %.2f", fire_conf)
                    self._snapshot_cb(f"obstacle-seg{segment_id}-{front_cm:.0f}cm")

                    # Çok yakınsa önce geri git
                    if 0 < front_cm < config.OBSTACLE_CLOSE_CM:
                        logger.info("[ENGEL] Çok yakın (%.1f cm) — %.0f cm geri gidiliyor.",
                                    front_cm, config.OBSTACLE_BACKUP_CM)
                        m2_motor.motor_drive("backward", config.DRIVE_SPEED)
                        time.sleep(config.OBSTACLE_BACKUP_CM / max(config.MOCK_CM_PER_SEC, 5.0))
                        m2_motor.stop()
                        time.sleep(0.5)

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

                # 6. Görsel yön düzeltmesi (her HEADING_CHECK_INTERVAL_S saniyede bir)
                if time.time() - _heading_last_check >= HEADING_CHECK_INTERVAL_S:
                    _heading_last_check = time.time()
                    correction = m4_vision.get_heading_correction()
                    if correction is not None:
                        logger.info(
                            "[HEADING] Görsel drift tespiti: %s → mikro düzeltme uygulanıyor.",
                            correction)
                        m2_motor.stop()
                        is_driving = False
                        m2_motor.set_total_distance_cm(
                            current_total + m2_motor.get_measured_distance_cm())
                        # DRIFT_RIGHT: robota sağa kaymış, sola döndür
                        # DRIFT_LEFT:  robota sola kaymış, sağa döndür
                        turn_deg = (-HEADING_MICRO_TURN_DEG
                                    if correction == "DRIFT_RIGHT"
                                    else HEADING_MICRO_TURN_DEG)
                        m2_motor.motor_turn(turn_deg, config.TURN_SPEED)
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
    # 3 yönlü tarama (ön → sağ → sol → ön)
    # ──────────────────────────────────────────────────────────────────────

    def _scan_three_directions(self, segment_id: int) -> None:
        """Robot durur. Ön, sağ ve sol yönleri snapshot + sensör ile tarar.
        Net dönüş = 0° → robot orijinal yönüne geri döner.

        Sıra: ön bak → sağa 90° → sağa bak → sola 90° → sola 90° → sola bak
              → sağa 90° → ön kontrol → devam
        """
        m2_motor.stop()
        time.sleep(0.3)
        logger.info("[SCAN] 3 yönlü tarama başlıyor (segment %d).", segment_id)

        # --- 1. ÖN ---
        self._snapshot_cb(f"seg{segment_id}-on")
        reading = m3_sensors.get_navigation_sensors_filtered()
        fire_conf = m4_vision.get_fire_confidence()
        logger.info("[SCAN] ÖN — front=%.0f cm | fire=%.2f", reading.front_cm, fire_conf)
        time.sleep(SCAN_WAIT_S)

        # --- 2. SAĞ ---
        m2_motor.turn_right_90()
        self._snapshot_cb(f"seg{segment_id}-sag")
        reading = m3_sensors.get_navigation_sensors_filtered()
        fire_conf = m4_vision.get_fire_confidence()
        logger.info("[SCAN] SAĞ — front=%.0f cm | fire=%.2f", reading.front_cm, fire_conf)
        time.sleep(SCAN_WAIT_S)

        # --- sola dön → sola dön (orijinalden 90° sol) ---
        m2_motor.turn_left_90()
        m2_motor.turn_left_90()

        # --- 3. SOL ---
        self._snapshot_cb(f"seg{segment_id}-sol")
        reading = m3_sensors.get_navigation_sensors_filtered()
        fire_conf = m4_vision.get_fire_confidence()
        logger.info("[SCAN] SOL — front=%.0f cm | fire=%.2f", reading.front_cm, fire_conf)
        time.sleep(SCAN_WAIT_S)

        # --- orijinal yöne geri dön ---
        m2_motor.turn_right_90()

        # --- Son ön kontrol ---
        reading = m3_sensors.get_navigation_sensors_filtered()
        logger.info("[SCAN] Tarama bitti. Ön: %.0f cm. Devam ediliyor.", reading.front_cm)
        if 0 < reading.front_cm <= config.OBSTACLE_THRESHOLD_CM:
            logger.warning("[SCAN] Tarama sonrası önde engel (%.0f cm) — bypass başlatılıyor.",
                           reading.front_cm)
            self._snapshot_cb(f"seg{segment_id}-post-scan-engel")
            from m5_navigation.position import PositionVerifier
            from m5_navigation.obstacle import ObstacleAvoidance
            ObstacleAvoidance(PositionVerifier()).avoid(segment_id, reading.front_cm)

    # ──────────────────────────────────────────────────────────────────────
    # 360° tarama sonrası görsel yön doğrulama
    # ──────────────────────────────────────────────────────────────────────

    def _verify_heading_after_scan(self) -> None:
        """360° tarama sonrası kameradan kuzeye bakılıyor mu doğrula.

        4×90° pivot dönüşleri hatalı kalibrasyonla tam 360° yapmayabilir.
        Görsel yön düzeltmesi robotu tekrar kuzeye hizalar.
        Hizalama sağlanana veya max deneme sayısına ulaşana kadar tekrarlar.
        """
        for attempt in range(3):
            correction = m4_vision.get_heading_correction()
            if correction is None:
                logger.info("[HEADING] Tarama sonrası yön doğrulandı. ✓")
                return
            logger.info(
                "[HEADING] Tarama sonrası drift: %s → düzeltme %d/3",
                correction, attempt + 1)
            turn_deg = (-HEADING_MICRO_TURN_DEG
                        if correction == "DRIFT_RIGHT"
                        else HEADING_MICRO_TURN_DEG)
            m2_motor.motor_turn(turn_deg, config.TURN_SPEED)
            time.sleep(0.3)
        logger.warning("[HEADING] Tarama sonrası yön tam hizalanamadı — sürüşe devam.")

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

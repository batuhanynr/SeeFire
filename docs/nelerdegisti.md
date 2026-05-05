# SeeFire — Rapor ile Mevcut Kod Arasındaki Değişiklikler

Bu belge, `SeeFire_Module_Documentation_Report.md` (ve PDF, v1.0, Nisan 2026) raporunda planlanan tasarımla, **newbekir** branch'indeki güncel Python kodu arasındaki tüm farkları listeler.

Yeni bir rapor yazılacağı zaman bu belgedeki bilgiler **güncel doğru (source of truth)** olarak kabul edilmelidir.

> **Source-of-Truth Önceliği:** Python kodu → `config.py` → `CLAUDE.md` → bu dosya → eski rapor/header'lar

---

## 1. Donanım ve Bileşen Değişiklikleri

| # | Konu | Rapordaki Plan | Güncel Kod | Değişiklik Nedeni |
|---|---|---|---|---|
| 1.1 | **ADC Entegresi** | MCP3008 (10-bit, 0–1023) | **MCP3208** (12-bit, 0–4095) | Daha yüksek hassasiyet. `sensors.py` → `_read_mcp3208()` fonksiyonu 12-bit SPI protokolü kullanıyor. ADC max değeri kodun her yerinde 4095. |
| 1.2 | **Ultrasonik Sensör Sayısı** | 2 adet HC-SR04 (Ön + Sağ) | **3 adet** HC-SR04 (Sol + Ön + Sağ) | Sadece duvar takibi değil, ön engel algılama + yan sensörlerle sıkışmayı önleme. `config.py`: `TRIG_LEFT/ECHO_LEFT`, `TRIG_FRONT/ECHO_FRONT`, `TRIG_RIGHT/ECHO_RIGHT`. |
| 1.3 | **Ultrasonik Sensör Pinleri** | Rapor Appendix A: `TRIG_FRONT=23, ECHO_FRONT=24, TRIG_RIGHT=25, ECHO_RIGHT=8` | `TRIG_LEFT=23, ECHO_LEFT=24, TRIG_RIGHT=25, ECHO_RIGHT=8, TRIG_FRONT=16, ECHO_FRONT=20` | Eski "front" pinleri artık "left" olarak adlandırıldı; 3. sensör (front) yeni pinlerde (16, 20). |
| 1.4 | **Batarya Tipi** | Raporda "LiPo 2S, 7.4V, 2200mAh" | **2S 18650 Li-ion Pack** (nominal 7.4V, max 8.4V, BMS'li) | 18650 hücreler daha güvenli ve şarj edilebilir. `config.py`: `BATTERY_MAX_V=8.4`, `BATTERY_NOMINAL_V=7.4`. |
| 1.5 | **Batarya Voltaj Bölücü** | Raporda belirtilmemiş (sadece ADC üzerinden okuma bahsediyor) | **20kΩ / 10kΩ voltaj bölücü** MCP3208'in 1. kanalında | `config.py`: `VDIV_R1=20000.0`, `VDIV_R2=10000.0`, `BATTERY_ADC_CH=1`. |
| 1.6 | **Batarya Eşik Değerleri** | Rapor Appendix B: `BATTERY_LOW_V=7.0`, `BATTERY_CRIT_V=6.6` | `BATTERY_LOW_V=6.8`, `BATTERY_CRIT_V=6.4` | Li-ion hücre başına 3.2V–4.2V aralığına göre kalibre edildi. |
| 1.7 | **Tehlike Eşikleri** | Rapor Section 6.2: `ir_temp > 55°C` VERIFY tetikleyici | `IR_TEMP_THRESHOLD = 60.0°C` (config.py) | Gerçek sensör testleri sonucu ayarlandı. |
| 1.8 | **MQ-2 ADC Max** | Rapor: smoke_level 0–1023 aralığında | smoke_level 0–**4095** aralığında | MCP3208 12-bit olduğu için değer aralığı 4 kat genişledi. Fusion score formülünde `smoke_level / 4095` kullanılmalıdır. |
| 1.9 | **Kaldırılan Sensörler** | Rapor C.2: MPU6050 ve DHT22 zaten kaldırılmış olarak belirtiliyor | Tamamen kaldırılmış, kodda hiçbir referans yok | Raporla uyumlu. |
| 1.10 | **Tekerlek Enkoder** | Raporda yok (dead-reckoning ile zaman tabanlı tahmin) | **2 adet tekerlek enkoderi** eklendi (GPIO 6, 21) | `config.py`: `ENCODER_LEFT_PIN=6`, `ENCODER_RIGHT_PIN=21`, `ENCODER_TICKS_PER_CM=20.0`. Motor modülünde rising-edge interrupt ile pulse sayımı yapılıyor. |

---

## 2. Navigasyon Mimarisi Değişiklikleri (M5)

Bu en büyük mimari değişikliktir.

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 2.1 | **Keşif Stratejisi** | Right-hand wall-following ile bilinmeyen ortamı keşfetme | **Sektör bazlı statik rota traversali**. Harita önceden çizilmiş, keşif aşaması yok. |
| 2.2 | **Harita** | Occupancy grid (40×40 hücre, 10cm çözünürlük) oluşturuluyor ve JSON olarak kaydediliyor | **Statik harita**. Grid oluşturma veya kaydetme yok. `save_map()`/`load_map()` M7'de hala mevcut ama M5 tarafından kullanılmıyor. |
| 2.3 | **Rota Tanımı** | Wall-following ile otomatik oluşturulan waypoints | `config.py`'de tanımlı sabit waypoints: `WAYPOINTS = [(100,1), (200,2), (300,3)]`. Her tuple: `(hedef_kuzey_mesafe_cm, sektör_id)`. |
| 2.4 | **Konum Kaynağı** | Dead-reckoning (motor komut süresi + yön ile pozisyon tahmini, düşük doğruluk) | **Tekerlek enkoderi** birincil konum kaynağı. `m2_motor.get_total_distance_cm()` ile encoder pulse'larından mesafe hesaplanıyor. |
| 2.5 | **Başlangıç Pozisyon Doğrulama** | Raporda yok | **`PositionVerifier.verify_start()`**: Robot harekete başlamadan önce sol/sağ HC-SR04 okumalarını `START_LEFT_CM`/`START_RIGHT_CM` ile karşılaştırıyor. Tolerans dışındaysa `RuntimeError` fırlatıyor. |
| 2.6 | **Midpoint Snapshot** | Raporda yok | Her sektörün orta noktasında (`(başlangıç + hedef) / 2`) robot duruyor ve fotoğraf çekiyor. Engel bypass sırasında bile midpoint atlanmıyor. |
| 2.7 | **Engel Kaçınma** | Wall-following sırasında sadece "turn left away from wall" | **Kamera + ultrasonik hibrit karar mekanizması**: M4 Canny-edge ile yön ipucu → ultrasonik fallback. `_side_pass()`: Engel yüzeyine bakan sensör (`left_cm` veya `right_cm`) engel temizlenene kadar yan geçiş. Encoder ile geri dönüş + lateral fine-tune. |
| 2.8 | **Sensör Filtreleme** | Tekil okuma | **Medyan filtreleme**: `get_navigation_sensors_filtered(samples=3)` — 3 okumanın medyanı alınarak gürültü/yankı artefaktları azaltılıyor. |
| 2.9 | **M5 Komutları** | `EXPLORE`, `PATROL`, `VERIFY`, `STOP`, `RESUME` komut seti | Komut seti kaldırıldı. `NavigationController.run()` direkt sektör döngüsü çalıştırıyor. M6'dan `execute_command()` çağrısı beklemiyor. |
| 2.10 | **Navigasyon Thread** | Rapor: ~100ms cadence'de sürekli döngü | `run()` metodu blocking şekilde çalışıyor. Ayrı bir thread M6 tarafından yönetilecek (henüz implement edilmedi). |

---

## 3. Motor Kontrol Değişiklikleri (M2)

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 3.1 | **Mesafe Bazlı Sürüş API** | Sadece `motor_drive(dir, speed)` ve `motor_turn(angle, speed)` | **`drive_distance_cm(cm)`**: Verilen mesafeyi encoder ile ölçerek sür, dur. **`turn_left_90()` / `turn_right_90()`**: 90° yerinde dönüş. M5 bunları kullanıyor. |
| 3.2 | **Toplam Mesafe Takibi** | Yok | **`get_total_distance_cm()` / `set_total_distance_cm()`**: Encoder pulse'larından biriken toplam kuzey mesafesi. Engel bypass sonrası yan mesafeler bu değerden çıkarılıyor. |
| 3.3 | **Batarya Okuma** | Rapor M2 Section: `M2_BATTERY_LOW_V = 9.6V (3S)`, `M2_BATTERY_CRIT_V = 8.4V (3S)` | `get_battery_voltage()` MCP3208 kanal 1'den okuyup voltaj bölücü formülü ile gerçek voltaj hesaplıyor. Eşikler: `LOW=6.8V`, `CRIT=6.4V` (2S). |
| 3.4 | **Dönüş Yöntemi** | Açıya göre orantılı zamanlı dönüş | `_turn_in_place()`: Sabit `MOCK_TURN_90_SECONDS` (0.8s) süreyle diferansiyel sürüş. Encoder diferansiyel ile açı ölçümü yok, zaman bazlı. |

---

## 4. Sensör Entegrasyonu Değişiklikleri (M3)

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 4.1 | **Navigasyon Veri Yapısı** | `m3_ultrasonic_t`: sadece `left_cm`, `right_cm` | **`NavData`**: `left_cm`, `front_cm`, `right_cm`, `timestamp`. `center_cm` backward-compat property olarak alias. |
| 4.2 | **Sensör Sıralı Okuma** | 2 sensör sıralı okunuyor | 3 sensör sıralı okunuyor (cross-talk önleme için eşzamanlı tetikleme yok). |
| 4.3 | **Fusion Smoke Aralığı** | `smoke_level / 1023` | `smoke_level / 4095` olmalı (12-bit ADC). **Not:** M6 henüz implement edilmediğinden fusion formülü henüz kodda yok. Rapor yazılırken formül `smoke_level / 4095` olarak güncellenmelidir. |
| 4.4 | **API Fonksiyonları** | `m3_get_ultrasonic_distances()`, `m3_get_navigation_sensors()` | `get_navigation_sensors()` (NavData döndürür), `get_navigation_sensors_filtered(samples=3)` (medyan filtreli), `read_battery_adc()` (M2 için). |

---

## 5. Görüntü İşleme Değişiklikleri (M4)

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 5.1 | **YOLOv8n Pipeline** | Tam pipeline: model yükleme, 320×320 inference, 5 FPS thread, `m4_vision_result_t` yayın | **Henüz implement edilmedi.** Sadece kamera açma/kapama ve frame capture var. |
| 5.2 | **Engel Yön İpucu** | Raporda yok | **`determine_turn_direction()`**: Canny edge + alt-yarı ROI + sol/sağ boş piksel sayımı ile `"LEFT"` / `"RIGHT"` / `None` döndürüyor. M5 obstacle bypass tarafından kullanılıyor. |
| 5.3 | **Kamera Çözünürlüğü** | 320×320 (YOLO input) | 640×480 (raw capture). YOLO entegre edildiğinde 320×320 resize eklenecek. |
| 5.4 | **Snapshot API** | `m4_capture_snapshot(buf, sz, len)` → JPEG bytes | Sadece `capture_frame()` → raw frame. M7 `save_snapshot()` ile JPEG yazılıyor. |

---

## 6. Karar Motoru Değişiklikleri (M6)

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 6.1 | **FSM State'ler** | 5 state: `INIT → EXPLORE → PATROL → VERIFY → ALARM` | **Henüz implement edilmedi.** `decision.py` sadece placeholder. Planlanan state'ler: `INIT → NAVIGATE → VERIFY → ALARM → STOP` (EXPLORE/PATROL kaldırıldı, statik rota nedeniyle NAVIGATE birleştirildi). |
| 6.2 | **Fusion Score** | Formül raporda tanımlı: `(0.5×vision) + (0.3×smoke/1023) + (0.2×IR_score)` | Kodda yok. Formül `config.py`'deki ağırlıklar (`W_VISION=0.5`, `W_SMOKE=0.3`, `W_IR=0.2`) ile aynı kalacak, ama `smoke/4095` olarak güncellenmeli. |
| 6.3 | **Alarm Orkestrasyonu** | M6 → M2 (`set_alarm`), M4 (`capture_snapshot`), M5 (`STOP`), M7 (`log_event`) | Henüz bağlanmadı. |

---

## 7. Veri Kayıt Değişiklikleri (M7)

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 7.1 | **Events Tablosu Şeması** | 10 sütun: `row_id, event_type, timestamp, pos_x, pos_y, confidence, vision_conf, smoke_level, ir_temp, snapshot_path, details` | 6 sütun: `id, timestamp, event_type, fusion_score, sensor_data, snapshot_path`. Daha basit ama işlevsel. |
| 7.2 | **Event Tipleri** | INTEGER enum: 0–8 (`STATE_CHANGE`, `FIRE_DETECTED`, vb.) | STRING: `"STATE_CHANGE"`, `"FIRE_DETECTED"`, vb. Daha okunabilir. |
| 7.3 | **Veri Dizini** | Sabit `/data/` | Ortam değişkeni `SEEFIRE_DATA_DIR` veya repo-içi `runtime_data/`. Mock modda geliştirme makinesinde çalışabiliyor. |
| 7.4 | **Snapshot Dosya Adı** | `img_NNN.jpg` (sayısal sayaç) | `{event_id}_{YYYYMMDD_HHMMSS}.jpg` (event ID + timestamp) |
| 7.5 | **SQLite WAL Mode** | Rapor Risk R8: "planned for v0.2" | **Aktif:** `PRAGMA journal_mode=WAL` init'te çalıştırılıyor. |
| 7.6 | **m7_event_t** | Rapordaki C struct: 10 alan (pos_x, pos_y, vision_conf, smoke_level, ir_temp, details dahil) | Python dataclass: 5 alan (`timestamp, event_type, fusion_score, sensor_data, snapshot_path`). Detaylı sensör verisi `sensor_data` string'inde tutulabilir. |

---

## 8. Yazılım Mimarisi Değişiklikleri

| # | Konu | Rapordaki Plan | Güncel Kod |
|---|---|---|---|
| 8.1 | **MOCK Mode** | Raporda bahsedilmiyor. Sadece RPi üzerinde çalışacak kod tasarımı. | Kapsamlı MOCK mode: `RPi.GPIO`, `smbus2`, `spidev`, `opencv` yoksa sistem çökmez. M2/M3 rastgele sensör değerleri üretiyor. M4 `None` döndürüyor. |
| 8.2 | **Başlatma Sırası** | Rapor: `M7 → M2 → M3 → M4 → M5 → M6` | `main.py`: `M7 → M2 → M3 → M4`. M5 ve M6 henüz bağlı değil. |
| 8.3 | **Thread Modeli** | 3 thread: FSM (M6, 500ms), Vision (M4, 5FPS), Navigation (M5, 100ms) | Henüz thread yok. Tüm modüller synchronous çalışıyor. M6 implement edildiğinde thread modeli devreye girecek. |
| 8.4 | **Config Sabitleri** | Rapor Appendix B: `OBSTACLE_DIST_CM`, `WALL_FOLLOW_DIST_CM`, `GRID_RESOLUTION_M`, `NAV_LOOP_MS`, `CRUISE_SPEED`, `GRID_WIDTH/HEIGHT_CELLS` | Bu sabitler kaldırıldı. Yerine: `WAYPOINTS`, `STEP_DISTANCE_CM`, `SIDE_STEP_CM`, `OBSTACLE_THRESHOLD_CM`, `OBSTACLE_CLEAR_CM`, `START_LEFT/RIGHT_CM`, `POSITION_TOLERANCE_CM`, `FINE_TUNE_STEP_CM`, `DRIVE_SPEED`, `TURN_SPEED`, `ENCODER_TICKS_PER_CM`, `MOCK_CM_PER_SEC`, `MOCK_TURN_90_SECONDS` eklendi. |
| 8.5 | **GPIO Pin Doğrulama** | Raporda yok | `config.validate_gpio_pins()`: Başlangıçta tüm GPIO pin'lerinin benzersiz olduğunu kontrol ediyor. Çakışma varsa `ValueError` fırlatıyor. |
| 8.6 | **Fusion Ağırlık Doğrulama** | Raporda yok | `config.validate_fusion_weights()`: `W_VISION + W_SMOKE + W_IR ≈ 1.0` kontrol ediyor. |

---

## 9. Modül Implementasyon Durumu

| Modül | Rapordaki Durum | Güncel Durum |
|---|---|---|
| M1 | Sadece donanım spesifikasyonu | Değişiklik yok — hala sadece donanım |
| M2 | Tasarım aşaması (header) | **Implement edildi:** Motor sürüş, enkoder mesafe, batarya okuma, alarm I/O, mock mode |
| M3 | Tasarım aşaması (header) | **Implement edildi:** 3 ultrasonik sensör, MQ-2, MLX90614, medyan filtreleme, batarya ADC, mock mode |
| M4 | Tasarım aşaması (header) | **Kısmen implement edildi:** Kamera açma/kapama, frame capture, engel yön ipucu (Canny). **Yok:** YOLOv8n inference pipeline |
| M5 | Tasarım aşaması (header) | **Implement edildi:** Waypoint sektör traversal, midpoint/waypoint snapshot, engel kaçınma, başlangıç pozisyon doğrulama, lateral fine-tune |
| M6 | Tasarım aşaması (header) | **Henüz implement edilmedi:** Placeholder. FSM, fusion score, alarm orkestrasyonu yok |
| M7 | Tasarım aşaması (header) | **Implement edildi:** SQLite (WAL mode), event logging, map save/load, JPEG snapshot |

---

## 10. Inter-Module Communication Değişiklikleri

Rapor Section 5'teki iletişim matrisine göre güncel durum:

| IF# | Rapordaki Çağrı | Güncel Durum |
|---|---|---|
| IF-01 | M5 → M2 `motor_drive/stop/turn` | **Değişti:** M5 artık `drive_distance_cm()`, `turn_left_90()`, `turn_right_90()`, `stop()` kullanıyor |
| IF-02 | M6 → M2 `set_alarm/blink_led` | **Yok:** M6 henüz implement edilmedi |
| IF-03 | M6 → M2 `get_battery_voltage` | **Yok:** M6 henüz implement edilmedi |
| IF-04 | M5 → M3 `get_ultrasonic_distances` | **Değişti:** `get_navigation_sensors()` ve `get_navigation_sensors_filtered()` kullanılıyor |
| IF-05 | M6 → M3 `get_fusion_sensors` | **Yok:** M6 henüz implement edilmedi |
| IF-06 | M6 → M4 `get_latest_result` | **Yok:** M6 henüz implement edilmedi |
| IF-07 | M6 → M4 `capture_snapshot` | **Yok:** M6 henüz implement edilmedi. M5 doğrudan `m4_vision.capture_frame()` çağırıyor |
| IF-08 | M6 → M5 `execute_command` | **Değişti:** M5 artık komut beklemiyor, `run()` ile direkt çalışıyor |
| IF-09 | M6 → M5 `get_nav_status` | **Yok:** M6 henüz implement edilmedi |
| IF-10 | M5 → M7 `save_map/load_map` | **Kullanılmıyor:** Statik harita nedeniyle M5 harita kaydetmiyor |
| IF-11 | M6 → M7 `log_event` | **Yok:** M6 henüz implement edilmedi |
| IF-12 | M6 → M7 `save_snapshot` | **Yok:** M6 henüz implement edilmedi |
| Yeni | M5 → M4 `determine_turn_direction()` | **Eklendi:** Engel kaçınma yön kararı için |
| Yeni | M5 → M2 `get/set_total_distance_cm()` | **Eklendi:** Encoder bazlı odometri |

---

## 11. Rapor Yazarları İçin Önemli Notlar

Yeni bir rapor yazılırken şu değişiklikler dikkate alınmalıdır:

1. **Navigasyon:** Wall-following ve occupancy grid açıklamaları tamamen çıkarılmalı, yerine waypoint-driven sector traversal anlatılmalıdır.
2. **Keşif aşaması:** EXPLORE state'i yok. Robot doğrudan önceden tanımlı rotada hareket ediyor.
3. **EXPLORE/PATROL geçişi:** Yok. Statik rota nedeniyle bu state'lere gerek yok.
4. **Fusion score formülü:** `smoke_level / 1023` yerine `smoke_level / 4095` kullanılmalıdır (12-bit ADC).
5. **Encoder:** Dead-reckoning yerine tekerlek enkoderi birincil konum kaynağı olarak anlatılmalıdır.
6. **3 ultrasonik sensör:** 2 değil, 3 sensör (sol, ön, sağ) kullanılıyor.
7. **MCP3208:** MCP3008 yerine MCP3208 (12-bit) kullanılıyor.
8. **Batarya eşikleri:** `LOW=6.8V`, `CRIT=6.4V` (raporda `7.0V` ve `6.6V` yazıyordu).
9. **IR eşik:** `60°C` (raporda `55°C` yazıyordu).
10. **Başlangıç doğrulama:** Robot harekete başlamadan önce sol/sağ duvar mesafeleri kontrol ediliyor.
11. **Mock mode:** Raporun "Runtime Model" kısmında mock moddan bahsedilmeli. Geliştirme makinelerinde RPi olmadan test yapılıyor.
12. **Veri dizini:** Sabit `/data/` yerine `SEEFIRE_DATA_DIR` ortam değişkeni veya repo-içi `runtime_data/`.

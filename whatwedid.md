# SeeFire Projesi - Geliştirme Günlüğü (What We Did)

Bu dosya, projede yapılan geliştirme adımlarını, alınan kararları ve tarihsel ilerlemeyi kayıt altında tutmak amacıyla oluşturulmuştur.

---

## Tarih: 5 Mayıs 2026
**Geliştirici:** Bekir Emre Sarıpınar & GitHub Copilot

### Yapılan İşlemler:

**1. Proje Analizi ve Hedef Belirleme**
- `docs/` klasöründeki proje dokümanları (`SeeFire_Interface_report.md` ve PDF formatlı güncel raporlar) incelendi.
- Bekir Emre Sarıpınar'ın sorumluluğundaki modüllerin sınırları çizildi: **M2 (Motor Control & Power)** ve **M3 (Sensor Integration)**.

**2. Batarya Konfigürasyonu Güncellemesi (`config.py`)**
- Batarya tipinin 3S LiPo'dan, **2S 18650 Li-ion** (Maksimum 8.4V, Nominal 7.4V) hücreye geçirildiği bilgisi işlendi. 
- Gerçek voltaj okuması yapabilmek için gerekli "Voltaj Bölücü" (Voltage Divider) direnç değerleri (`VDIV_R1 = 20000.0`, `VDIV_R2 = 10000.0`) ve tehlike limitleri (`BATTERY_CRIT_V = 6.4V`) `config.py` içerisine eklendi.

**3. M2 ve M3 Modülleri İçin "Sanal Geliştirme (MOCK)" Altyapısının Kurulması**
- Fiziksel robot şasisi henüz elimizde olmadığı için kodların hatasız devam edebilmesi adına **MOCK_MODE** oluşturuldu. Mac/PC ortamında Raspberry Pi pinleri olmadan sistem simüle edildi.
- **`m2_motor/motor.py`:** Motor hız limitleri (0-100), yön fonksiyonları (`motor_drive`, `motor_turn`), `set_alarm` ve `get_battery_voltage` fonksiyonlarının sanal çıktıları/matematiği yazıldı ve ana log yapısına bağlandı.
- **`m3_sensors/sensors.py`:** Analog, I2C ve GPIO üzerinden okunan sensörler (HC-SR04, MQ-2, MLX) MOCK moda entegre edildi. Navigasyon (M5) modülü için rastgele/sanal engel mesafesi üreten bir iskelet kuruldu. `read_battery_adc()` çağrısı aktifleştirilip M2'ye entegre edildi.

**4. Modüller Arası Entegrasyon Testi**
- `test_mocks.py` dosyası ile sistem test edildi.
- M2'nin doğru matematik formülüyle, M3 modülü içerisindeki sanal ADC kanalından veriyi alıp `7.4V` okuyabildiği, sensörlerin sahte "16.8cm, 26.2cm" uzaklıklar döndürdüğü ve takımın diğer üyeleri (özellikle Navigation ve FSM ekipleri) için altyapının %100 hazır olduğu görüldü.

**5. Donanım ve Tasarım Değişiklikleri (Ahmet Furkan Tarafından Tamamlananlar)**
Bu bölümde, proje dokümantasyonu ile fiziksel gerçeklik arasındaki uyuşmazlıkları gidermek amacıyla belirtilen *kesinleşmiş* donanım değişiklikleri listelenmiştir:

* **SBC (Ana Kart):** Raspberry Pi 5 8GB'den vazgeçilip, **Raspberry Pi 4 4GB** kullanılmasına karar verildi.
* **Ultrasonik Sensör (HC-SR04):** Sensör sayısı 2'den **3'e çıkarıldı** (Ön, Sağ, Sol). Her bir Echo pini için 1kΩ + 2kΩ voltaj bölücü dirençleri eklendi. (Pin ataması `config.py` içine dahil edildi).
* **Güç Kaynağı:** 3S hazır LiPo yerine, **2S 18650 Li-ion Pack (2600 mAh, BMS'li)** hazırlandı ve XT60 Pigtail ile bağlantısı tamamlandı.
* **Kaldırılan Sensörler:** MPU6050 (IMU) ve DHT22 sensörleri stabilite ve proje kapsamına uygun olmaması sebebiyle tasarımdan tamamen **çıkartıldı**.
* **Eklenen Diğer Donanımlar:**
  - Aktif Soğutucu (Heatsink + Fan - YOLO yükü için).
  - USB-C Kablo (Buck converter'dan Pi'yi 5V beslemek için).
  - 8.4V Şarj Adaptörü ve Rocker Switch.

*(Not: Rapor PDF'leri, Appendix A GPIO Pin listesi, Malzeme Tablosu, Malzeme Riskleri ve config sabit limitleri de bu yeni güncellemeler doğrultusunda güncellenmiştir.)*

---

## Tarih: 5 Mayıs 2026 — Navigation Mimarisi Yenilemesi
**Geliştirici:** Alperen & Claude

### Karar
`navigation_modulu.md` dokümanı projeye benimsendi. M5 navigation, **wall-following + occupancy grid** yaklaşımından **waypoint-driven south→north sektör traversali** modeline geçirildi. Encoder birincil konum kaynağı; HC-SR04 yan sensörler yalnızca başlangıç doğrulaması ve engel sonrası lateral fine-tune için kullanılıyor. Engelde dönüş yönü kameradan piksel oranlamasıyla belirleniyor (yedek: ultrasonic). Arduino kullanılmıyor — tüm I/O Raspberry Pi GPIO üzerinden, encoder pulse'ları GPIO interrupt ile sayılıyor. Kod dili tamamen İngilizce.

### Dosya Bazında Değişiklikler

**`config.py`**
- Kaldırıldı: `OBSTACLE_DIST_CM`, `WALL_FOLLOW_DIST_CM`, `GRID_RESOLUTION_M` (eski navigasyon modeline ait).
- `TRIG_CENTER/ECHO_CENTER` → `TRIG_FRONT/ECHO_FRONT` olarak yeniden adlandırıldı (anlamsal netlik).
- Eklendi: `ENCODER_LEFT_PIN=6`, `ENCODER_RIGHT_PIN=21`, `ENCODER_TICKS_PER_CM`.
- Eklendi: `WAYPOINTS = [(100,1),(200,2),(300,3)]`, `STEP_DISTANCE_CM`, `SIDE_STEP_CM`.
- Eklendi: `OBSTACLE_THRESHOLD_CM`, `OBSTACLE_CLEAR_CM`.
- Eklendi: `START_LEFT_CM`, `START_RIGHT_CM`, `POSITION_TOLERANCE_CM`, `FINE_TUNE_STEP_CM`.
- Eklendi: `DRIVE_SPEED`, `TURN_SPEED`, `MOCK_CM_PER_SEC`, `MOCK_TURN_90_SECONDS` (mock-mode time-based fallback).
- `validate_gpio_pins()` yeni pin isimlerini kapsayacak şekilde güncellendi.

**`m2_motor/motor.py`**
- Encoder pulse-counting: `_on_left_tick` / `_on_right_tick` rising-edge interrupt callback'leri.
- Yeni distance-based API: `drive_distance_cm(cm)`, `turn_left_90()`, `turn_right_90()`, `stop()`, `total_distance_cm` property, `set_total_distance_cm(value)`.
- Mock modda encoder yerine elapsed-time × `MOCK_CM_PER_SEC` ile mesafe simülasyonu.
- Eski API (`motor_drive`, `motor_turn`, `motor_stop`, `set_alarm`, `get_battery_voltage`) M6 uyumluluğu için olduğu gibi korundu.

**`m2_motor/__init__.py`**
- Yeni public sembolleri (`drive_distance_cm`, `turn_*_90`, `stop`, `get_total_distance_cm`, `set_total_distance_cm`) re-export ediyor.

**`m3_sensors/sensors.py`**
- `init_sensors`'a 3. ultrasonik (front) GPIO setup eklendi.
- `NavData` artık `front_cm` alanını içeriyor (M5 engel tespiti için).
- `get_navigation_sensors_filtered(samples=3)`: 3 okumanın per-eksen medyanı — gürültü ve yansıma artefaktlarına karşı.

**`m4_vision/vision.py`** (placeholder yerine gerçek kod)
- `VisionM4.init()` (camera open + warmup), `capture_frame()`, `close()`.
- `determine_turn_direction(frame=None) -> "LEFT"|"RIGHT"|None`: Canny + lower-half ROI + soldan/sağdan boş piksel sayımı. OpenCV yoksa `None` döner (caller ultrasonic'e düşer).

**`m4_vision/__init__.py`**
- Yeni fonksiyonları re-export ediyor.

**`m5_navigation/`** (placeholder'dan tam implementasyon)
- `navigation.py`: `NavigationController` — `start()` (start position verify), `run(waypoints=None)` (sektör döngüsü). `_check_midpoint` engel kaçınmaya callback olarak veriliyor → midpoint snapshot bypass sırasında bile asla atlanmıyor.
- `obstacle.py`: `ObstacleAvoidance.avoid(sector_id)` — kamera/ultrasonic karar, 90° dönüş, sol-sensör gözetiminde yan-geçiş, encoder tabanlı geri dönüş, lateral fine-tune. Bypass öncesi north-distance snapshot alınıp sonra geri yazılıyor (yan hareketler kuzey-ilerleyişi olarak sayılmasın diye).
- `position.py`: `PositionVerifier` — `verify_start()` (RuntimeError raise), `verify_and_correct()` (FINE_TUNE_STEP_CM yan adım).
- `__init__.py`: üç sınıfı public yapıyor.

**`CLAUDE.md`**
- Module Overview tablosunda M2/M3/M4/M5 satırları yeni sorumlulukları yansıtacak şekilde güncellendi.
- Critical Hardware Constraints: MPU6050 drift maddesi (artık IMU yok) → encoder slip + lateral fine-tune ile değiştirildi.

### Doğrulama
- Tüm modüller mock modda hatasız import oluyor.
- End-to-end mock dry-run: 2-waypoint rotada 4 snapshot (2 midpoint + 2 waypoint) tetiklendi, 40 cm encoder okuması alındı.
- Engel-yolu mock dry-run: front sensör threshold'u zorlandığında `RIGHT` yönüne bypass, 10 cm yan-geçiş sonrası clear, lateral fine-tune çalıştı.

### Eski Mimariden Geri Kalan İş
- `ENCODER_TICKS_PER_CM` ve `MOCK_CM_PER_SEC` fiziksel robotla kalibre edilmeli.
- M6 decision engine henüz implement edilmedi — FSM döngüsü, fusion score hesaplama ve alarm orkestrasyonu bekliyor.
- M4 YOLOv8n inference pipeline henüz entegre edilmedi — sadece kamera ve engel yön ipucu mevcut.
- M5 ve M6 `main.py`'ye henüz bağlanmadı.

---

## Tarih: 5 Mayıs 2026 — Kod Tutarsızlık Düzeltmeleri
**Geliştirici:** Bekir Emre Sarıpınar

### Yapılan Düzeltmeler

**Kritik Hata Düzeltmeleri:**
- `m3_sensors/sensors.py`: `NavData` alanı `center_cm` yerine **`front_cm`** olarak yeniden adlandırıldı. Eski test/doküman uyumluluğu için `center_cm` property'si backward-compat alias olarak eklendi.
- `m3_sensors/sensors.py`: `init_sensors()` içindeki `config.TRIG_CENTER` / `config.ECHO_CENTER` referansları **`config.TRIG_FRONT` / `config.ECHO_FRONT`** olarak düzeltildi (önceden RPi'de `AttributeError` veriyordu).

**Engel Kaçınma İyileştirmesi:**
- `m5_navigation/obstacle.py`: `_side_pass()` fonksiyonuna **`direction` parametresi** eklendi. Engel yönlü sensör dinamik olarak seçiliyor (`RIGHT` bypass → `left_cm`, `LEFT` bypass → `right_cm`). Önceden sadece sol sensör sabit olarak kullanılıyordu.
- `m5_navigation/obstacle.py`: Docstring güncellendi — artık "obstacle-facing side sensor" ifadesi kullanılıyor.

**Test Düzeltmeleri:**
- `m2_motor/tests/test_motor.py`: Testler `MOCK_MODE` kontrolü ile yeniden yazıldı. `RPi.GPIO` olmadan da anlamlı çalışıyor. Batarya testlerinde mock_voltage doğrudan set ediliyor.
- `m3_sensors/tests/test_sensors.py`: Aynı şekilde `MOCK_MODE` kontrolü eklendi. `_read_mcp3208` doğru metod adı ile mock'lanıyor. `front_cm` ve `center_cm` alias testi eklendi.

**main.py Güncellemesi:**
- M4 vision `init()` çağrısı eklendi. Başlatma sırası artık: `M7 → M2 → M3 → M4`.

**Config:**
- `DATA_DIR` varsayılanı `/data` yerine repo-içi `runtime_data/` olarak değiştirildi (`SEEFIRE_DATA_DIR` ortam değişkeni ile override edilebilir). Mock modda yazılabilir dizin garantisi.

**Dokümantasyon:**
- `CLAUDE.md` tamamen yeniden yazıldı ve repo için **current architecture note** görevi görüyor. Modül durumları, runtime gerçeği, sensor/motion model, mock mode ve source-of-truth önceliği tanımlanıyor.
- `navigation_modulu.md` eski Arduino / wall-following / occupancy-grid taslağından arındırılıp mevcut Raspberry Pi tabanlı sector-traverse mantığına göre güncellendi.
- `docs/nelerdegisti.md` rapor ile mevcut kod arasındaki tüm farkları kapsayacak şekilde yeniden yazıldı.

**Header Dosyaları:**
- `m2_motor.h`: 2S batarya değerleri (8.4V/6.8V/6.4V), encoder pin'leri (6, 21), mesafe bazlı API fonksiyonları eklendi. 3S referanslar kaldırıldı.
- `m3_sensors.h`: 3 sensör (`TRIG/ECHO_FRONT` eklendi), `M3_ADC_MAX=4095`, `M3_ULTRASONIC_COUNT=3`, `m3_nav_data_t` artık `front_cm` içeriyor, `m3_get_navigation_sensors_filtered` eklendi.
- `m4_vision.h`: YOLO pipeline referansları kaldırıldı. Sadece `init/close/capture_frame/determine_turn_direction`. `m4_turn_hint_t` enum eklendi.
- `m5_navigation.h`: Wall-following ve occupancy grid tamamen kaldırıldı. Waypoint/sector traversal API (`m5_run_navigation`, `m5_handle_obstacle`, `m5_verify_start_position`).
- `m6_decision.h`: EXPLORE/PATROL yerine `M6_STATE_NAVIGATE`. `M6_BATTERY_LOW_V=6.8` config.py ile uyumlu. Placeholder notu eklendi.
- `m7_logging.h`: `m7_event_t` Python dataclass ile uyumlu hale getirildi. `m7_save_snapshot` signature güncellendi.

**README Dosyaları:**
- Tüm modül README'leri (`m2_motor`, `m3_sensors`, `m4_vision`, `m5_navigation`, `m6_decision`, `m7_logging`) sadeleştirildi — eski C-style örnekler kaldırıldı, güncel Python API'yi yansıtıyor.

**`m2_motor/__init__.py`:**
- `set_total_distance_cm` fonksiyonu `__all__` listesine eklendi.

### Doğrulama
- `python3 -m pytest m2_motor/tests/test_motor.py m3_sensors/tests/test_sensors.py -v` → **6/6 PASSED**
- Tüm modüller mock modda hatasız import ediliyor.
- `test_mocks.py` güncel `front_cm` alanını doğru yazdırıyor.

### Source of Truth Sırası

Tutarsızlık durumunda şu sıralama geçerli kabul edilmelidir:
1. Python implementasyonu
2. `config.py`
3. `CLAUDE.md`
4. `docs/nelerdegisti.md`
5. tarihsel raporlar ve eski roadmap belgeleri

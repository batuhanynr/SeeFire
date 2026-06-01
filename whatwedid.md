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

---

## Tarih: 28 Mayıs 2026 — M5 Engel Kaçınma Algoritması Yenileme Tasarımı
**Geliştirici:** Alperen & Claude

### Karar
Mevcut `obstacle.py` engel-bitti kontrolünü sabit `OBSTACLE_CLEAR_CM = 40` eşiği ile yapıyor. Bu eşik dinamik bir referansla değiştirilecek: engeli ilk gördüğümüzdeki front mesafesi `D₀` saklanır; clearance-side sensör `D₀ + 15 cm`'i aşınca engel bitmiş sayılır. Ayrıca yan-geçişte robot 90° döndüğü için yeni "ileri" sensör artık `front` (eski yön düzeltildi: önceden hatalı şekilde `right_cm` duvar kontrolü için kullanılıyordu sanılıyordu — gerçekte hiçbir yerde yapılmıyordu, eklenecek). Sıkıştığımızda (front < `WALL_CLEARANCE_CM = 10`) bir kez geri dönüp ters yönden bypass denenir; iki yön de tıkalıysa abort + alarm.

### Plan Dosyası
Tam tasarım, sensör yönelimi tabloları, algoritma akışı, dosya bazında değişiklikler ve simülatör yol haritası `m5_navigation/OBSTACLE_PLAN.md` dosyasında. İlerleme bu dosyada takip edilecek.

### Sırada (henüz implement edilmedi)
1. `config.py`: `OBSTACLE_CLEARANCE_DELTA_CM = 15.0`, `WALL_CLEARANCE_CM = 10.0`, `SIDE_PASS_SAFETY_CAP_CM = 200.0` eklenecek; `OBSTACLE_CLEAR_CM` silinecek.
2. `m5_navigation/obstacle.py`: `avoid()` `reference_distance` parametresi alacak, `_side_pass` clearance/wall/cap üçlü çıkışla yeniden yazılacak, `_retreat_and_retry` helper'ı eklenecek (max 1 retry).
3. `m5_navigation/navigation.py`: engel görüldüğünde `front_cm` `avoid()`'a geçirilecek.
4. Testler güncellenecek; yeni senaryolar: duvar dibinde engel (retreat), iki yön tıkalı (abort).
5. Simülatör altyapısı (`m5_navigation/sim/`): `world.py` (ray-cast geometri), `mock_drivers.py` (m2/m3 mock'larını world'e bağla), `visualizer.py` (matplotlib animasyon). Algoritmanın görsel doğrulaması için.

### Açık Sorular
- Abort sonrası M6 davranışı (entegrasyon yapıldığında belirlenecek).
- `D₀` için `get_navigation_sensors_filtered`'ın front-median değeri kullanılacak (tek okuma değil).

---

## Tarih: 28 Mayıs 2026 — M5 Engel Algoritması Implementasyonu (Adım 2-6)
**Geliştirici:** Alperen & Claude

### Yapılan
**`config.py`:** `OBSTACLE_CLEAR_CM` (sabit 40 cm eşik) kaldırıldı. Yerine eklenenler:
- `OBSTACLE_CLEARANCE_DELTA_CM = 15.0` — clearance-side sensör `D₀ + delta`'yı aşınca engel bitti sayılır.
- `WALL_CLEARANCE_CM = 10.0` — yan-geçişte front sensörü bu eşiğin altına inerse perpendicular duvara dayandık demektir.
- `SIDE_PASS_SAFETY_CAP_CM = 200.0` — önceden obstacle.py içinde hardcoded olan 200 cm safety cap, config'e taşındı.

**`m5_navigation/obstacle.py`:** Tamamen yeniden yazıldı.
- `avoid(sector_id, reference_distance)` — caller engel anındaki `front_cm`'i (`D₀`) iletir.
- `_side_pass` → `(traveled, wall_hit)` tuple döner. Üç çıkış: clearance, wall hit, safety cap.
- Clearance kontrolü artık dinamik: `clearance > D₀ + OBSTACLE_CLEARANCE_DELTA_CM`.
- Wall kontrolü **front sensörü** kullanıyor (90° dönüş sonrası front = yeni ileri).
- `_attempt_bypass` helper: dönüş + side-pass + (wall hit ise) retreat + dönüşü geri al. Robotu başlangıç noktasına ve kuzey oryantasyonuna geri getirir.
- Retry mantığı: ilk yön duvara takılırsa ters yönden 1 kez denenir. İkisi de tıkalıysa `ObstacleBlockedError` raise edilir.
- `_return_to_route` mevcut encoder-only dönüş mantığı helper'a ayrıldı.

**`m5_navigation/navigation.py`:** Tek satır değişikliği — `self._obstacle.avoid(sector_id, reference_distance=front)`.

**`m5_navigation/tests/test_navigation.py`:** Mevcut testler yeni imzaya uyarlandı. Üç yeni test:
- `test_avoidance_retries_on_wall_hit` — ilk yön wall, ters yön clear → 2. attempt LEFT'ten yapılır.
- `test_avoidance_aborts_when_both_sides_blocked` — iki yön de wall → `ObstacleBlockedError`.
- `test_side_pass_clears_at_dynamic_threshold` — `D₀ + 15` eşiğinin sabit 40 yerine kullanıldığını doğrular.
- `test_side_pass_detects_wall_via_front_sensor` — wall detection front'tan, rear sensörden değil.

### Doğrulama
- `python3 -m pytest m5_navigation/tests/test_navigation.py -v` → **8/8 PASSED**.
- `python3 -m pytest m2_motor/tests m3_sensors/tests` → **8/8 PASSED** (regresyon yok).

### Sırada
`OBSTACLE_PLAN.md` §7 durum tablosu güncellendi. Adım 7-9 (simülatör altyapısı) bekliyor: `m5_navigation/sim/world.py`, `mock_drivers.py`, `visualizer.py` ve senaryo dosyaları.

---

## Tarih: 30 Mayıs 2026 — M5 Simülatör + Forward-Pass Düzeltmesi
**Geliştirici:** Alperen & Claude

### Yapılan
**Simülatör altyapısı (`m5_navigation/sim/`):**
- `world.py` — 2D top-down dünya: dikdörtgen sınırlar, `Obstacle` rectangle listesi, robot pose (x, y, heading). Ray-segment intersection ile sensör okumaları geometriden türetiliyor. Motor komutları (drive/turn/stop) world'e bağlı; her komut sonrası `Frame` kaydediliyor.
- `mock_drivers.py` — m2_motor / m3_sensors / m4_vision modül-seviye fonksiyonlarını world'e patch'liyor. NavigationController değişiklik olmadan üstte çalışıyor.
- `visualizer.py` — matplotlib `FuncAnimation`. Harita sınırları, engeller, robot çemberi + yön oku, sensör ışınları (3), trajectory. `.gif` save ya da interaktif pencere.
- `demo.py` — 3 senaryo (`single`, `wall`, `blocked`) ve CLI: `python3 -m m5_navigation.sim.demo single --save out.gif`.

**Forward-pass faz eklendi (`obstacle.py`):**
Simülatör ilk koşuda algoritma bug'u yakaladı: yan-geçiş → kuzeye dön → route'a geri akışı engelin **kuzey kenarını geçmediği** için her tur aynı engele takılıp sonsuz döngüye giriyordu. Eski kodda da olan, testlerin `_side_pass`'ı mock'lamasıyla gizlenmiş bir bug'tı.

Eklenen faz (`_forward_pass_obstacle`): yan-geçiş clear olduktan ve kuzeye döndükten sonra, robot kuzeye step-step ilerliyor. İki-aşamalı state machine:
- **ACQUIRE**: yan sensör engeli yakın görene kadar (henüz altındayız) sür.
- **RELEASE**: yan sensör tekrar uzak görene kadar (engelin kuzey kenarını geçtik) sür.

Bu mesafe gerçek kuzey ilerlemesi → `total_distance_cm` korunuyor (lateral hareketler hâlâ sıfırlanıyor). `config.FORWARD_PASS_SAFETY_CAP_CM = 100.0` cap eklendi. Yeni unit test `test_forward_pass_clears_when_side_sensor_passes_obstacle` ekledi.

**Bypass akış güncellemesi (`avoid()`):**
- `_attempt_bypass` artık `(side_distance, forward_distance)` döndürüyor (önceden sadece side).
- `_return_to_route` basitleşti: forward-pass sonrası robot zaten kuzey bakıyor; tek dönüş + sürüş + dönüş.
- `set_total_distance_cm(north_before + forward_distance)` — forward-pass gerçek ilerleme olarak sayılıyor.

### Doğrulama
- `python3 -m pytest m5_navigation/tests/test_navigation.py -v` → **9/9 PASSED**.
- Simülatör 3 senaryosunun hepsi başarılı:
  - **single**: (30,0) → (30,150). 44 frame. Temiz bypass.
  - **wall**: RIGHT engellendi, LEFT retry başardı → (30,150). 55 frame.
  - **blocked**: iki yön de engelli, `ObstacleBlockedError` raise edildi. Robot (30,50)'de güvenle durdu.
- GIF'ler `runtime_data/sim_*.gif` altında kaydedildi (her biri 600-750 KB).

### Kullanım
```bash
python3 -m m5_navigation.sim.demo single                          # interaktif pencere
python3 -m m5_navigation.sim.demo wall --save run.gif             # gif kaydet
python3 -m m5_navigation.sim.demo blocked --interval 150          # frame hızı
```

### Sırada
M6 Decision Engine entegrasyonu — `ObstacleBlockedError` artık navigation'dan dışarı çıkıyor; M6 FSM bunu alarm/abort event'i olarak ele almalı. Sim'e yeni senaryolar kolayca eklenebilir (birden fazla engel, ardışık engeller).

---

## Tarih: 30 Mayıs 2026 — 4-Yön Tarama + Saf Kuzey Encoder Modeli
**Geliştirici:** Alperen & Claude

### Karar
Her sektörün **tam ortasında** robot durup 4 yöne (N/E/S/W) kamera taraması yapacak — yangın/duman tespiti için alan kapsama. Tetikleme noktası **y-koordinatı** (kuzey ilerlemesi) midpoint'e geldiği an; rota üzerinde mi yoksa engel bypass'i sırasında forward-pass içinde mi olduğu farketmez. Sektör sonunda (waypoint) sadece tek frame snapshot — 4-yön tarama orada yapılmaz (kullanıcı seçimi B).

Bunun için **encoder modeli** değişti: `m2_motor.get_total_distance_cm()` artık "toplam kat edilen mesafe" değil **saf kuzey ilerlemesi**. Lateral hareketler `_drive_lateral` sarmalı ile per-step save/restore yaparak encoder'ı kirletmiyor.

### Yapılan
**`m5_navigation/obstacle.py`:**
- Yeni `_drive_lateral(cm)` static method — `drive_distance_cm` çağrısını encoder save/restore ile sarmalıyor. Side-pass, return-to-route, retreat-from-wall'da kullanılıyor.
- `_side_pass` lateral step → `_drive_lateral`.
- `_return_to_route` lateral drive → `_drive_lateral`.
- `_retreat_from_wall` lateral drive → `_drive_lateral`.
- `avoid()` sonundaki `set_total_distance_cm(north_before + forward_distance)` satırı **kaldırıldı**. Lateral rollback sayesinde encoder zaten doğru.
- Modül docstring'i yeni modeli açıklayacak şekilde güncellendi.

**`m5_navigation/navigation.py`:**
- Yeni `_scan_four_directions(label_prefix)` method:
  1. `m2_motor.stop()` + 0.3 s.
  2. Sırasıyla N→E→S→W: `snapshot_callback("...-N/E/S/W")` + 0.2 s + `turn_right_90()` + 0.1 s.
  3. Net rotasyon 360° → robot başlangıç yönünde (kuzey) kalır.
- `_check_midpoint` artık `_snapshot` yerine `_scan_four_directions` çağırıyor.
- `_snapshot` (tek frame) waypoint'lerde kullanılmaya devam ediyor.

**`m5_navigation/tests/test_navigation.py`:**
- `test_drive_lateral_preserves_north_progress` — lateral drive encoder'ı kirletmiyor.
- `test_four_direction_scan_captures_each_heading` — 4 snapshot doğru label, 4 right-turn.
- `test_avoidance_maneuver_flow` set_total_distance assertion kaldırıldı (artık `avoid()` o satırı çağırmıyor).

### Doğrulama
- `python3 -m pytest m5_navigation/tests/test_navigation.py -v` → **11/11 PASSED**.
- Simülatör `single` senaryosu log'u:
  ```
  [OBSTACLE] D0=20.0 cm. Bypass direction: LEFT
  [OBSTACLE] Side-pass cleared after 15.0 cm (right_cm=170.0 > 35.0).
  [OBSTACLE] Forward-pass acquired obstacle at 20.0 cm (right_cm=5.0).
  [SCAN] sector-1-midpoint-N
  [SCAN] sector-1-midpoint-E
  [SCAN] sector-1-midpoint-S
  [SCAN] sector-1-midpoint-W
  [OBSTACLE] Forward-pass released after 40.0 cm (right_cm=45.0 > 35.0).
  [WAYPOINT] Sector 1 end.
  ```
  Tarama bypass forward-pass içinde, y=75 (sektör midpoint) noktasında tetiklendi. Robot kuzeye bakıyordu, 4 yönü taradı, kaldığı yerden devam etti.
- Tüm 3 sim senaryosunun GIF'i yenilendi (`runtime_data/sim_*.gif`).

### Sırada
- M6 Decision Engine'in `[SCAN]` event'lerini fire/smoke fusion için işlemesi (M4 inference pipeline tamamlandığında).
- M7 logging tarafına 4-yön snapshot'larının ayrı event'ler olarak yazılması (label zaten ayrımı içeriyor).

---

## Tarih: 30 Mayıs 2026 — Sensör Gürültü Filtresi + Sütun-Uyumlu Konum Düzeltme
**Geliştirici:** Alperen & Claude

### Karar
Üç ilişkili iyileştirme birlikte yapıldı:
1. **D₀ ölçümü gürültüden korunsun** — engel tespit anında front değeri tek okuma yerine 3-okuma median'ından alınsın (`get_navigation_sensors_filtered`). Tek hatalı HC-SR04 reading'i (ör. yansıma yüzünden 3 cm okuma) artık bypass mesafelerini bozamaz.
2. **Periyodik konum düzeltme** — `PositionVerifier.verify_and_correct()` sadece bypass sonrası değil, **her waypoint'te de** çağrılır. Encoder slip ve dönüş açı hatası uzun rotalarda birikiyor; her sektör sonu bir düzeltme şansı.
3. **İki-sensör sanity gate (sütun-uyumlu)** — gerçek harita düzgün dikdörtgen değil; binanın taşıyıcı sütunları/dikitleri var. Bunların yanından geçerken tek sensör tabanlı düzeltme yanlış kalibrasyon yapar. Yeni mantık:
   ```
   expected_width = START_LEFT_CM + START_RIGHT_CM   # 60 cm
   measured = left + right
   if |measured - expected| > 2 × POSITION_TOLERANCE_CM:
       skip correction (sütun/anomali var)
   ```
   Sütun yanında robot encoder'a güveniyor; bir sonraki güvenli waypoint'te düzeltme tekrar denenir.

### Yapılan
**`m5_navigation/navigation.py`:**
- `_traverse_sector`'da front okuması `get_navigation_sensors()` → `get_navigation_sensors_filtered()`.
- Waypoint snapshot'tan sonra `self._position.verify_and_correct()` çağrısı eklendi.

**`m5_navigation/position.py`:**
- `verify_and_correct` baş kısmına iki-sensör genişlik kontrolü eklendi. Tolerans `2 × POSITION_TOLERANCE_CM = 10 cm`.
- Width mismatch durumunda INFO log'u + erken return.

**`m5_navigation/tests/test_navigation.py`:**
- `test_verify_and_correct_skips_when_corridor_width_mismatches` — sol+sağ ≠ 60 olunca düzeltme yapılmıyor.
- `test_verify_and_correct_applies_when_width_consistent` — genişlik tutuyorsa ve left_err > tolerans ise düzeltme uygulanıyor.

### Doğrulama
- `python3 -m pytest m5_navigation/tests/test_navigation.py -v` → **13/13 PASSED**.
- Sim multi senaryosu: 3 sektör tamamlandı, scan'ler düzgün tetiklendi. Geometri mükemmel olduğundan width check her zaman geçti ve left_err her zaman 0 olduğu için düzeltme aksiyonu fire etmedi — sim'de **beklenen davranış**. Gerçek robotta tekerlek slip oldukça etkin olacak.
- Sim'in mock geometrisi sütun simüle etmiyor; sütun-uyumlu davranış birim testleriyle doğrulandı.

### Notlar
- İleride spesifik sütun konumları config'e (örn. `COLUMN_WAYPOINTS = {2, 5}`) eklenebilir. Şu anki yaklaşım haritaya özel veri istemiyor, dinamik sensör kontrolü ile çalışıyor.
- M5 algoritmik olarak **kapanmaya** yakın. Kalan iş ağırlıklı olarak M6/M7 entegrasyonu ve gerçek robotta kalibrasyon.

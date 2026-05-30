# M5 — Engel Kaçınma Algoritması Yenileme Planı

**Başlangıç:** 2026-05-28
**Sahibi:** Alperen
**Durum:** Tasarım onaylandı, implementasyon bekliyor.

Bu dosya başka bir konuşmaya geçildiğinde kaldığımız yeri korumak için. Tasarım kararlarını, kalan işleri ve simülasyon yol haritasını tutar. İlerleme oldukça hem buradaki "Durum" tablosu hem de `whatwedid.md` güncellenir.

---

## 1. Motivasyon

Mevcut `m5_navigation/obstacle.py` engel-bitti kararını sabit `OBSTACLE_CLEAR_CM = 40` eşiği ile veriyor. Bu:
- Engel 40 cm'den uzaktaysa daha en başında "temiz" sanıyor.
- Engel duvara çok yakınsa hiçbir zaman clear olmuyor.
- Side-pass sırasında duvara dayanma durumu algılanmıyor (`right_cm` kullanılıyor ama sağa döndükten sonra sağ sensör geriye bakıyor, anlamsız).

Yeni algoritma:
- Engeli ilk gördüğümüzdeki front mesafesini referans (`D₀`) olarak kullan.
- Engelin bittiği yer: clearance-side sensör > `D₀ + 15`.
- Duvar çarpışmasını **yeni "ileri" sensörü** (yan-geçiş sırasında front) ile algıla.
- Bir yönden geçemiyorsak geri dönüp ters yönü dene.

---

## 2. Sensör Yönelimi Tablosu

Kuzeye bakarken (başlangıç oryantasyonu):

| Sensör | Yön |
|---|---|
| `front` | kuzey |
| `left` | batı |
| `right` | doğu |

**Sağa 90° döndükten sonra (doğuya bakıyor — bypass east-ward):**

| Sensör | Fiziksel yön | Görevi |
|---|---|---|
| `front` | doğu | İleri duvar/engel — **duvar kontrolü** |
| `left` | kuzey | Solumuzdaki orijinal engel — **clearance kontrolü** ✓ |
| `right` | güney | Geride — kullanılmıyor |

**Sola 90° döndükten sonra (batıya bakıyor):**

| Sensör | Fiziksel yön | Görevi |
|---|---|---|
| `front` | batı | İleri duvar — duvar kontrolü |
| `right` | kuzey | Sağımızdaki orijinal engel — clearance kontrolü ✓ |
| `left` | güney | Kullanılmıyor |

---

## 3. Algoritma Akışı

```
1. Forward step döngüsü → front_cm ≤ OBSTACLE_THRESHOLD_CM
2. D₀ = front_cm kaydet
3. Yön kararı: kamera ipucu → ultrasonic fallback (left vs right karşılaştırması)
4. Seçilen yöne 90° dön
5. Side-pass döngüsü:
     while True:
         clearance = left_cm  if direction=="RIGHT" else right_cm
         wall      = front_cm
         if clearance > D₀ + OBSTACLE_CLEARANCE_DELTA_CM:
             cleared → break
         if wall < WALL_CLEARANCE_CM:
             stuck → retreat-and-retry
         if traveled > SIDE_PASS_SAFETY_CAP_CM:
             abort
         drive_distance_cm(SIDE_STEP_CM)
         traveled += SIDE_STEP_CM
         midpoint_callback(sector_id)   # snapshot fırsatı
6. Cleared akışı (mevcut mantık):
     - return_first_turn() x2 (geri dönüş yönüne dön)
     - drive_distance_cm(traveled)
     - return_first_turn (kuzeye geri dön)
     - PositionVerifier.verify_and_correct()
7. Retreat-and-retry akışı:
     - 180° dön
     - drive_distance_cm(traveled)        # başlangıç noktasına dön
     - 180° dön                            # tekrar kuzeye bak
     - direction = "LEFT" if "RIGHT" else "RIGHT"
     - 4. adımdan tekrar başla (yalnızca bir kez retry; ikinci tıkanma → abort + alarm)
8. Abort: m6_decision'a "passable yol yok" event'i; bypass'tan exception ya da
   status code ile çık. Şimdilik log + raise; M6 entegrasyonu sonra.
```

---

## 4. `config.py` Değişiklikleri

Eklenecek:
```python
OBSTACLE_CLEARANCE_DELTA_CM = 15.0    # left/right > D₀ + delta → engel bitti
WALL_CLEARANCE_CM           = 10.0    # front < bu → yan duvara dayandık
SIDE_PASS_SAFETY_CAP_CM     = 200.0   # mevcut hardcoded değer
```

Kaldırılacak / işlevi değişecek:
- `OBSTACLE_CLEAR_CM = 40.0` → artık dinamik (`D₀ + delta`). Sabit tamamen silinebilir.

---

## 5. Dosya Bazında Yapılacak Değişiklikler

- **`config.py`**: yukarıdaki üç sabit eklenir, `OBSTACLE_CLEAR_CM` silinir.
- **`m5_navigation/obstacle.py`**:
  - `avoid(sector_id, reference_distance)` — `D₀` parametresi alır.
  - `_side_pass` clearance + wall + cap üçlü çıkış koşuluyla yeniden yazılır.
  - Yeni `_retreat_and_retry` helper'ı.
  - Retry sayacı (max 1).
- **`m5_navigation/navigation.py`**:
  - `_traverse_sector` engeli görünce `front_cm`'i `avoid()`'a geçirir.
- **`m5_navigation/tests/`**:
  - Mevcut testler güncellenir.
  - Yeni senaryolar: "engel duvar dibinde, retreat tetikleniyor", "iki yön de tıkalı → abort".

---

## 6. Simülatör Yol Haritası

Algoritma yazıldıktan sonra dev makinesinde görsel test için:

```
m5_navigation/sim/
  __init__.py
  world.py            # 2D harita: dikdörtgen sınırlar + Obstacle listesi
  mock_drivers.py     # m2_motor ve m3_sensors mock'larını world geometrisine bağlar
                      # (ray-cast tabanlı sensör okuması)
  visualizer.py       # matplotlib animasyon: robot, yön oku, sensör ışınları,
                      # trajectory, engeller, harita sınırları
scenarios/
  scenario_single_obstacle.py
  scenario_wall_hugging_obstacle.py   # retreat tetikleyici
  scenario_blocked_both_sides.py      # abort tetikleyici
```

Senaryolar `NavigationController.run()`'u sim mock'ları altında çalıştırır, `.gif` veya interaktif pencere üretir.

---

## 7. Durum Tablosu

| Adım | Açıklama | Durum |
|---|---|---|
| 1 | Algoritma tasarımı (bu dosya) | ✅ 2026-05-28 |
| 2 | `config.py` yeni sabitler | ✅ 2026-05-28 |
| 3 | `obstacle.py` `_side_pass` yeniden yazımı | ✅ 2026-05-28 |
| 4 | `obstacle.py` retreat-and-retry | ✅ 2026-05-28 |
| 5 | `navigation.py` `D₀` aktarımı | ✅ 2026-05-28 |
| 6 | Test güncellemesi + yeni senaryolar | ✅ 2026-05-28 (9/9 PASS) |
| 7 | `sim/world.py` + `mock_drivers.py` | ✅ 2026-05-30 |
| 8 | `sim/visualizer.py` matplotlib | ✅ 2026-05-30 |
| 9 | Senaryo dosyaları (`sim/demo.py`) | ✅ 2026-05-30 |
| 10 | **Forward-pass faz eklendi** (acquire/release state machine) | ✅ 2026-05-30 |
| 11 | **4-yön tarama (N/E/S/W)** sektör midpoint'lerinde | ✅ 2026-05-30 |
| 12 | **Lateral rollback** — yan hareketler kuzey-encoder'ı kirletmiyor | ✅ 2026-05-30 |
| 13 | Filtered front okuma → `D₀` gürültüden korunuyor | ✅ 2026-05-30 |
| 14 | Periyodik konum düzeltme (her waypoint'te) | ✅ 2026-05-30 |
| 15 | İki-sensör sanity gate (sütun-uyumlu) | ✅ 2026-05-30 |

---

## 8. Açık Sorular / Sonraya Bıraktıklarımız

- **Retry sayısı:** şimdilik 1. İki yön de tıkalıysa abort. İleride çoklu engel rotasyonu için artırılabilir.
- **Abort sonrası davranış:** M6 decision engine bunu nasıl ele alacak? Şimdilik exception + log; M6 entegrasyonu yapıldığında event olarak iletilecek.
- **`D₀` ölçüm gürültüsü:** tek okuma yerine `get_navigation_sensors_filtered`'ın front değerini kullanmak daha güvenli (median).
- **Robot kare değil:** dönüş sonrası sol/sağ okuması front'tan ufak fark gösterebilir. Delta = 15 cm bu farkı zaten absorbe ediyor.

---

## 9. 4-Yön Tarama (Eklendi 2026-05-30)

### Amaç
Her sektörün **tam ortasında** robot durup 4 yöne kamera taraması yapar (yangın/duman tespiti için alan kapsama). Engel kaçınma rotasında olsa bile y-merkezde durulup taranır — sektörün ortasını coğrafi olarak ıskalamamak için.

### Tetikleme Kuralı
- Y-koordinatı (kuzey ilerlemesi) sektör midpoint'ine ulaştığı anda tetiklenir.
- Robot **mutlaka kuzeye bakar durumdadır**: lateral hareketler (side-pass, return-to-route) `_drive_lateral` ile encoder'ı kirletmediğinden, midpoint sadece kuzey sürüş sırasında geçilebilir.
- Forward-pass (bypass'in kuzey ilerleme fazı) içinde geçilirse robot off-route'ta (örn. x=15) durur ve tarar — bu OK, alan kapsama amacı korunur.

### Davranış
1. `m2_motor.stop()` + 0.3 s bekleme.
2. Sırasıyla N → E → S → W:
   - `snapshot_callback("sector-{id}-midpoint-{yön}")` çağrılır.
   - 0.2 s bekleme.
   - `turn_right_90()` → bir sonraki yöne dön.
   - 0.1 s bekleme.
3. Toplam 4 × 90° = 360° net rotasyon → robot orijinal yöne (kuzey) döner.
4. Çağıran (main loop ya da forward-pass) kaldığı yerden devam.

### Waypoint Davranışı
Sektör sonunda (waypoint) tek frame snapshot (`_snapshot`). 4-yön tarama yapılmaz — kullanıcı kararı (B).

### Encoder Modeli: Lateral Rollback
`obstacle.py._drive_lateral(cm)`:
```
before = m2_motor.get_total_distance_cm()
m2_motor.drive_distance_cm(cm)
m2_motor.set_total_distance_cm(before)
```
Side-pass, return-to-route ve retreat hareketleri bunu kullanır. Sonuç: `get_total_distance_cm()` her zaman saf kuzey ilerlemesi. Bypass sonunda ekstra düzeltme gerekmiyor (eski `set_total_distance_cm(north_before + forward_distance)` satırı kaldırıldı).

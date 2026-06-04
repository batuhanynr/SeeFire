# SeeFire — Akıllı İç Mekan Yangın Tespit Robotu

## CSE 396 — Otonom Robot Sistemleri Projesi

---

## Problem

Yangınlar erken tespit edilemediğinde:
- Can kaybı yaşanıyor
- Maddi hasar büyüyor
- Müdahale gecikiyor

**Gerekli:** Yangını ilk andan tespit eden, otonom çalışan, insan müdahalesi gerektirmeyen sistem

---

## Çözüm: SeeFire Robot

**Tam otonom iç mekan yangın tespiti ve bildirim sistemi**

Algıla → Tespit Et → Engellerden Kaçın → Logla → Bildir

---

## Donanım Mimarisisi

- **Beyin:** Raspberry Pi 4
- **Hareket:** 4WD chassis, L298N motor sürücü x2
- **Görü:** Kamera modülü
- **Algılama:** 5 sensör
  - MQ-2 (gaz/duman)
  - MLX90614 (sıcaklık)
  - HC-SR04 ultrasonik x3 (sol/ön/sağ)

---

## Yazılım: M1-M7 Modüler Mimari

7 modül, 21 test passing, tam entegrasyon

| Modül | Görev | Durum |
|-------|------|-------|
| M1 | Chassis & Mekanik | ✅ |
| M2 | Motor Kontrol | ✅ |
| M3 | Sensör Entegrasyonu | ✅ |
| M4 | Görüntü İşleme | ✅ |
| M5 | Navigasyon | ✅ |
| M6 | Karar Motoru | ✅ |
| M7 | Logging | ✅ |

---

## M2: Motor Kontrol

**Özellikler:**
- L298N x2 paralel GPIO kontrol
- Encoder tabanlı odometri (1.665 tick/cm)
- İvmeli kalkış (10-step ramp)
- Geri bildirimli sürüş
- Mock mode (test için)

**Sonuç:** Pürüzsüz, güvenilir hareket

---

## M3: Sensör Entegrasyonu

**5 sensör, median filtre, gürültü yok**

- MQ-2 → gaz/duman konsantrasyonu
- MLX90614 → yüzey sıcaklığı (SMBus)
- HC-SR04 x3 → 3 boyutlu mesafe algılama

**Güvenlik:** 3-sample median filtre, outlier rejection

---

## M4: Görüntü İşleme

**YOLOv8n ile Yangın/Duman Tespiti**

- Gerçek zamanlı kamera akışı
- YOLOv8n model inference
- Yangın & duman sınıflandırma
- Turn direction hint (engel bypass için)

**Sonuç:** Görsel algılama aktif

---

## M5: Navigasyon

**Waypoint sürüş + Akıllı Engel Geçme**

1. Normal sürüş: Waypoint takibi
2. Engel görürse: Dikdörtgen bypass
   - En geniş tarafa 90° dön
   - Yanal geçiş (engel temizlenene kadar)
   - Forward-pass (engel boyu kadar)
   - Return-to-route (rota hizalaması)

**Sonuç:** Asla çarpmaz, her zaman ilerler

---

## M6: Karar Motoru

**5-State FSM ile Otonom Karar**

```
INIT → NAVIGATE → VERIFY → ALARM → STOP
```

- **NAVIGATE:** Normal sürüş
- **VERIFY:** Yangın teyidi (fusion score)
- **ALARM:** M7 log + trigger
- **STOP:** Güvenli duruş

**Güvenlik:** Battery monitoring, timeout koruması

---

## M7: Logging & Çıktı

**Her şeyi kayıt altına al**

- SQLite database (WAL mode, thread-safe)
- Event logging
- JPEG snapshot (event_id_timestamp.jpg)
- JSON map save/load (atomic write)
- Güvenlik: Race-condition yok

---

## Kamera-Free Mod: nav_no_cam.py

**Ultrasonik sadece engel geçme**

Kamera yokken de çalışır:

1. 15sn ilerle → dur
2. Sağa 90° bak (2sn)
3. 180° sola bak (2sn)
4. Kuzeye dön → devam

**Engel görene kadar sür**

---

## Akıllı Engel Geçme (nav_no_cam.py)

**3-layer öncelik sistemi:**

| Öncelik | Durum | Aksiyon |
|--------|-------|---------|
| 1 | Ön < 60cm | Dur → geniş tarafa 90° → ileri |
| 2 | Yan < 20cm | 8° mikro düzeltme |
| 3 | Ön 600+cm | Çaprazlık kontrolü |
| 4 | 15sn geçti | Sağ/sol tarama |

**Sonuç:** Asla duvara çarpmaz

---

## Demo Videosu

**[Buraya video embed veya screenshot eklenecek]**

Robot çalışırken:
- Engel tespiti
- 90° dönüş
- Bypass manevrası
- Rotalama

---

## Test Sonuçları

- ✅ 21 unit test passing
- ✅ Encoder kalibrasyonu (1.665 tick/cm)
- ✅ Tank turn 90° (0.80 sn)
- ✅ Median filtre stabilliği
- ✅ FSM state transition
- ✅ SQLite thread-safety
- ✅ Bypass manevrası (Pi fiziksel test)

---

## Teknik Özet

| Kategori | Sonuç |
|----------|-------|
| Donanım | ✅ Tam entegre |
| Yazılım | ✅ M1-M7 working |
| Test | ✅ 21 passing |
| Demo | ✅ Fiziksel Pi testi |
| Deployment | ✅ Production hazır |

---

## Gelecek Geliştirmeler

- Çoklu robot koordinasyonu
- Cloud dashboard
- Mobil app notification
- Daha büyük mapping

---

## Soru & Cevap

**Teşekkürler!**

---

SeeFire Proje Ekibi
CSE 396 — Otonom Robot Sistemleri

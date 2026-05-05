# Navigation Modülü — Tasarım ve Karar Belgesi

**Proje:** Otonom İç Mekan Navigasyon Robotu  
**Platform:** Raspberry Pi + Arduino  
**Güncelleme:** 2026  

---

## İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Sistem Mimarisi](#2-sistem-mimarisi)
3. [Harita ve Rota Yapısı](#3-harita-ve-rota-yapısı)
4. [Başlangıç Konum Doğrulama](#4-başlangıç-konum-doğrulama)
5. [Ana Navigasyon Döngüsü](#5-ana-navigasyon-döngüsü)
6. [Sektör Yönetimi ve Görüntü İşleme](#6-sektör-yönetimi-ve-görüntü-işleme)
7. [Engel Kaçınma Algoritması](#7-engel-kaçınma-algoritması)
8. [Rotaya Geri Dönüş — Encoder Önceliği](#8-rotaya-geri-dönüş--encoder-önceliği)
9. [Konum Doğrulama](#9-konum-doğrulama)
10. [Kamera ile Dönüş Yönü Belirleme](#10-kamera-ile-dönüş-yönü-belirleme)
11. [Tam Akış Diyagramı](#11-tam-akış-diyagramı)
12. [Pseudo-code](#12-pseudo-code)
13. [navigation.py — Tam Kod](#13-navigationpy--tam-kod)
14. [Alınan Kararlar ve Gerekçeler](#14-alınan-kararlar-ve-gerekçeler)

---

## 1. Genel Bakış

Robot, önceden çizilmiş statik bir harita üzerinde **güney → kuzey** yönünde hareket eder. Rota, güney-kuzey ekseninde eşit **sektörlere** bölünmüştür. Her sektörün sonunda ve ortasında robot durarak kamera görüntüsü alır ve görüntü işleme yapar.

Önünde statik ya da dinamik bir engel çıkarsa **engel kaçınma algoritması** devreye girer. Engel kaçınma sırasında bile sektör orta noktasına gelindiğinde görüntü işleme yapılır — hiçbir sektör atlanmaz.

### Temel özellikler

| Özellik | Değer |
|---|---|
| Hareket yönü | Güney → Kuzey (tek eksen) |
| Konum takibi | Encoder (birincil) + HC-SR04 sol/sağ (doğrulama) |
| Engel tespiti | HC-SR04 ön sensör |
| Dönüş yönü kararı | Kamera piksel oranlaması (birincil) + HC-SR04 sol/sağ (yedek) |
| Rotaya geri dönüş | Encoder counter (sensör kullanılmaz) |
| Görüntü işleme | Logitech C270 + OpenCV |
| Waypoint | Her sektör sonu + her sektör ortası |

---

## 2. Sistem Mimarisi

```
┌────────────────────────────────────────────────────┐
│                  Raspberry Pi                      │
│                                                    │
│   NavigationController                             │
│     │                                              │
│     ├── [navigation.py]  Ana döngü                 │
│     │     ├── Sektör takibi                        │
│     │     ├── Waypoint yönetimi                    │
│     │     └── Görüntü işleme tetikleme             │
│     │                                              │
│     ├── [obstacle.py]    Engel kaçınma             │
│     │     ├── Dönüş yönü belirleme                 │
│     │     ├── Yan geçiş (sol sensör takibi)        │
│     │     └── Encoder ile geri dönüş               │
│     │                                              │
│     ├── [camera.py]      Logitech C270             │
│     │     ├── Kare alma + buffer yönetimi          │
│     │     ├── Engel taraf tespiti (piksel)         │
│     │     └── Görüntü işleme görevi                │
│     │                                              │
│     ├── [sensors.py]     HC-SR04 x3               │
│     │     └── Seri port üzerinden Arduino          │
│     │                                              │
│     ├── [motors.py]      Hareket komutları         │
│     │     └── Seri port üzerinden Arduino          │
│     │                                              │
│     └── [position.py]    Konum doğrulama           │
│           └── Encoder + sensör ince ayarı          │
│                                                    │
└──────────────────────┬─────────────────────────────┘
                       │ USB Serial
┌──────────────────────▼─────────────────────────────┐
│                    Arduino                         │
│   Motor sürücü + Encoder okuma + HC-SR04 tetikleme │
└────────────────────────────────────────────────────┘
```

---

## 3. Harita ve Rota Yapısı

Harita önceden çizilmiştir ve robot tarafından değiştirilmez (statik). Rota güney-kuzey ekseninde **N adet sektöre** bölünmüştür.

```
KUZEY
  │
  │   ◉ Waypoint 3 (Sektör 3 sonu)     ← dur + görüntü işle
  │   │
  │   · Sektör 3 ortası                ← dur + görüntü işle (engel olsa bile)
  │   │
  │   ◉ Waypoint 2 (Sektör 2 sonu)     ← dur + görüntü işle
  │   │
  │   · Sektör 2 ortası                ← dur + görüntü işle (engel olsa bile)
  │   │
  │   ◉ Waypoint 1 (Sektör 1 sonu)     ← dur + görüntü işle
  │   │
  │   · Sektör 1 ortası                ← dur + görüntü işle (engel olsa bile)
  │   │
  ▼ GÜNEY (Başlangıç)
```

### Rota tanımı

Her waypoint `(hedef_kuzey_cm, sektor_no)` çiftiyle tanımlanır.  
`hedef_kuzey_cm`: başlangıçtan kuzey yönüne kat edilecek toplam mesafe.

```python
WAYPOINT_LISTESI = [
    (100, 1),   # 100 cm kuzey = Sektör 1 sonu
    (200, 2),   # 200 cm kuzey = Sektör 2 sonu
    (300, 3),   # 300 cm kuzey = Sektör 3 sonu
]
```

Sektör orta noktası her sektörün başında hesaplanır:

```python
sektor_orta_cm = mevcut_cm + (hedef_cm - mevcut_cm) / 2
```

---

## 4. Başlangıç Konum Doğrulama

Robot çalışmaya başlamadan önce sol ve sağ HC-SR04 sensörleri okunur. Ölçülen mesafeler, haritadan bilinen başlangıç referans değerleriyle karşılaştırılır.

```
Başlangıç noktasında:
  sol_sensör  → sol duvara mesafe (beklenen: BASLANGIC_SOL_CM)
  sag_sensör  → sağ duvara mesafe (beklenen: BASLANGIC_SAG_CM)

  |ölçülen - beklenen| ≤ TOLERANS_CM  → konum onaylandı ✓
  |ölçülen - beklenen| >  TOLERANS_CM  → HATA: robot doğru konumda değil
```

**Neden önemli:** Başlangıç konumu yanlışsa tüm encoder tabanlı konum hesapları birikimli hata üretir. Bu adım, sistemin güvenilir bir referans noktasından başlamasını garantiler.

```python
def baslat(self):
    okuma = self.sensor.filtreli_oku()
    sol_hata = abs(okuma["sol"] - BASLANGIC_SOL_CM)
    sag_hata = abs(okuma["sag"] - BASLANGIC_SAG_CM)

    if sol_hata > TOLERANS_CM or sag_hata > TOLERANS_CM:
        raise RuntimeError("Başlangıç konumu uyuşmuyor.")
```

---

## 5. Ana Navigasyon Döngüsü

Her sektör için şu mantık işletilir:

```
Her sektör için:
  ┌─────────────────────────────────────────┐
  │ 1. Sektör orta noktasını hesapla       │
  │                                         │
  │ 2. DÖNGÜ: mevcut_cm < hedef_cm          │
  │    ┌───────────────────────────────┐    │
  │    │ a. Sektör ortasına gelindi mi? │    │
  │    │    Evet → DUR + GÖRÜNTÜ İŞLE  │    │
  │    │                               │    │
  │    │ b. Ön sensör ölç              │    │
  │    │    Açık → İLERİ_GİT           │    │
  │    │    Engel → ENGEL_KAÇINMA      │    │
  │    └───────────────────────────────┘    │
  │                                         │
  │ 3. Waypoint'e ulaşıldı                 │
  │    DUR + GÖRÜNTÜ İŞLE                  │
  └─────────────────────────────────────────┘
```

Döngü her iterasyonda yalnızca bir adım (`ADIM_MESAFE_CM`) ilerler. Bu sayede sektör orta noktası kontrolü hassas şekilde yapılabilir.

---

## 6. Sektör Yönetimi ve Görüntü İşleme

### Görüntü işlemenin tetiklendiği anlar

| Koşul | Açıklama |
|---|---|
| Sektör orta noktası | Her sektörde bir kez, yolun ortasında |
| Waypoint (sektör sonu) | Her sektörün sonunda |
| Detour sırasında orta nokta | Engel kaçınma rotasında da tetiklenir |

### Kritik karar: Engel varsa sektör atlanmaz

Engel kaçınma sırasında robot farklı bir (detour) rota izler. Bu rota sektör orta noktasını geçebilir. Bu durumda bile `sektor_orta_gecildi` bayrağı kontrol edilir ve görüntü işleme tetiklenir.

```python
# Ana döngüde
if not sektor_orta_gecildi and mevcut_cm >= sektor_orta_cm:
    self.sektor_ortasi_goruntu_isle(sektor_no)
    sektor_orta_gecildi = True

# Engel kaçınma döngüsünde (aynı mantık)
if not self.sektor_orta_gecildi and self.motor.toplam_mesafe_cm >= sektor_orta_cm:
    self.kamera.goruntu_isle()
    self.sektor_orta_gecildi = True
```

**Neden:** Robot bir sektörü hiç işlemeden geçmemelidir. Sektörlerin amacı belirli bölgelerde görüntü toplamaktır; engel varlığı bu amacı ortadan kaldırmaz.

---

## 7. Engel Kaçınma Algoritması

Ön sensör `ENGEL_ESIGI_CM` değerinin altına düştüğünde tetiklenir.

### Adım adım akış

```
[1] DÖNÜŞ YÖNÜ BELİRLE
    └── Kamera piksel oranlaması (birincil)
        └── Kenar tespiti → sol_bosluk / sag_bosluk piksel
        └── sag > sol → SAĞ, sol > sag → SOL
    └── Kamera karar veremezse → HC-SR04 sol/sağ okuması (yedek)

[2] 90° DÖNÜŞ
    └── Seçilen yöne (SAĞ veya SOL) 90° dön
    └── Robot artık doğu veya batıya bakıyor

[3] YAN GEÇİŞ — sol sensör engeli takip eder
    └── Robot doğuya bakarken sol sensör KUZEYE bakar
    └── Sol sensör engelin doğu yüzeyini takip eder
    └── Her adımda:
        ├── Sektör orta noktası kontrolü
        ├── İLERİ_GİT(YAN_ADIM_CM)
        └── yan_mesafe += YAN_ADIM_CM
    └── sol_sensör > BITTI_ESIGI_CM → engel aşıldı, döngüden çık

[4] ROTAYA GERİ DÖN — encoder ile (sensör kullanılmaz)
    └── Kuzeye dön (90° sol)
    └── Batıya dön (90° sol)
    └── İLERİ_GİT(yan_mesafe) ← encoder: tam gidiş mesafesi
    └── Kuzeye dön (90° sağ)

[5] KONUM DOĞRULA — sensör burada devreye girer
    └── Sol + sağ sensör ölç
    └── Hata > TOLERANS_CM → ince ayar yap
```

### Sol sensörün rolü yan geçişte

Robot doğuya döndüğünde yön referansları değişir:

```
Robot doğuya bakarken:
  ön sensör  → doğu (hareket yönü)
  sol sensör → kuzey (engelin yüzeyi bu yönde)
  sağ sensör → güney
```

Sol sensör, engelin **kuzey yüzeyine** olan mesafeyi ölçer. Engel devam ettiği sürece bu değer küçük kalır. Engel bittiğinde değer aniden büyür — bu bitişi işaret eder.

---

## 8. Rotaya Geri Dönüş — Encoder Önceliği

### Neden sensör kullanılmaz?

Geri dönüş sırasında robot batıya bakar. Sol sensör artık **güneyi** gösterir. Bu yönde başka bir engel, duvar çıkıntısı veya farklı bir nesne olabilir. Sensör bu nesneyi yanlış yorumlayarak erken dur komutu üretebilir.

```
Geri dönüş anında robot batıya bakıyor:
  sol sensör → güney ← burada başka engel olabilir
  sağ sensör → kuzey
```

### Encoder tabanlı geri dönüş

Yan geçişte gidilen mesafe `yan_mesafe` değişkenine her adımda eklenir. Geri dönüşte tam bu mesafe kadar batıya gidilir.

```python
# Yan geçiş sırasında (doğuya giderken)
yan_mesafe_cm = 0.0
while sol_sensör_engelde:
    motor.ileri_git(YAN_ADIM_CM)
    yan_mesafe_cm += YAN_ADIM_CM

# Geri dönüş (batıya)
motor.sola_don()          # kuzeye bak
motor.sola_don()          # batıya bak
motor.ileri_git(yan_mesafe_cm)   # encoder: tam gidiş mesafesi
motor.saga_don()          # kuzeye bak
```

**Encoder hatası:** Motor kayması (slip) veya zemin sürtünmesi nedeniyle encoder küçük hatalar biriktirebilir. Bu nedenle geri dönüş tamamlandıktan sonra sol+sağ sensörle konum doğrulaması yapılır ve gerekirse ince ayar uygulanır.

---

## 9. Konum Doğrulama

Encoder birincil konum aracıdır. Sensör yalnızca iki durumda devreye girer:

1. **Başlangıçta:** referans değerlerle karşılaştırma
2. **Engel kaçınma sonrası:** encoder hatasını telafi etme

```python
def dogrula(self):
    okuma = self.sensor.filtreli_oku()   # 3 okuma, medyan
    sol_hata = okuma["sol"] - BASLANGIC_SOL_CM
    sag_hata = okuma["sag"] - BASLANGIC_SAG_CM

    if abs(sol_hata) > TOLERANS_CM:
        if sol_hata > 0:
            # Sola kaymış → sağa küçük adım
            motor.saga_don()
            motor.ileri_git(INCE_AYAR_CM)
            motor.sola_don()
        else:
            # Sağa kaymış → sola küçük adım
            motor.sola_don()
            motor.ileri_git(INCE_AYAR_CM)
            motor.saga_don()
```

`filtreli_oku()` 3 okuma alıp medyan döner. Anlık gürültü ve yansıma hatalarına karşı koruma sağlar.

---

## 10. Kamera ile Dönüş Yönü Belirleme

### Neden kamera?

HC-SR04 sol ve sağ sensörler belirli bir doğrultuda tek nokta ölçer. Engelin tamamının sol veya sağ tarafa ne kadar uzandığını göremezler. Kamera, engelin **2 boyutlu görünümünü** değerlendirerek daha doğru karar verir.

### Yöntem: piksel oranlaması

Fiziksel cm hesabı yapılmaz. Yalnızca "hangi tarafta daha fazla açık alan var" sorusu cevaplanır.

```python
def donus_yonu_belirle(self, frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)

    # Alt yarıya odaklan (zemin gürültüsünü kes)
    roi  = edges[frame_height // 2:, :]
    cols = np.where(roi.any(axis=0))[0]

    if len(cols) == 0:
        return None          # engel görünmüyor

    sol_bosluk = cols[0]                  # engelin sol kenarına piksel
    sag_bosluk = frame_width - cols[-1]   # engelin sağ kenarından piksel

    return "SAG" if sag_bosluk > sol_bosluk else "SOL"
```

### Yedek: HC-SR04

Kamera `None` döndürürse (engel görünmüyorsa, ışık yetersizse vb.) sol ve sağ HC-SR04 okuması kullanılır:

```python
if yon is None:
    okuma = sensor.filtreli_oku()
    yon = "SAG" if okuma["sag"] > okuma["sol"] else "SOL"
```

### C270 teknik notları

| Parametre | Değer |
|---|---|
| Çözünürlük | 640 × 480 (Pi'de yavaşlarsa 320 × 240) |
| FPS | 30 |
| Buffer boyutu | 1 (gecikmeyi azaltır) |
| Isınma | İlk 5 kare atılır (bulanıklık) |
| Bağlantı | `/dev/video0` — `lsusb` ile doğrula |

---

## 11. Tam Akış Diyagramı

```
BAŞLAT
  │
  ▼
Sol + Sağ sensör ölç
  │
  ├─ Beklenen değer? ─── HAYIR ──→ HATA (konum uyuşmuyor)
  │
  ▼ EVET
Her sektör için:
  │
  ▼
sektor_orta_cm = mevcut + (hedef - mevcut) / 2
sektor_orta_gecildi = False
  │
  ▼
┌─── mevcut_cm < hedef_cm? ───────────────────────────────── HAYIR ──┐
│                                                                     │
│  Evet                                                               │
│  │                                                                  │
│  ├─ mevcut_cm >= sektor_orta_cm VE orta_gecilmedi?                  │
│  │    Evet → DUR → GORUNTU_ISLE → orta_gecildi = True               │
│  │                                                                  │
│  ▼                                                                  │
│  Ön sensör ölç                                                      │
│  │                                                                  │
│  ├─ on > ENGEL_ESIGI ──→ İLERİ_GİT ──────────────────────────────┐ │
│  │                                                                │ │
│  └─ on ≤ ENGEL_ESIGI ──→ ENGEL_KAÇINMA                           │ │
│          │                                                        │ │
│          ├─ [1] Kamera → dönüş yönü (yedek: sensör)              │ │
│          │                                                        │ │
│          ├─ [2] 90° dön (SAĞ veya SOL)                           │ │
│          │                                                        │ │
│          ├─ [3] YAN GEÇİŞ DÖNGÜSÜ                                │ │
│          │       │                                                │ │
│          │       ├─ Sektör orta kontrolü → GORUNTU_ISLE?         │ │
│          │       ├─ İLERİ_GİT(YAN_ADIM_CM)                       │ │
│          │       ├─ yan_mesafe += YAN_ADIM_CM                    │ │
│          │       └─ sol > BITTI_ESIGI? → döngüden çık            │ │
│          │                                                        │ │
│          ├─ [4] Rotaya geri dön (encoder ile)                    │ │
│          │       SOL'A DÖN → SOL'A DÖN → İLERİ_GİT(yan_mesafe) │ │
│          │       SAĞ'A DÖN                                       │ │
│          │                                                        │ │
│          └─ [5] Konum doğrula (sensör ince ayar)                 │ │
│                                                          ────────┘ │
└─────────────────────────────────────────────────────────────────────┘
  │
  ▼
DUR → GORUNTU_ISLE (waypoint sonu)
  │
  ▼
Sonraki sektör?
  │
  ├─ Evet → döngü başına dön
  └─ Hayır → TAMAMLANDI
```

---

## 12. Pseudo-code

```
══════════════════════════════════════════════
BAŞLATMA
══════════════════════════════════════════════

  sol = SENSOR_OKU(sol)
  sag = SENSOR_OKU(sağ)

  EĞER |sol - beklenen_sol| > TOLERANS:  HATA_VER()
  EĞER |sag - beklenen_sag| > TOLERANS:  HATA_VER()

  konum_onaylandi = TRUE


══════════════════════════════════════════════
ANA DÖNGÜ — HER SEKTÖR İÇİN
══════════════════════════════════════════════

  sektor_orta_cm   = mevcut_cm + (hedef_cm - mevcut_cm) / 2
  orta_gecildi     = FALSE

  WHILE mevcut_cm < hedef_cm:

    ── Sektör orta kontrolü ─────────────────
    EĞER mevcut_cm >= sektor_orta_cm VE orta_gecildi = FALSE:
      DUR()
      GORUNTU_ISLE()          ← engel olsa da atlanmaz
      orta_gecildi = TRUE

    ── İlerleme ─────────────────────────────
    on = SENSOR_OKU(ön)

    EĞER on > ENGEL_ESIGI:
      ILERI_GIT()

    DEGILSE:
      ENGEL_KAÇINMA()         ← aşağıya bak


  ── Waypoint ulaşıldı ────────────────────────
  DUR()
  GORUNTU_ISLE()


══════════════════════════════════════════════
ENGEL_KAÇINMA()
══════════════════════════════════════════════

  [1] DÖNÜŞ YÖNÜ BELİRLE
      yon = KAMERA_PIKSEL_ORA()         ← birincil
      EĞER yon = None:
        yon = (sag_sensör > sol_sensör) ? SAG : SOL    ← yedek

  [2] 90° yon'a DÖN
      yan_mesafe = 0

  [3] YAN GEÇİŞ — sol sensör engeli takip eder
      WHILE SENSOR_OKU(sol) < BITTI_ESIGI:

        EĞER mevcut_cm >= sektor_orta_cm VE orta_gecildi = FALSE:
          DUR()
          GORUNTU_ISLE()       ← detour'da da atlanmaz
          orta_gecildi = TRUE

        ILERI_GIT(YAN_ADIM)
        yan_mesafe += YAN_ADIM

  [4] ROTAYA GERİ DÖN — encoder kullanılır, sensör KULLANILMAZ
      ── Neden: geri dönerken solda başka engel olabilir ──

      SOL'A DÖN 90°           ← kuzeye bak
      SOL'A DÖN 90°           ← batıya bak
      ILERI_GIT(yan_mesafe)   ← encoder: gidiş mesafesi kadar
      SAĞ'A DÖN 90°           ← kuzeye bak

  [5] KONUM DOĞRULA — sensör sadece burada devreye girer
      sol = SENSOR_OKU(sol)
      sag = SENSOR_OKU(sağ)

      EĞER |sol - beklenen_sol| > TOLERANS: INCE_AYAR_YAP()
```

---

## 13. navigation.py — Tam Kod

```python
"""
navigation.py
─────────────
Ana navigasyon döngüsü.

Sorumluluklar:
  - Başlangıç konum doğrulama
  - Sektör ve waypoint yönetimi
  - Sektör orta noktası görüntü işleme tetikleme
  - Engel tespiti ve EngelKacin modülü çağrısı
  - Engel sonrası konum doğrulama
"""

import time
from config import (
    ENGEL_ESIGI_CM,
    BASLANGIC_SOL_CM,
    BASLANGIC_SAG_CM,
    TOLERANS_CM,
    ADIM_MESAFE_CM,
    WAYPOINT_LISTESI,
)
from camera import Kamera
from sensors import SensorManager
from motors import MotorController
from position import KonumTakip
from obstacle import EngelKacin


class NavigationController:

    def __init__(self):
        self.sensor = SensorManager()
        self.kamera = Kamera()
        self.motor  = MotorController(self.sensor.ser)
        self.konum  = KonumTakip(self.sensor, self.motor)
        self.engel  = EngelKacin(
            sensor=self.sensor,
            motor=self.motor,
            kamera=self.kamera,
            konum=self.konum,
        )

    # ──────────────────────────────────────────────────────────
    # BAŞLATMA
    # ──────────────────────────────────────────────────────────

    def baslat(self):
        """
        Sol ve sağ sensörle başlangıç konumunu doğrula.
        Beklenen değerlerden fazla sapma varsa RuntimeError fırlatır.
        """
        print("[BAŞLATMA] Konum doğrulanıyor...")
        okuma = self.sensor.filtreli_oku()

        sol_hata = abs(okuma["sol"] - BASLANGIC_SOL_CM)
        sag_hata = abs(okuma["sag"] - BASLANGIC_SAG_CM)

        if sol_hata > TOLERANS_CM or sag_hata > TOLERANS_CM:
            raise RuntimeError(
                "Başlangıç konumu uyuşmuyor. "
                "Sol: {:.1f} cm (beklenen {:.1f} ±{:.1f}), "
                "Sağ: {:.1f} cm (beklenen {:.1f} ±{:.1f})".format(
                    okuma["sol"], BASLANGIC_SOL_CM, TOLERANS_CM,
                    okuma["sag"], BASLANGIC_SAG_CM, TOLERANS_CM,
                )
            )

        print("[BAŞLATMA] Onaylandı — Sol: {:.1f} cm, Sağ: {:.1f} cm".format(
            okuma["sol"], okuma["sag"]
        ))

    # ──────────────────────────────────────────────────────────
    # GÖRÜNTÜ İŞLEME
    # ──────────────────────────────────────────────────────────

    def goruntu_isle(self, etiket=""):
        """
        Robotun durduğu noktada görüntü işleme yapar.
        Her iki tetiklenme koşulunda da (waypoint + sektör ortası)
        bu fonksiyon çağrılır.

        Args:
            etiket: log çıktısı için bağlam bilgisi
        """
        print("[GÖRÜNTÜ] {} — işleniyor...".format(etiket))
        self.motor.dur()
        time.sleep(0.3)

        sonuc = self.kamera.goruntu_isle()
        print("[GÖRÜNTÜ] Sonuç:", sonuc)
        time.sleep(0.2)
        return sonuc

    # ──────────────────────────────────────────────────────────
    # ANA DÖNGÜ
    # ──────────────────────────────────────────────────────────

    def calistir(self, waypoint_listesi=None):
        """
        Navigasyon ana döngüsü.

        Args:
            waypoint_listesi: [(hedef_kuzey_cm, sektor_no), ...]
                              None → config.WAYPOINT_LISTESI kullanılır
        """
        if waypoint_listesi is None:
            waypoint_listesi = WAYPOINT_LISTESI

        self.baslat()

        for hedef_cm, sektor_no in waypoint_listesi:
            print("\n[SEKTÖR {}] Başlıyor — hedef: {} cm".format(sektor_no, hedef_cm))

            # Sektör orta noktasını hesapla
            mevcut_cm           = self.motor.toplam_mesafe_cm
            sektor_orta_cm      = mevcut_cm + (hedef_cm - mevcut_cm) / 2
            sektor_orta_gecildi = False

            print("[SEKTÖR {}] Orta nokta: {:.1f} cm".format(sektor_no, sektor_orta_cm))

            # ── Sektör döngüsü ─────────────────────────────
            while self.motor.toplam_mesafe_cm < hedef_cm:

                # Sektör orta noktası kontrolü
                if (not sektor_orta_gecildi and
                        self.motor.toplam_mesafe_cm >= sektor_orta_cm):
                    self.goruntu_isle("Sektör {} ortası".format(sektor_no))
                    sektor_orta_gecildi = True

                # Ön sensör ölç
                okuma = self.sensor.oku()
                on    = okuma["on"]

                if on < 0:
                    # Sensör okunamadı — güvenli adım at
                    print("[UYARI] Ön sensör okunamadı.")
                    self.motor.ileri_git(ADIM_MESAFE_CM)
                    continue

                if on > ENGEL_ESIGI_CM:
                    # Yol açık
                    self.motor.ileri_git(ADIM_MESAFE_CM)

                else:
                    # Engel tespit edildi
                    print("[ENGEL] {:.1f} cm — kaçınma başlıyor.".format(on))

                    self.engel.kac(
                        sektor_no           = sektor_no,
                        sektor_orta_cm      = sektor_orta_cm,
                        sektor_orta_gecildi = sektor_orta_gecildi,
                    )

                    # EngelKacin içindeki güncel bayrak al
                    sektor_orta_gecildi = self.engel.sektor_orta_gecildi

                    # Konum doğrulaması EngelKacin içinde yapıldı
                    print("[ENGEL] Kaçınma tamamlandı. Rotaya devam.")

            # ── Waypoint'e ulaşıldı ────────────────────────
            print("[WAYPOINT] Sektör {} sonu.".format(sektor_no))
            self.goruntu_isle("Sektör {} waypoint".format(sektor_no))

        print("\n[TAMAMLANDI] Tüm sektörler geçildi.")
        self.kapat()

    # ──────────────────────────────────────────────────────────
    # KAPATMA
    # ──────────────────────────────────────────────────────────

    def kapat(self):
        self.motor.dur()
        self.kamera.kapat()
        self.sensor.kapat()
```

---

## 14. Alınan Kararlar ve Gerekçeler

### 1. Encoder birincil, sensör yalnızca doğrulama aracı

**Karar:** Konum takibinde encoder kullanılır. HC-SR04 sol/sağ sensörler yalnızca başlangıç onayı ve engel kaçınma sonrası ince ayar için devreye girer.

**Gerekçe:** Sürekli sensör tabanlı takip ortam bağımlıdır. Duvar pürüzleri, perspektif değişimi ve çoklu yansımalar hata üretir. Encoder mekanik olarak belirleyicidir ve ortam koşullarından etkilenmez.

---

### 2. Geri dönüşte sensör kullanılmaz

**Karar:** Engel kaçınma sonrası orijinal rota çizgisine dönerken `yan_mesafe` encoder counter'ı kullanılır.

**Gerekçe:** Geri dönüş sırasında robot batıya bakar ve sol sensörü güneye yönelir. Bu yönde başka bir engel, köşe çıkıntısı veya farklı bir nesne bulunabilir. Sensör bunu yanlış yorumlayarak erken dur komutu verebilir. Encoder bu riski ortadan kaldırır.

---

### 3. Dönüş yönü kameradan belirlenir

**Karar:** Engel kaçınmada hangi yöne döneceğini kamera piksel oranlaması belirler. HC-SR04 yedek olarak kullanılır.

**Gerekçe:** HC-SR04, sabit bir açıda tek nokta ölçer. Kamera, engelin tüm yüzeyinin görüntüsünü değerlendirerek hangi tarafta daha fazla açık alan olduğunu daha güvenilir biçimde belirler.

---

### 4. Sektör görüntü işleme hiçbir koşulda atlanmaz

**Karar:** Engel kaçınma (detour) rotasında bile sektör orta noktasına gelindiğinde görüntü işleme yapılır.

**Gerekçe:** Sektörlerin amacı belirli bölgelerde görüntü toplamaktır. Engel varlığı bu amacı ortadan kaldırmaz. `sektor_orta_gecildi` bayrağı hem ana döngüde hem de `EngelKacin` içinde aynı şekilde kontrol edilir.

---

### 5. Sol sensör yan geçişte engeli takip eder

**Karar:** Robot doğuya döndükten sonra sol sensör (artık kuzeyi gösterir) engelin doğu yüzeyini takip eder.

**Gerekçe:** Robot doğuya bakarken sol sensör kuzey yönünü gösterir. Engel kuzey tarafında olduğundan sol sensör engelin yüzeyine olan mesafeyi ölçer. Mesafe büyüdüğünde engel aşılmış demektir.

---

### 6. Medyan filtreli sensör okuma

**Karar:** Kritik ölçümlerde (`filtreli_oku`) 3 okuma alınır ve medyan döndürülür.

**Gerekçe:** HC-SR04 tek okumada gürültülü veri üretebilir. Medyan, ortalamanın aksine, aykırı değerlerden etkilenmez.

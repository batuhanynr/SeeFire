# Robot Navigasyon — Pseudo-Code Dokümantasyonu

## 📋 Genel Bakış

Bu doküman, otonom bir robotun sensör tabanlı navigasyon ve engel kaçınma mantığını pseudo-code formatında tanımlar. Sistem üç ana bloktan oluşur: **Başlatma**, **Ana Döngü** ve **Engel Kaçınma**.

---

## 1. 🚀 Başlatma

Robot çalışmaya başladığında önce sol ve sağ sensörlerden konum verisini okur, ardından rotayı yükler.

```
BAŞLAT:
  sol_mesafe  = SENSOR_OKU(sol)
  sag_mesafe  = SENSOR_OKU(sağ)

  EĞER sol_mesafe VE sag_mesafe beklenen değerlerdeyse:
    konum_onaylandi = TRUE
    rota = YUKLE_ROTA(harita)
  DEĞİLSE:
    HATA_VER("Başlangıç konumu uyuşmuyor")
    DUR
```

> ⚠️ **Not:** Her iki sensör de beklenen aralık dışındaysa sistem tamamen durur ve hata fırlatır.
> 

---

## 2. 🔄 Ana Döngü

Rota üzerindeki her waypoint için robot ileri hareket eder; önündeki engel eşiği aşılırsa engel kaçınma moduna geçer.

```
HER waypoint İÇİN rota:

  ── [1] ROTADA İLERLE ─────────────────────────────
  WHILE hedef_waypoint'e ulaşılmadı:
    on_mesafe = SENSOR_OKU(ön)

    EĞER on_mesafe > ENGEL_ESIGI:
      İLERİ_GİT()
    DEĞİLSE:
      ENGEL_KAÇINMA()  →  [2]'ye git

  ── [WAYPOINT'E ULAŞILDI] ─────────────────────────
  DUR()
  GORUNTU_ISLE()       ← kamera görevi burada
  SONRAKİ_WAYPOINT_SEÇ()
```

> 📷 **Kamera görevi:** Her waypoint'e varıldığında robot durur ve görüntü işleme rutini çalıştırılır.
> 

---

## 3. 🛑 Engel Kaçınma

Engel tespit edildiğinde robot yan geçiş manevrası yapar ve ardından orijinal rotaya geri döner.

### [2] Yön Belirleme

```
ENGEL_KAÇINMA():

  sol_bos = SENSOR_OKU(sol) > MIN_BOSLUK
  sag_bos = SENSOR_OKU(sağ) > MIN_BOSLUK

  EĞER sag_bos:
    donus_yonu = SAĞ
  YOKSA EĞER sol_bos:
    donus_yonu = SOL
  DEĞİLSE:
    GERİ_GİT()          ← çıkmaz sokak durumu
    donus_yonu = BELİRLE()
```

### [3] Engeli Yan Taraftan Aşma

```
90° donus_yonu'na DÖN
yan_gidilen_mesafe = 0

WHILE YAN_SENSOR_OKU(engel_taraf) < ENGEL_BİTTİ_ESIGI:
  İLERİ_GİT(adım)
  yan_gidilen_mesafe += adım    ← kaç cm yan gidildi?

← engel burada bitti
```

### [4] Rotaya Geri Dönüş

```
EĞER donus_yonu == SAĞ:
  SOL'A DÖN 90°
DEĞİLSE:
  SAĞ'A DÖN 90°

İLERİ_GİT(yan_gidilen_mesafe)   ← geri hizaya gel

EĞER donus_yonu == SAĞ:
  SOL'A DÖN 90°
DEĞİLSE:
  SAĞ'A DÖN 90°

← robot tekrar kuzeye bakıyor ve rota çizgisinde
```

### [5] Konum Doğrulama (Hibrit Yöntem)

```
sol_ref = SENSOR_OKU(sol)
sag_ref = SENSOR_OKU(sağ)

EĞER |sol_ref - beklenen_sol| > TOLERANS:
  ince_ayar_yap()    ← küçük sağ/sol düzeltme

ROTADA İLERLE()  →  [1]'e dön
```

---

## 4. 🗺️ Akış Özeti

| Adım | Açıklama | İlgili Blok |
| --- | --- | --- |
| [1] | Rotada ileri hareket | Ana Döngü |
| [2] | Engel yönünü belirleme | Engel Kaçınma |
| [3] | Engeli yan taraftan aşma | Engel Kaçınma |
| [4] | Orijinal rotaya geri dönüş | Engel Kaçınma |
| [5] | Konum doğrulama ve ince ayar | Engel Kaçınma |

---

## 5. 📐 Temel Değişkenler ve Sabitler

| Değişken / Sabit | Açıklama |
| --- | --- |
| `ENGEL_ESIGI` | Ön sensörde engelleyen minimum mesafe |
| `MIN_BOSLUK` | Yan geçiş için gereken minimum boşluk |
| `ENGEL_BİTTİ_ESIGI` | Yan sensörde engelin bittiğini gösteren eşik |
| `TOLERANS` | Konum doğrulamada kabul edilen sapma miktarı |
| `yan_gidilen_mesafe` | Engel boyunca yan gidilen toplam mesafe (cm) |
| `donus_yonu` | Engel kaçınma için seçilen yön (SAĞ / SOL) |
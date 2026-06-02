# SeeFire — Fiziksel Kablolama Planı

**Proje:** SeeFire Yangın Tespit Robotu | **Grup:** Group 4 | **Ders:** CSE 396 Spring 2025-2026  
**Platform:** Raspberry Pi 4 | **Şasi:** 4WD Çift Katlı Akrilik | **Batarya:** LiPo 2S 7.4V 2200mAh

---

## 1. Python Pin Sabitleri (config.py)

```python
# ════════════════════════════════════════════════════════
#  SeeFire — Donanım Pin Sabitleri (BCM numaralandırması)
# ════════════════════════════════════════════════════════

# ── Motor Sürücüler (L298N ×2 — Ön + Arka, paralel sinyal) ───────
# Motor 1=FL, Motor 2=FR, Motor 3=RL, Motor 4=RR
# Ön L298N: Motor 1 (OUT1/2), Motor 2 (OUT3/4)
# Arka L298N: Motor 3 (OUT1/2), Motor 4 (OUT3/4)
# Her iki sürücünün IN ve EN pinleri aynı GPIO'ya paralel bağlı.
PIN_IN1 = 17      # Sol yön A  (Motor 1+3) — her iki L298N IN1'e paralel
PIN_IN2 = 18      # Sol yön B  (Motor 1+3) — her iki L298N IN2'ye paralel
PIN_IN3 = 27      # Sağ yön A  (Motor 2+4) — her iki L298N IN3'e paralel
PIN_IN4 = 22      # Sağ yön B  (Motor 2+4) — her iki L298N IN4'e paralel
PIN_ENA = 12      # Sol PWM    (Motor 1+3) — her iki L298N ENA'ya paralel (hw PWM)
PIN_ENB = 13      # Sağ PWM    (Motor 2+4) — her iki L298N ENB'ye paralel (hw PWM)

# ── Teker Enkoderleri (2 adet — Motor 1 ve Motor 2) ──────────────
PIN_ENC_LEFT  = 6   # Sol enkoder sinyal (Motor 1 / FL) — BCM 6 (Pin 31)
PIN_ENC_RIGHT = 7   # Sağ enkoder sinyal (Motor 2 / FR) — BCM 7 (Pin 26)
# VCC: 3.3V  |  GND: GND  |  Sinyal: 3.3V uyumlu (bölücü yok)

# ── HC-SR04 Ultrasonik Sensörler ─────────────────────────────────
PIN_TRIG_FRONT = 23   # Ön sensör — tetik
PIN_ECHO_FRONT = 24   # Ön sensör — yankı (voltaj bölücüden, ~3.18V)
PIN_TRIG_RIGHT = 25   # Sağ sensör — tetik
PIN_ECHO_RIGHT = 21   # Sağ sensör — yankı (voltaj bölücüden, ~3.18V)
PIN_TRIG_LEFT  = 20   # Sol sensör — tetik
PIN_ECHO_LEFT  = 16   # Sol sensör — yankı (voltaj bölücüden, ~3.18V)
# VCC: 5V  |  TRIG: 3.3V çıkış (Pi direkt)
# ECHO: 5V çıkış → 1kΩ + 2kΩ bölücü → GPIO (~3.18V ölçüldü ✓)

# ── MLX90614 IR Termometre (I²C) ─────────────────────────────────
I2C_BUS         = 1       # /dev/i2c-1
MLX90614_ADDR   = 0x5A    # Varsayılan I²C adresi
# SDA: GPIO2 (Pin 3)  |  SCL: GPIO3 (Pin 5)
# VCC: 3.3V  |  GND: GND

# ── MCP3008 ADC (SPI) ────────────────────────────────────────────
SPI_BUS     = 0     # /dev/spidev0.x
SPI_DEVICE  = 0     # CE0 — ancak CS GPIO5 üzerinden yazılımsal
PIN_SPI_CS  = 5     # CS/SHDN — GPIO5 (Pin 29)
# CLK: GPIO11 (Pin 23)  |  MISO: GPIO9 (Pin 21)  |  MOSI: GPIO10 (Pin 19)
# VDD: 3.3V  |  VREF: 3.3V  |  AGND: GND  |  DGND: GND

# ── MQ-2 Gaz/Duman Sensörü ───────────────────────────────────────
MQ2_CHANNEL     = 0       # MCP3008 CH0
MQ2_WARMUP_SEC  = 60      # Açılışta bekleme süresi
MQ2_THRESHOLD   = 300     # Ham ADC eşik (0–1023)
# VCC: 5V  |  GND: GND  |  AOUT → MCP3008 CH0  |  DOUT: bağlı değil

# ── Alarm ─────────────────────────────────────────────────────────
PIN_LED    = 26   # Alarm LED — 330Ω seri direnç ile (Pin 37)
PIN_BUZZER = 19   # Aktif buzzer (Pin 35)
```

---

## 2. GPIO Tam Atama Tablosu

> Sıralama: Header Pin numarasına göre. Tüm GPIO numaraları BCM.

| Header Pin | BCM GPIO | Yön   | Bağlı Bileşen              | Protokol     |
|:----------:|:--------:|:-----:|----------------------------|:------------:|
| 1          | —        | OUT   | MLX90614 VCC, MCP3008 VDD/VREF | 3.3V güç |
| 2          | —        | OUT   | HC-SR04 ×3 VCC, MQ-2 VCC  | 5V güç       |
| 3          | GPIO2    | I/O   | MLX90614 SDA               | I²C          |
| 4          | —        | OUT   | LM2596 OUT+ bağlantısı     | 5V güç (Pi besleme) |
| 5          | GPIO3    | I/O   | MLX90614 SCL               | I²C          |
| 6          | —        | GND   | Fan (−), genel GND         | —            |
| 7          | GPIO4    | IN    | Serbest                    | Dijital      |
| 9          | —        | GND   | MLX90614 GND               | —            |
| 11         | GPIO17   | OUT   | L298N ×2 IN1 — sol yön A (paralel)  | Dijital      |
| 12         | GPIO18   | OUT   | L298N ×2 IN2 — sol yön B (paralel)  | Dijital      |
| 13         | GPIO27   | OUT   | L298N ×2 IN3 — sağ yön A (paralel)  | Dijital      |
| 14         | —        | GND   | Genel GND                  | —            |
| 15         | GPIO22   | OUT   | L298N ×2 IN4 — sağ yön B (paralel)  | Dijital      |
| 16         | GPIO23   | OUT   | HC-SR04 ön TRIG            | Dijital      |
| 17         | —        | OUT   | Breadboard 3.3V rayı       | 3.3V güç     |
| 18         | GPIO24   | IN    | HC-SR04 ön ECHO (bölücüden)| Dijital      |
| 19         | GPIO10   | OUT   | MCP3008 DIN (MOSI)         | SPI          |
| 20         | —        | GND   | MCP3008 AGND/DGND          | —            |
| 21         | GPIO9    | IN    | MCP3008 DOUT (MISO)        | SPI          |
| 22         | GPIO25   | OUT   | HC-SR04 sağ TRIG           | Dijital      |
| 23         | GPIO11   | OUT   | MCP3008 CLK (SCLK)         | SPI          |
| 25         | —        | GND   | Genel GND                  | —            |
| 26         | GPIO7    | IN    | Enkoder sağ (Motor 2 / FR) | Dijital      |
| 29         | GPIO5    | OUT   | MCP3008 CS/SHDN            | SPI (yazılımsal CS) |
| 31         | GPIO6    | IN    | Enkoder sol (Motor 1 / FL) | Dijital      |
| 32         | GPIO12   | OUT   | L298N ×2 ENA — sol PWM (paralel) | PWM (1kHz)   |
| 33         | GPIO13   | OUT   | L298N ×2 ENB — sağ PWM (paralel) | PWM (1kHz)   |
| 34         | —        | GND   | Buzzer (−)                 | —            |
| 35         | GPIO19   | OUT   | Aktif buzzer (+)           | Dijital      |
| 36         | GPIO16   | IN    | HC-SR04 sol ECHO (bölücüden)| Dijital     |
| 37         | GPIO26   | OUT   | Alarm LED (330Ω seri)      | Dijital      |
| 38         | GPIO20   | OUT   | HC-SR04 sol TRIG           | Dijital      |
| 40         | GPIO21   | IN    | HC-SR04 sağ ECHO (bölücüden)| Dijital     |
| 40         | —        | GND   | Fan Kırmızı (+)            | 5V güç       |
| 40         | —        | GND   | Fan Siyah (−)              | —            |

### Boşta Kalan GPIO Pinleri

| Header Pin | BCM GPIO | Not                          |
|:----------:|:--------:|------------------------------|
| 7          | GPIO4    | Serbest                      |
| 27         | GPIO0    | I²C ID EEPROM — dokunma      |
| 28         | GPIO1    | I²C ID EEPROM — dokunma      |
| 24         | GPIO8    | SPI CE0 — sensör için kullanma |

---

## 3. Güç Hattı Topolojisi

```
LiPo 2S 7.4V
    │
    ├─ (+) ──→ [Anahtar] ──→ [Sigorta 5-10A] ──→ Breadboard (+) rayı
    │                                                     │
    │                                   ┌─────────────────┼─────────────────┐
    │                                   │                 │                 │
    │                            L298N #1 VS       L298N #2 VS         LM2596 IN+
    │                            (ön sürücü)       (arka sürücü)       (7.4V giriş)
    │                                                                       │
    │                                                                LM2596 OUT+
    │                                                                (5.00V — kalibreli)
    │                                                                       │
    │                                                              Pi Header Pin 4
    │
    └─ (−) ──→ Breadboard GND rayı (ortak toprak)
                     │
        ┌────────────┼─────────────┬──────────────┬──────────────┐
        │            │             │              │              │
    L298N #1 GND  L298N #2 GND  LM2596 OUT−   Pi Pin 6       Tüm sensör
                                                              GND'leri
```

**Güç Rayları (breadboard):**

| Ray       | Kaynak               | Besledikleri                                  |
|-----------|----------------------|-----------------------------------------------|
| (+) 7.4V  | LiPo → Anahtar → Sigorta | L298N #1 VS, L298N #2 VS, LM2596 IN+   |
| 5V        | Pi Pin 2 veya Pin 4  | HC-SR04 ×3 VCC, MQ-2 VCC, Fan (+)            |
| 3.3V      | Pi Pin 1 veya Pin 17 | MLX90614 VCC, MCP3008 VDD+VREF, Enkoder VCC  |
| GND       | LiPo (−)             | Her şeyin GND'si — ortak toprak               |

---

## 4. Voltaj Bölücü Devreleri (HC-SR04 ECHO)

HC-SR04 ECHO pini 5V çıkış üretir. Pi GPIO max 3.3V tolere eder.  
**Her ECHO için ayrı bölücü** — 3 sensör = 3 ayrı devre.

```
HC-SR04 ECHO (5V)
        │
       [1kΩ]
        │
        ├──────────── GPIO (Pi)   ← ~3.18V ölçüldü ✓
        │
       [2kΩ]
        │
       GND
```

| Sensör    | ECHO Kaynağı | GPIO Hedef | Ölçülen Gerilim |
|-----------|:------------:|:----------:|:---------------:|
| Ön        | HC-SR04 ön   | GPIO24     | ~3.18V ✓        |
| Sağ       | HC-SR04 sağ  | GPIO21     | ~3.18V ✓        |
| Sol       | HC-SR04 sol  | GPIO16     | ~3.18V ✓        |

---

## 5. Motor ve Enkoder Bağlantıları

### Motor Tanımları

| Motor No | Pozisyon  | Kısaltma | Sürücü       |
|:--------:|-----------|:--------:|:------------:|
| Motor 1  | Ön Sol    | FL       | Ön L298N #1  |
| Motor 2  | Ön Sağ    | FR       | Ön L298N #1  |
| Motor 3  | Arka Sol  | RL       | Arka L298N #2 |
| Motor 4  | Arka Sağ  | RR       | Arka L298N #2 |

### Ön L298N (#1) — Motor 1 ve Motor 2

| L298N #1 Terminali | Bağlantı                              |
|:------------------:|---------------------------------------|
| **OUT1**           | Motor 1 (FL) — tel A                  |
| **OUT2**           | Motor 1 (FL) — tel B                  |
| **OUT3**           | Motor 2 (FR) — tel A                  |
| **OUT4**           | Motor 2 (FR) — tel B                  |
| **IN1**            | GPIO17 (Pin 11) — sol yön A (paralel) |
| **IN2**            | GPIO18 (Pin 12) — sol yön B (paralel) |
| **IN3**            | GPIO27 (Pin 13) — sağ yön A (paralel) |
| **IN4**            | GPIO22 (Pin 15) — sağ yön B (paralel) |
| **ENA**            | GPIO12 (Pin 32) — sol PWM (paralel)   |
| **ENB**            | GPIO13 (Pin 33) — sağ PWM (paralel)   |
| **VS**             | 7.4V breadboard (+) rayı              |
| **GND**            | Ortak GND rayı                        |
| **5V**             | ⚠️ Boşta (bağlama)                   |

### Arka L298N (#2) — Motor 3 ve Motor 4

| L298N #2 Terminali | Bağlantı                              |
|:------------------:|---------------------------------------|
| **OUT1**           | Motor 3 (RL) — tel A                  |
| **OUT2**           | Motor 3 (RL) — tel B                  |
| **OUT3**           | Motor 4 (RR) — tel A                  |
| **OUT4**           | Motor 4 (RR) — tel B                  |
| **IN1**            | GPIO17 (Pin 11) — sol yön A (paralel) |
| **IN2**            | GPIO18 (Pin 12) — sol yön B (paralel) |
| **IN3**            | GPIO27 (Pin 13) — sağ yön A (paralel) |
| **IN4**            | GPIO22 (Pin 15) — sağ yön B (paralel) |
| **ENA**            | GPIO12 (Pin 32) — sol PWM (paralel)   |
| **ENB**            | GPIO13 (Pin 33) — sağ PWM (paralel)   |
| **VS**             | 7.4V breadboard (+) rayı              |
| **GND**            | Ortak GND rayı                        |
| **5V**             | ⚠️ Boşta (bağlama)                   |

### Paralel GPIO Sinyal Şeması

Pi'den çıkan 6 sinyal kablosu her iki L298N'e paralel bağlıdır:

```
Pi GPIO17 (Pin 11) ──┬── L298N #1 IN1  →  Motor 1 (FL) yön A
                     └── L298N #2 IN1  →  Motor 3 (RL) yön A

Pi GPIO18 (Pin 12) ──┬── L298N #1 IN2  →  Motor 1 (FL) yön B
                     └── L298N #2 IN2  →  Motor 3 (RL) yön B

Pi GPIO27 (Pin 13) ──┬── L298N #1 IN3  →  Motor 2 (FR) yön A
                     └── L298N #2 IN3  →  Motor 4 (RR) yön A

Pi GPIO22 (Pin 15) ──┬── L298N #1 IN4  →  Motor 2 (FR) yön B
                     └── L298N #2 IN4  →  Motor 4 (RR) yön B

Pi GPIO12 (Pin 32) ──┬── L298N #1 ENA  →  Motor 1 (FL) hız
                     └── L298N #2 ENA  →  Motor 3 (RL) hız

Pi GPIO13 (Pin 33) ──┬── L298N #1 ENB  →  Motor 2 (FR) hız
                     └── L298N #2 ENB  →  Motor 4 (RR) hız
```

### L298N Yön Tablosu (yazılım referansı — her iki sürücü için aynı)

| Hareket     | IN1 | IN2 | IN3 | IN4 | Etki                                |
|-------------|:---:|:---:|:---:|:---:|-------------------------------------|
| İleri       | H   | L   | H   | L   | Motor 1+3 ileri, Motor 2+4 ileri    |
| Geri        | L   | H   | L   | H   | Motor 1+3 geri, Motor 2+4 geri      |
| Sol dönüş   | L   | H   | H   | L   | Motor 1+3 geri, Motor 2+4 ileri     |
| Sağ dönüş   | H   | L   | L   | H   | Motor 1+3 ileri, Motor 2+4 geri     |
| Dur         | L   | L   | L   | L   | Tüm motorlar durur                  |

### Teker Enkoderleri

| Enkoder       | Motor             | GPIO    | Header Pin | VCC   |
|---------------|:-----------------:|:-------:|:----------:|:-----:|
| Sol enkoder   | Motor 1 (FL)      | GPIO6   | Pin 31     | 3.3V  |
| Sağ enkoder   | Motor 2 (FR)      | GPIO7   | Pin 26     | 3.3V  |

- Enkoder sinyali 3.3V uyumlu — voltaj bölücü yok
- Yazılımda interrupt tabanlı sayım (`GPIO.RISING` edge)
- Hız hesabı: `pulse_sayısı / saniye × tekerlek_çevresi`

---

## 6. Sensör Bağlantı Detayları

### HC-SR04 Ultrasonik (×3)

| Pin     | Ön Sensör    | Sağ Sensör   | Sol Sensör   |
|---------|:------------:|:------------:|:------------:|
| VCC     | 5V rayı      | 5V rayı      | 5V rayı      |
| GND     | GND rayı     | GND rayı     | GND rayı     |
| TRIG    | GPIO23       | GPIO25       | GPIO20       |
| ECHO    | GPIO24 (bölücü) | GPIO21 (bölücü) | GPIO16 (bölücü) |

- İki sensörü aynı anda tetikleme — crosstalk olur
- Timeout: 50ms | Mesafe hesabı: `süre_µs / 58.0` cm
- Hata dönüş değeri: `-1.0` (timeout veya >400cm)

### MLX90614 IR Termometre

| Pin | Bağlantı         |
|-----|------------------|
| VCC | 3.3V (Pin 1)     |
| GND | GND (Pin 9)      |
| SDA | GPIO2 (Pin 3)    |
| SCL | GPIO3 (Pin 5)    |

- I²C adresi: `0x5A`
- Kablo max 20cm — uzunsa bus kilitlenir
- GY-906 modülünde pull-up dirençleri mevcut, ekstra gerekmez

### MCP3008 ADC (DIP-16)

| MCP3008 Pin | No  | Bağlantı            |
|-------------|:---:|---------------------|
| VDD         | 16  | 3.3V rayı           |
| VREF        | 15  | 3.3V rayı           |
| AGND        | 14  | GND rayı            |
| CLK         | 13  | GPIO11 (Pin 23)     |
| DOUT        | 12  | GPIO9 (Pin 21) MISO |
| DIN         | 11  | GPIO10 (Pin 19) MOSI|
| CS/SHDN     | 10  | GPIO5 (Pin 29)      |
| DGND        | 9   | GND rayı            |
| CH0         | 1   | MQ-2 AOUT           |
| CH1–CH7     | 2–8 | Boşta               |

- Çentik (notch) yukarı bakacak şekilde yerleştir
- Pin 1 = sol üst köşe = CH0

### MQ-2 Gaz/Duman Sensörü

| Pin  | Bağlantı           |
|------|--------------------|
| VCC  | 5V rayı            |
| GND  | GND rayı           |
| AOUT | MCP3008 CH0 (Pin 1)|
| DOUT | Bağlı değil        |

---

## 7. Alarm ve Yardımcı Bileşenler

### Alarm LED

```
GPIO26 (Pin 37) ──→ [330Ω] ──→ LED Anot (+) ──→ LED Katot (−) ──→ GND
```

### Aktif Buzzer

```
GPIO19 (Pin 35) ──→ Buzzer (+)
GND             ──→ Buzzer (−)
```

### Soğutucu Fan

```
Pi Pin 4 (5V) ──→ Fan Kırmızı (+)
Pi Pin 6 (GND) ──→ Fan Siyah (−)
```

### USB Kamera (Logitech C270)

```
C270 USB-A ──→ Pi USB 2.0 portu (siyah port)
OpenCV device: /dev/video0
Çözünürlük: 320×320 (inference), 640×480 (snapshot)
```

---

## 8. Bus Konfigürasyonları

### I²C

```
/dev/i2c-1
SDA = GPIO2 | SCL = GPIO3
Cihaz: MLX90614 @ 0x5A
Kontrol: i2cdetect -y 1
```

### SPI

```
/dev/spidev0.0
CLK=GPIO11 | MOSI=GPIO10 | MISO=GPIO9 | CS=GPIO5 (yazılımsal)
Cihaz: MCP3008 CH0=MQ-2
Not: GPIO8 (HW CE0) kernel tarafından SPI için tutulabilir.
     HC-SR04 sağ ECHO GPIO21'e taşındı; spidev no_cs=True + GPIO5 yazılımsal CS kullan.
```

---

## 9. Kritik Uyarılar

| # | Uyarı |
|---|-------|
| 1 | HC-SR04 ECHO pinleri **5V çıkış** üretir. Bölücüsüz GPIO'ya bağlama — Pi yanar. |
| 2 | LM2596 çıkışını Pi'ye bağlamadan önce multimetreyle **5.00V** olduğunu doğrula. |
| 3 | Her iki L298N üzerindeki **ENA ve ENB jumper'larını çıkar** — yazılım PWM kullanıyor. |
| 4 | Her iki L298N **"5V" terminali boşta** — onboard regülatör kullanılmıyor. |
| 11 | İki L298N'in IN/EN pinleri **paralel bağlı** — kablo kopuklarında tek taraf çalışmayı bırakır, kontrol et. |
| 5 | MLX90614 kablosu **max 20cm** — uzunsa I²C bus kilitlenir. |
| 6 | MQ-2 açılışta **60 saniye ısınma** bekle — ilk okumalar geçersiz. |
| 7 | MCP3008 **çentik yukarı** bakacak şekilde takılmalı — ters takılırsa yanar. |
| 8 | Tüm GND'ler **tek ortak ray** üzerinde birleşmeli. |
| 9 | İki HC-SR04'ü **aynı anda tetikleme** — ardışık okuma yap. |
| 10 | GPIO8 SPI CE0 kernel tarafından tutulabilir — sensör ECHO hattında kullanma. Sağ ECHO GPIO21'e taşındı. |

---

## 10. Başlangıç Kontrol Listesi

```
[ ] LiPo voltajı ölçüldü (7.0V üzeri)
[ ] LM2596 çıkışı 5.00V kalibre edildi
[ ] Ön L298N (#1) ENA/ENB jumper'ları çıkarıldı
[ ] Arka L298N (#2) ENA/ENB jumper'ları çıkarıldı
[ ] Her iki L298N 5V terminali boşta
[ ] Motor 1 (FL) → L298N #1 OUT1/OUT2 bağlı
[ ] Motor 2 (FR) → L298N #1 OUT3/OUT4 bağlı
[ ] Motor 3 (RL) → L298N #2 OUT1/OUT2 bağlı
[ ] Motor 4 (RR) → L298N #2 OUT3/OUT4 bağlı
[ ] 6 sinyal kablosu (IN1-4 + ENA + ENB) her iki L298N'e paralel bağlı
[ ] Her iki L298N VS → 7.4V rayı bağlı
[ ] Her iki L298N GND → ortak GND rayı bağlı
[ ] 3 adet HC-SR04 ECHO bölücü devresi kuruldu ve ~3.18V ölçüldü
[ ] MCP3008 çentik yönü doğru
[ ] MLX90614 i2cdetect ile 0x5A adresinde görünüyor
[ ] Ortak GND rayı tüm bileşenlere ulaşıyor
[ ] Anahtar kapatıldığında sistem güç alıyor
[ ] Anahtar açıldığında sistem güçsüz kalıyor
```

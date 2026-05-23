# SeeFire — Fiziksel Kablolama Planı

**Proje:** SeeFire Yangın Tespit Robotu | **Grup:** Group 4 | **Ders:** CSE 396 Spring 2025-2026  
**Platform:** Raspberry Pi 4 | **Şasi:** 4WD Çift Katlı Akrilik | **Batarya:** LiPo 2S 7.4V 2200mAh

---

## 1. Python Pin Sabitleri (config.py)

```python
# ════════════════════════════════════════════════════════
#  SeeFire — Donanım Pin Sabitleri (BCM numaralandırması)
# ════════════════════════════════════════════════════════

# ── Motor Sürücü (L298N) ─────────────────────────────────────────
PIN_IN1 = 17      # Sol motor yön A
PIN_IN2 = 18      # Sol motor yön B
PIN_IN3 = 27      # Sağ motor yön A
PIN_IN4 = 22      # Sağ motor yön B
PIN_ENA = 12      # Sol motor PWM (hardware PWM)
PIN_ENB = 13      # Sağ motor PWM (hardware PWM)

# ── Teker Enkoderleri (2 adet — RL ve RR motorları) ──────────────
PIN_ENC_LEFT  = 4   # Sol enkoder sinyal (RL motoru)
PIN_ENC_RIGHT = 7   # Sağ enkoder sinyal (RR motoru)
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
| 7          | GPIO4    | IN    | Enkoder sol (RL motoru)    | Dijital      |
| 9          | —        | GND   | MLX90614 GND               | —            |
| 11         | GPIO17   | OUT   | L298N IN1 — sol yön A      | Dijital      |
| 12         | GPIO18   | OUT   | L298N IN2 — sol yön B      | Dijital      |
| 13         | GPIO27   | OUT   | L298N IN3 — sağ yön A      | Dijital      |
| 14         | —        | GND   | Genel GND                  | —            |
| 15         | GPIO22   | OUT   | L298N IN4 — sağ yön B      | Dijital      |
| 16         | GPIO23   | OUT   | HC-SR04 ön TRIG            | Dijital      |
| 17         | —        | OUT   | Breadboard 3.3V rayı       | 3.3V güç     |
| 18         | GPIO24   | IN    | HC-SR04 ön ECHO (bölücüden)| Dijital      |
| 19         | GPIO10   | OUT   | MCP3008 DIN (MOSI)         | SPI          |
| 20         | —        | GND   | MCP3008 AGND/DGND          | —            |
| 21         | GPIO9    | IN    | MCP3008 DOUT (MISO)        | SPI          |
| 22         | GPIO25   | OUT   | HC-SR04 sağ TRIG           | Dijital      |
| 23         | GPIO11   | OUT   | MCP3008 CLK (SCLK)         | SPI          |
| 25         | —        | GND   | Genel GND                  | —            |
| 26         | GPIO7    | IN    | Enkoder sağ (RR motoru)    | Dijital      |
| 29         | GPIO5    | OUT   | MCP3008 CS/SHDN            | SPI (yazılımsal CS) |
| 32         | GPIO12   | OUT   | L298N ENA — sol PWM        | PWM (1kHz)   |
| 33         | GPIO13   | OUT   | L298N ENB — sağ PWM        | PWM (1kHz)   |
| 34         | —        | GND   | Buzzer (−)                 | —            |
| 35         | GPIO19   | OUT   | Aktif buzzer (+)           | Dijital      |
| 36         | GPIO16   | IN    | HC-SR04 sol ECHO (bölücüden)| Dijital     |
| 37         | GPIO26   | OUT   | Alarm LED (330Ω seri)      | Dijital      |
| 38         | GPIO20   | OUT   | HC-SR04 sol TRIG           | Dijital      |
| 40         | GPIO21   | IN    | HC-SR04 sağ ECHO (bölücüden)| Dijital     |

### Boşta Kalan GPIO Pinleri

| Header Pin | BCM GPIO | Not                          |
|:----------:|:--------:|------------------------------|
| 27         | GPIO0    | I²C ID EEPROM — dokunma      |
| 28         | GPIO1    | I²C ID EEPROM — dokunma      |
| 31         | GPIO6    | Serbest                      |
| 24         | GPIO8    | SPI CE0 — sensör için kullanma |

---

## 3. Güç Hattı Topolojisi

```
LiPo 2S 7.4V
    │
    ├─ (+) ──→ [Anahtar] ──→ [Sigorta 5-10A] ──→ Breadboard (+) rayı
    │                                                     │
    │                                        ┌────────────┴────────────┐
    │                                        │                         │
    │                                   L298N VS                  LM2596 IN+
    │                                   (motor güç)               (7.4V giriş)
    │                                                                   │
    │                                                            LM2596 OUT+
    │                                                            (5.00V — kalibreli)
    │                                                                   │
    │                                                          Pi Header Pin 4
    │
    └─ (−) ──→ Breadboard GND rayı (ortak toprak)
                     │
        ┌────────────┼────────────┬──────────────┐
        │            │            │              │
    L298N GND   LM2596 OUT−   Pi Pin 6       Tüm sensör
                                              GND'leri
```

**Güç Rayları (breadboard):**

| Ray       | Kaynak               | Besledikleri                                  |
|-----------|----------------------|-----------------------------------------------|
| (+) 7.4V  | LiPo → Anahtar → Sigorta | L298N VS, LM2596 IN+                    |
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

### L298N Motor Çıkışları

| L298N Çıkışı | Bağlı Motorlar          | Birleştirme  |
|:------------:|-------------------------|:------------:|
| OUT1         | Motor FL (+) + Motor RL (+) | Paralel lehim |
| OUT2         | Motor FL (−) + Motor RL (−) | Paralel lehim |
| OUT3         | Motor FR (+) + Motor RR (+) | Paralel lehim |
| OUT4         | Motor FR (−) + Motor RR (−) | Paralel lehim |

### L298N Yön Tablosu (yazılım referansı)

| Hareket     | IN1 | IN2 | IN3 | IN4 |
|-------------|:---:|:---:|:---:|:---:|
| İleri       | H   | L   | H   | L   |
| Geri        | L   | H   | L   | H   |
| Sol dönüş   | L   | H   | H   | L   |
| Sağ dönüş  | H   | L   | L   | H   |
| Dur         | L   | L   | L   | L   |

### Teker Enkoderleri

| Enkoder       | Motor | GPIO    | Header Pin | VCC   |
|---------------|:-----:|:-------:|:----------:|:-----:|
| Sol enkoder   | RL    | GPIO4   | Pin 7      | 3.3V  |
| Sağ enkoder   | RR    | GPIO7   | Pin 26     | 3.3V  |

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
| 3 | L298N üzerindeki **ENA ve ENB jumper'larını çıkar** — yazılım PWM kullanıyor. |
| 4 | L298N **"5V" terminali boşta** — onboard regülatör kullanılmıyor. |
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
[ ] L298N ENA/ENB jumper'ları çıkarıldı
[ ] L298N 5V terminali boşta
[ ] 3 adet HC-SR04 ECHO bölücü devresi kuruldu ve ~3.18V ölçüldü
[ ] MCP3008 çentik yönü doğru
[ ] MLX90614 i2cdetect ile 0x5A adresinde görünüyor
[ ] Ortak GND rayı tüm bileşenlere ulaşıyor
[ ] Anahtar kapatıldığında sistem güç alıyor
[ ] Anahtar açıldığında sistem güçsüz kalıyor
```

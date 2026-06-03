# SeeFire — Fiziksel Kablolama Planı (v2 — Çift L298N)

**Proje:** SeeFire Yangın Tespit Robotu | **Grup:** Group 4 | **Ders:** CSE 396 Spring 2025-2026  
**Platform:** Raspberry Pi 4 | **Şasi:** 4WD Çift Katlı Akrilik | **Batarya:** LiPo 2S 7.4V 2200mAh

---

## 1. Python Pin Sabitleri (config.py)

```python
# ════════════════════════════════════════════════════════
#  SeeFire — Donanım Pin Sabitleri (BCM numaralandırması)
# ════════════════════════════════════════════════════════

# ── Motor Sürücü (L298N #1 Ön + L298N #2 Arka — paralel) ────────
PIN_IN1 = 17      # Sol motor yön A  → her iki L298N IN1
PIN_IN2 = 18      # Sol motor yön B  → her iki L298N IN2
PIN_IN3 = 27      # Sağ motor yön A  → her iki L298N IN3
PIN_IN4 = 22      # Sağ motor yön B  → her iki L298N IN4
PIN_ENA = 12      # Sol PWM          → her iki L298N ENA
PIN_ENB = 13      # Sağ PWM          → her iki L298N ENB

# ── Teker Enkoderleri (2 adet — RL ve RR motorları) ──────────────
PIN_ENC_LEFT  = 6    # Sol enkoder (RL motoru) — GPIO6 (Pin 31)
PIN_ENC_RIGHT = 7    # Sağ enkoder (RR motoru) — GPIO7 (Pin 26)
# VCC: 3.3V  |  GND: GND  |  Sinyal: 3.3V uyumlu (bölücü yok)

# ── HC-SR04 Ultrasonik Sensörler ─────────────────────────────────
PIN_TRIG_FRONT = 23  # Ön sensör tetik
PIN_ECHO_FRONT = 24  # Ön sensör yankı  (voltaj bölücüden ~3.18V)
PIN_TRIG_RIGHT = 25  # Sağ sensör tetik
PIN_ECHO_RIGHT = 21  # Sağ sensör yankı (voltaj bölücüden ~3.18V)
PIN_TRIG_LEFT  = 20  # Sol sensör tetik
PIN_ECHO_LEFT  = 16  # Sol sensör yankı (voltaj bölücüden ~3.18V)
# VCC: 5V  |  TRIG: direkt GPIO  |  ECHO: 1kΩ+2kΩ bölücüden GPIO

# ── MLX90614 IR Termometre (I²C) ─────────────────────────────────
I2C_BUS       = 1       # /dev/i2c-1
MLX90614_ADDR = 0x5A    # I²C adresi
# SDA: GPIO2 (Pin 3)  |  SCL: GPIO3 (Pin 5)  |  VCC: 3.3V

# ── MCP3008 ADC (SPI) ────────────────────────────────────────────
SPI_BUS    = 0          # /dev/spidev0.0
SPI_DEVICE = 0
PIN_SPI_CS = 5          # Yazılımsal CS — GPIO5 (Pin 29)
# CLK: GPIO11 (Pin 23)  |  MISO: GPIO9 (Pin 21)  |  MOSI: GPIO10 (Pin 19)
# VDD: 3.3V  |  VREF: 3.3V  |  AGND: GND  |  DGND: GND

# ── MQ-2 Gaz/Duman Sensörü ───────────────────────────────────────
MQ2_CHANNEL    = 0      # MCP3008 CH0
MQ2_WARMUP_SEC = 60     # Açılışta bekleme süresi (saniye)
MQ2_THRESHOLD  = 300    # Ham ADC alarm eşiği (0–1023)
# VCC: 5V  |  GND: GND  |  AOUT → MCP3008 CH0  |  DOUT: bağlı değil

# ── Alarm ─────────────────────────────────────────────────────────
PIN_LED    = 26         # Alarm LED — 330Ω seri (Pin 37)
PIN_BUZZER = 19         # Aktif buzzer (Pin 35)
```

---

## 2. GPIO Tam Atama Tablosu

> Tüm GPIO numaraları BCM. Header Pin = Pi'deki fiziksel pin.

| Header Pin | BCM GPIO | Yön | Bağlı Bileşen | Protokol |
|:---:|:---:|:---:|---|:---:|
| 1  | —      | OUT | MLX90614 VCC · MCP3008 VDD/VREF | 3.3V güç |
| 2  | —      | OUT | HC-SR04 ×3 VCC · MQ-2 VCC | 5V güç |
| 3  | GPIO2  | I/O | MLX90614 SDA | I²C |
| 4  | —      | OUT | LM2596 OUT+ (Pi besleme) | 5V güç |
| 5  | GPIO3  | I/O | MLX90614 SCL | I²C |
| 6  | —      | GND | Fan (−) · Genel GND | — |
| 9  | —      | GND | MLX90614 GND | — |
| 11 | GPIO17 | OUT | L298N #1+#2 IN1 — sol yön A | Dijital |
| 12 | GPIO18 | OUT | L298N #1+#2 IN2 — sol yön B | Dijital |
| 13 | GPIO27 | OUT | L298N #1+#2 IN3 — sağ yön A | Dijital |
| 14 | —      | GND | Genel GND | — |
| 15 | GPIO22 | OUT | L298N #1+#2 IN4 — sağ yön B | Dijital |
| 16 | GPIO23 | OUT | HC-SR04 ön TRIG | Dijital |
| 17 | —      | OUT | Breadboard 3.3V rayı | 3.3V güç |
| 18 | GPIO24 | IN  | HC-SR04 ön ECHO (bölücüden) | Dijital |
| 19 | GPIO10 | OUT | MCP3008 DIN (MOSI) | SPI |
| 20 | —      | GND | MCP3008 AGND/DGND | — |
| 21 | GPIO9  | IN  | MCP3008 DOUT (MISO) | SPI |
| 22 | GPIO25 | OUT | HC-SR04 sağ TRIG | Dijital |
| 23 | GPIO11 | OUT | MCP3008 CLK (SCLK) | SPI |
| 25 | —      | GND | Genel GND | — |
| 26 | GPIO7  | IN  | Enkoder sağ (RR motoru) | Dijital |
| 29 | GPIO5  | OUT | MCP3008 CS/SHDN | SPI yazılımsal |
| 31 | GPIO6  | IN  | Enkoder sol (RL motoru) | Dijital |
| 32 | GPIO12 | OUT | L298N #1+#2 ENA — sol PWM | PWM 1kHz |
| 33 | GPIO13 | OUT | L298N #1+#2 ENB — sağ PWM | PWM 1kHz |
| 34 | —      | GND | Buzzer (−) | — |
| 35 | GPIO19 | OUT | Aktif buzzer (+) | Dijital |
| 36 | GPIO16 | IN  | HC-SR04 sol ECHO (bölücüden) | Dijital |
| 37 | GPIO26 | OUT | Alarm LED (330Ω seri) | Dijital |
| 38 | GPIO20 | OUT | HC-SR04 sol TRIG | Dijital |
| 40 | GPIO21 | IN  | HC-SR04 sağ ECHO (bölücüden) | Dijital |

### Güç Pinleri

| Header Pin | Fonksiyon | Bağlı Bileşen |
|:---:|---|---|
| Pin 1  | 3.3V çıkış | MLX90614 VCC · MCP3008 VDD+VREF · Enkoder VCC |
| Pin 2  | 5V çıkış   | HC-SR04 ×3 VCC · MQ-2 VCC |
| Pin 4  | 5V çıkış   | LM2596 OUT+ bağlantı noktası (Pi ana besleme) |
| Pin 6  | GND        | Fan (−) |
| Pin 9  | GND        | MLX90614 GND |
| Pin 14 | GND        | Breadboard GND yedek |
| Pin 17 | 3.3V çıkış | Breadboard 3.3V rayı |
| Pin 20 | GND        | MCP3008 AGND/DGND |
| Pin 25 | GND        | Genel yedek |
| Pin 34 | GND        | Buzzer (−) |

### Boşta Kalan Pinler

| Header Pin | BCM GPIO | Not |
|:---:|:---:|---|
| 7  | GPIO4 | Serbest |
| 24 | GPIO8 | SPI CE0 — kullanma (kernel tutar) |
| 27 | GPIO0 | I²C ID EEPROM — dokunma |
| 28 | GPIO1 | I²C ID EEPROM — dokunma |

---

## 3. Güç Hattı Topolojisi

```
LiPo 2S 7.4V
    │
    ├─ (+) ──→ [Anahtar] ──→ [Sigorta 5-10A] ──→ Breadboard (+) rayı
    │                                                      │
    │                                       ┌──────────────┴──────────────┐
    │                                       │                             │
    │                                 L298N #1 VS                    LM2596 IN+
    │                                 L298N #2 VS                    (7.4V giriş)
    │                                 (motor güç)                         │
    │                                                              LM2596 OUT+
    │                                                              (5.00V kalibreli)
    │                                                                     │
    │                                                           Pi Header Pin 4
    │
    └─ (−) ──→ Breadboard GND rayı (ortak toprak)
                      │
         ┌────────────┼──────────────┬──────────────┐
         │            │              │              │
    L298N #1 GND  L298N #2 GND  LM2596 OUT−    Pi Pin 6
    + tüm sensör GND'leri
```

### Güç Rayları

| Ray | Kaynak | Besledikleri |
|---|---|---|
| (+) 7.4V | LiPo → Anahtar → Sigorta | L298N #1 VS · L298N #2 VS · LM2596 IN+ |
| 5V | Pi Pin 2 veya Pin 4 | HC-SR04 ×3 VCC · MQ-2 VCC · Fan (+) |
| 3.3V | Pi Pin 1 veya Pin 17 | MLX90614 VCC · MCP3008 VDD+VREF · Enkoder VCC |
| GND | LiPo (−) | Her şeyin GND'si — ortak toprak |

---

## 4. Çift L298N Motor Bağlantıları

### Motor Tanımları

| Motor No | Pozisyon | Kısaltma |
|:---:|---|:---:|
| Motor 1 | Ön Sol | FL |
| Motor 2 | Ön Sağ | FR |
| Motor 3 | Arka Sol | RL |
| Motor 4 | Arka Sağ | RR |

---

### L298N #1 — Ön Sürücü (Motor 1 FL + Motor 2 FR)

**Motor çıkışları:**

| L298N #1 | Bağlantı |
|:---:|---|
| OUT1 | Motor 1 (FL) — tel A |
| OUT2 | Motor 1 (FL) — tel B |
| OUT3 | Motor 2 (FR) — tel A |
| OUT4 | Motor 2 (FR) — tel B |

**Kontrol girişleri:**

| L298N #1 | GPIO | Header Pin | Fonksiyon |
|:---:|:---:|:---:|---|
| ENA | GPIO12 | Pin 32 | Motor 1 hız (PWM) |
| IN1 | GPIO17 | Pin 11 | Sol yön A |
| IN2 | GPIO18 | Pin 12 | Sol yön B |
| IN3 | GPIO27 | Pin 13 | Sağ yön A |
| IN4 | GPIO22 | Pin 15 | Sağ yön B |
| ENB | GPIO13 | Pin 33 | Motor 2 hız (PWM) |

**Güç:**

| L298N #1 Terminali | Bağlantı |
|:---:|---|
| VCC (12V) | Breadboard (+) rayı 7.4V |
| GND | Breadboard GND rayı |
| 5V | ⚠️ Boşta — bağlama |

> ENA ve ENB jumper'larını çıkar.

---

### L298N #2 — Arka Sürücü (Motor 3 RL + Motor 4 RR)

**Motor çıkışları:**

| L298N #2 | Bağlantı |
|:---:|---|
| OUT1 | Motor 3 (RL) — tel A |
| OUT2 | Motor 3 (RL) — tel B |
| OUT3 | Motor 4 (RR) — tel A |
| OUT4 | Motor 4 (RR) — tel B |

**Kontrol girişleri — Ön sürücüyle aynı GPIO'lara paralel:**

| L298N #2 | GPIO | Header Pin | Fonksiyon |
|:---:|:---:|:---:|---|
| ENA | GPIO12 | Pin 32 | Motor 3 hız (PWM) — paralel |
| IN1 | GPIO17 | Pin 11 | Sol yön A — paralel |
| IN2 | GPIO18 | Pin 12 | Sol yön B — paralel |
| IN3 | GPIO27 | Pin 13 | Sağ yön A — paralel |
| IN4 | GPIO22 | Pin 15 | Sağ yön B — paralel |
| ENB | GPIO13 | Pin 33 | Motor 4 hız (PWM) — paralel |

**Güç:**

| L298N #2 Terminali | Bağlantı |
|:---:|---|
| VCC (12V) | Breadboard (+) rayı 7.4V |
| GND | Breadboard GND rayı |
| 5V | ⚠️ Boşta — bağlama |

> ENA ve ENB jumper'larını çıkar.

---

### Paralel Sinyal Şeması

```
Pi Pin 32 GPIO12 ──┬── L298N #1 ENA  →  Motor 1 (FL) hız
                   └── L298N #2 ENA  →  Motor 3 (RL) hız

Pi Pin 11 GPIO17 ──┬── L298N #1 IN1  →  Motor 1+3 yön A
                   └── L298N #2 IN1

Pi Pin 12 GPIO18 ──┬── L298N #1 IN2  →  Motor 1+3 yön B
                   └── L298N #2 IN2

Pi Pin 13 GPIO27 ──┬── L298N #1 IN3  →  Motor 2+4 yön A
                   └── L298N #2 IN3

Pi Pin 15 GPIO22 ──┬── L298N #1 IN4  →  Motor 2+4 yön B
                   └── L298N #2 IN4

Pi Pin 33 GPIO13 ──┬── L298N #1 ENB  →  Motor 2 (FR) hız
                   └── L298N #2 ENB  →  Motor 4 (RR) hız
```

### Hareket Doğrulama Tablosu

| Hareket | Motor 1 FL | Motor 2 FR | Motor 3 RL | Motor 4 RR |
|---|:---:|:---:|:---:|:---:|
| İleri | ↑ | ↑ | ↑ | ↑ |
| Geri | ↓ | ↓ | ↓ | ↓ |
| Sola dön | ↓ | ↑ | ↓ | ↑ |
| Sağa dön | ↑ | ↓ | ↑ | ↓ |
| Dur | — | — | — | — |

---

## 5. Voltaj Bölücü Devreleri (HC-SR04 ECHO)

HC-SR04 ECHO 5V çıkış üretir. Pi GPIO max 3.3V tolere eder.  
3 sensör = 3 ayrı bölücü devre. Ölçülen çıkış: **~3.18V ✓**

```
HC-SR04 ECHO (5V)
        │
       [1kΩ]
        │
        ├─────── GPIO (Pi)
        │
       [2kΩ]
        │
       GND
```

| Sensör | ECHO → GPIO | Header Pin |
|---|:---:|:---:|
| Ön | GPIO24 | Pin 18 |
| Sağ | GPIO21 | Pin 40 |
| Sol | GPIO16 | Pin 36 |

---

## 6. Enkoder Bağlantıları

| Enkoder | Motor | GPIO | Header Pin | VCC |
|---|:---:|:---:|:---:|:---:|
| Sol | RL (Motor 3) | GPIO6 | Pin 31 | 3.3V |
| Sağ | RR (Motor 4) | GPIO7 | Pin 26 | 3.3V |

- Sinyal 3.3V uyumlu — voltaj bölücü yok
- Yazılımda interrupt: `GPIO.RISING` edge
- Hız: `pulse/sn × tekerlek çevresi (π × 65mm)`

---

## 7. Sensör Bağlantıları

### HC-SR04 Ultrasonik (×3)

| Pin | Ön | Sağ | Sol |
|---|:---:|:---:|:---:|
| VCC | 5V rayı | 5V rayı | 5V rayı |
| GND | GND rayı | GND rayı | GND rayı |
| TRIG | GPIO23 | GPIO25 | GPIO20 |
| ECHO | GPIO24 (bölücü) | GPIO21 (bölücü) | GPIO16 (bölücü) |

### MLX90614 IR Termometre

| Pin | Bağlantı |
|---|---|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 9) |
| SDA | GPIO2 (Pin 3) |
| SCL | GPIO3 (Pin 5) |

### MCP3008 ADC (DIP-16)

| MCP3008 Pin | No | Bağlantı |
|---|:---:|---|
| VDD | 16 | 3.3V rayı |
| VREF | 15 | 3.3V rayı |
| AGND | 14 | GND rayı |
| CLK | 13 | GPIO11 (Pin 23) |
| DOUT | 12 | GPIO9 (Pin 21) |
| DIN | 11 | GPIO10 (Pin 19) |
| CS | 10 | GPIO5 (Pin 29) |
| DGND | 9 | GND rayı |
| CH0 | 1 | MQ-2 AOUT |

### MQ-2

| Pin | Bağlantı |
|---|---|
| VCC | 5V rayı |
| GND | GND rayı |
| AOUT | MCP3008 CH0 |
| DOUT | Bağlı değil |

---

## 8. Alarm ve Yardımcı Bileşenler

```
Alarm LED:  GPIO26 (Pin 37) → [330Ω] → LED Anot → LED Katot → GND
Buzzer:     GPIO19 (Pin 35) → Buzzer(+)  |  Buzzer(−) → GND (Pin 34)
Fan:        Pin 4 (5V)      → Fan(+)     |  Fan(−)    → Pin 6 (GND)
Kamera:     C270 USB-A      → Pi USB 2.0 portu (siyah port)
```

---

## 9. Bus Konfigürasyonları

```
I²C:  /dev/i2c-1  |  SDA=GPIO2  |  SCL=GPIO3  |  MLX90614@0x5A
      Test: i2cdetect -y 1

SPI:  /dev/spidev0.0  |  CLK=GPIO11  |  MOSI=GPIO10  |  MISO=GPIO9
      CS=GPIO5 (yazılımsal)  |  MCP3008 CH0=MQ-2
      Not: GPIO8 (HW CE0) kullanılmıyor — spidev no_cs=True kullan
```

---

## 10. Kritik Uyarılar

| # | Uyarı |
|:---:|---|
| 1 | HC-SR04 ECHO **5V çıkış** — bölücüsüz bağlama, Pi yanar |
| 2 | LM2596 çıkışını Pi'ye bağlamadan önce **5.00V** ölç |
| 3 | Her iki L298N'de **ENA/ENB jumper'larını çıkar** |
| 4 | Her iki L298N **5V terminali boşta** |
| 5 | MLX90614 kablosu **max 20cm** |
| 6 | MQ-2 açılışta **60 saniye** bekle |
| 7 | MCP3008 **çentik yukarı** — ters takılırsa yanar |
| 8 | Tüm GND'ler **tek ortak ray** üzerinde |
| 9 | HC-SR04'leri **aynı anda tetikleme** — crosstalk olur |
| 10 | **GPIO8 kullanma** — SPI CE0 kernel tarafından tutulur |
| 11 | Arka motorlar ters dönüyorsa L298N #2 **OUT kablolarını yer değiştir** |
| 12 | **Pi'yi USB-C ve LiPo ile aynı anda besleme** — 5V çarpışması |

---

## 11. Montaj Kontrol Listesi

```
[ ] LiPo voltajı ölçüldü (7.0V üzeri)
[ ] LM2596 çıkışı 5.00V kalibre edildi
[ ] L298N #1 ENA/ENB jumper'ları çıkarıldı
[ ] L298N #2 ENA/ENB jumper'ları çıkarıldı
[ ] L298N #1 ve #2 5V terminalleri boşta
[ ] L298N #1 ve #2 VS → 7.4V rayına bağlandı
[ ] L298N #1 ve #2 GND → ortak GND rayına bağlandı
[ ] Motor 1 FL → L298N #1 OUT1/OUT2
[ ] Motor 2 FR → L298N #1 OUT3/OUT4
[ ] Motor 3 RL → L298N #2 OUT1/OUT2
[ ] Motor 4 RR → L298N #2 OUT3/OUT4
[ ] L298N #1 ve #2 kontrol pinleri GPIO'lara paralel bağlandı
[ ] 3 adet HC-SR04 ECHO bölücü kuruldu (~3.18V ölçüldü ✓)
[ ] MCP3008 çentik yönü doğru
[ ] MLX90614 i2cdetect ile 0x5A görünüyor
[ ] Ortak GND tüm bileşenlere ulaşıyor
[ ] İleri harekette 4 motor aynı yönde döndü ✓
[ ] Dönüş testi yapıldı ✓
```

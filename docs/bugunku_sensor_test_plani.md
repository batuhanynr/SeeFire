# SeeFire Bugunku Sensor Test Plani

Tarih: 2026-05-23

Kaynak pin dokumani: `docs/Seefire Wiring Plan.md`

## Bugunku Hedef

Araca bagli ama eksik testi yapilacak sensorler:

| Bilesen | Baglanti | Beklenen |
|---|---|---|
| Teker enkoderleri | Sol `GPIO4`, sag `GPIO7` | Teker donunce pulse sayisi artar |
| USB kamera | `/dev/video0` | OpenCV frame alir, snapshot yazar |
| MLX90614 IR | I2C bus 1, adres `0x5A` | `i2cdetect` cihaz gorur, sicaklik okunur |

## On Kontrol

| Kontrol | Durum |
|---|---|
| LM2596 cikisi multimetre ile 5.00V | TODO |
| Tum GND hatlari ortak | TODO |
| L298N ENA/ENB jumperlari cikarildi | TODO |
| HC-SR04 ECHO boluculeri takili | TODO |
| Kamera USB 2.0 porta takili | TODO |
| MLX90614 kablosu 20cm altinda | TODO |

## Raspberry Komutlari

```bash
cd ~/SeeFire
python3 test_mocks.py
SEEFIRE_FORCE_MOCK=1 .venv/bin/python -m pytest
python3 hardware_sensor_check.py --all
```

Tek tek calistirma:

```bash
python3 hardware_sensor_check.py --encoders --encoder-seconds 10
python3 hardware_sensor_check.py --camera
python3 hardware_sensor_check.py --ir
```

## Kabul Kriteri

| Bilesen | PASS kosulu |
|---|---|
| Enkoder | Sol ve sag tick degeri `> 0` |
| Kamera | `/dev/video0` acilir, bos olmayan frame alinir |
| IR | `i2cdetect -y 1` ciktisinda `5a` gorulur, sicaklik okunur |

## Test Sonuclari

| Zaman | Test | Durum | Detay |
|---|---|---|---|
| 2026-05-23 15:01:58 | encoders | FAIL | `GPIO busy`; Pi `gpioinfo` GPIO7=`spi0 CS1`, GPIO8=`spi0 CS0` gosteriyor |
| 2026-05-23 15:01:58 | camera | FAIL | `/dev/video0` yok; sadece sistem video node'lari `/dev/video10+` gorunuyor |
| 2026-05-23 15:01:58 | ir_mlx90614 | FAIL | I2C bus 1 bos; `i2cdetect -y 1` ciktisinda `5a` yok, okuma `OSError: [Errno 5] Input/output error` |

## Tani ve Sonraki Is

| Blokaj | Muhtemel neden | Sonraki is |
|---|---|---|
| Enkoder GPIO busy | `/boot/firmware/config.txt` icinde `dtparam=spi=on`; kernel GPIO7/GPIO8'i SPI CE pinleri olarak tutuyor | Wiring plana uygun kalmak icin SPI CE pinlerini GPIO7/8'den ayir veya SPI'yi gecici kapat; reboot sonrasi enkoder testini tekrar calistir |
| Kamera yok | USB kamera takili degil veya farkli device olarak enumerate olmadi | Logitech C270 USB porta tak, `ls /dev/video*` icinde `/dev/video0` dogrula, sonra kamera testini tekrar calistir |
| IR yok | MLX90614 bagli degil, SDA/SCL/VCC/GND hatasi var veya I2C aktif cihaz gormuyor | SDA=GPIO2, SCL=GPIO3, VCC=3.3V, GND ortak kontrol; `i2cdetect -y 1` icinde `5a` gorulene kadar devam |

## Pin Guncellemesi

2026-05-23: Sag HC-SR04 ECHO, SPI CE0 cakismasi nedeniyle `GPIO8` yerine `GPIO21` olarak guncellendi.

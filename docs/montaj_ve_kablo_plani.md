# SeeFire Faz 2: Sensör ve Braket Yerleşim Planı

Bu döküman, Faz 2 kapsamında gerçekleştirilecek olan sensör montajı ve kablolama detaylarını içerir.

## 1. Ultrasonik Sensör Yerleşimi (HC-SR04)
Robotun engelleri algılaması ve mesafe düzeltmesi yapması için 3 adet HC-SR04 kullanılacaktır:
- **Ön Sensör (TRIG=16, ECHO=20):** Tam merkezde, engelleri doğrudan algılamak için.
- **Sol Sensör (TRIG=23, ECHO=24):** Robotun sol duvar mesafesini ölçmek ve şeritte kalmasını sağlamak için.
- **Sağ Sensör (TRIG=25, ECHO=8):** Sağ duvar mesafesini ölçmek ve engel kaçınma manevrasında referans almak için.

## 2. Termal ve Duman Sensörleri
- **MLX90614 (I2C):** Ön tarafta, duman sensörüyle aynı eksende. Pi'nin I2C pinlerine (SDA=2, SCL=3) bağlı.
- **MQ-2 (MCP3208 CH0):** Gaz ve duman algılaması için ön-üst kısımda konumlandırılacak.
- **MCP3208 (SPI):** Analog sensörleri (MQ-2 ve Batarya) Pi'ye bağlamak için kullanılır.

## 3. Kablolama ve Gerilim Bölücüler
- **HC-SR04 Echo Pinleri:** Pi GPIO pinleri 3.3V seviyesindedir, ancak HC-SR04 Echo çıkışı 5V'dur. Her Echo pini için 1kΩ ve 2kΩ dirençlerle **gerilim bölücü** devresi kurulmalıdır.
- **Batarya Takibi:** 2S Li-ion batarya (~8.4V max) voltajını ölçmek için MCP3208 CH1 girişine R1=20kΩ, R2=10kΩ gerilim bölücü üzerinden bağlantı yapılır.

## 4. Encoder Kurulumu
- **Sol Encoder:** GPIO 6
- **Sağ Encoder:** GPIO 21
- Encoder diskleri motor millerine sıkıca oturtulmalı ve optik sensörler disk deliklerini net görecek şekilde hizalanmalıdır.

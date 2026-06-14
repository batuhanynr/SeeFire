# SeeFire Web Dashboard

## 1. Dashboard'a Giriş

| Başlatma Komutu | Açıklama |
|---|---|
| `python3 -m web_dashboard` | Varsayılan port 5000'de başlatır |
| `python3 -m web_dashboard --port 5001` | Özel port ile başlatır |
| `python3 -m web_dashboard --mock-manual` | GPIO gerektirmeyen simülasyon modu |
| `python3 -m web_dashboard --manual-live` | Gerçek GPIO manuel sürüş modu (varsa) |

Ardından tarayıcıdan `http://<raspberry-pi-ip>:5000/` adresine gidilir. Backend Python stdlib (`http.server`) ile yazılmıştır, ek kütüphane gerektirmez. Arayüz dili **Türkçe**'dir.

---

## 2. Ana Bileşenler ve Göstergeler

### Üst Bilgi Çubuğu (Header)
- **Robot** rozeti — `main.py` prosesi çalışıyorsa yeşil "Robot ON", değilse kırmızı "Robot OFF"
- **DB** rozeti — M7 SQLite veritabanına bağlantı varsa yeşil "DB LIVE", yoksa kırmızı
- **Saat** — canlı sistem saati

### Kamera Bölümü
- MJPEG akışını gösteren `<img>` etiketi
- Varsayılan stream portu: **8080** (`SEEFIRE_STREAM_PORT` ile değiştirilebilir)
- Aktifleştirme: `SEEFIRE_STREAM=1 python3 main.py`
- Canlı değilse "Kamera akışı bekleniyor" placeholderi gösterilir
- Yangın tespit edildiğinde video üzerine **kırmızı badge** (ateş yüzdesi + yön) overlapi basılır

### Robot Durumu Kartı
Füzyon durum makinesinin 5 durumu:

| Durum | Anlamı | Renk |
|---|---|---|
| `INIT` | Sistem başlatılıyor | Mavi |
| `NAVIGATE` | Robot rota üzerinde ilerliyor | Yeşil |
| `VERIFY` | Risk yüksek, karar motoru doğrulama modunda | Turuncu |
| `ALARM` | Yangın alarmı aktif | Kırmızı |
| `STOP` | Robot durdu / görev sonlandı | Gri |

Altında **Hareket** satırı: manuel moddaysa gönderilen komut (`STOP / FORWARD / LEFT / RIGHT` vb.)

### Füzyon Skoru Kartı
- 0.0 – 1.0 arası skalada canlı çubuk
- Varsayılan alarm eşiği: **0.60** (`FUSION_ALARM_THRESH`)
- Temizlenme eşiği: **0.40** (`FUSION_CLEAR_THRESH`)
- Skor formülü: `(0.5 × vision) + (0.3 × smoke/4095) + (0.2 × temp/60.0)`

### 8 Sensör Telemetri Kartı

| Kart | Birim | Anlamı |
|---|---|---|
| 🌡️ **Sıcaklık** | °C | MLX90614 IR sensörü (eşik: 60°C) |
| 💨 **Duman (MQ-2)** | / 4095 | MQ-2 ADC değeri (eşik: 300) |
| 🔥 **Ateş (YOLO)** | % | YOLOv8n ateş tespit güven skoru (eşik: 0.25) |
| 📏 **Toplam Mesafe** | cm | Enkoderden hesaplanan katedilen yol |
| ⬆️ **Ön Mesafe** | cm | Ön HC-SR04 ultrasonik (engel eşiği: 30cm) |
| ↔️ **Sol / Sağ** | cm | Sol ve sağ HC-SR04 (başlangıç referansı: 200cm) |
| 🔋 **Batarya** | V | Gerilim (düşük: 6.8V, kritik: 6.4V) |
| ⚙️ **Motor L/R** | PWM | Sol/sağ motor PWM değerleri (0–100) |

### Olay Günlüğü Tablosu
- M7 SQLite veritabanından okunan son 30 olay
- Sütunlar: Zaman, Olay (badge'li), Füzyon, Duman, Sıcaklık, Ateş%
- Badge türleri: `Alarm` (kırmızı), `Kontrol` (turuncu), `Durdu` (gri), `Snapshot` (mavi), `Engel` (sarı)

### Snapshot Galerisi
- M7 tarafından kaydedilen JPEG görüntülerinin küçük resimleri
- Her karta: badge, başlık, zaman, füzyon skoru, ateş%, dosya boyutu
- Yeni sekmede açma desteği
- **Görüntüleri Temizle** butonu (toplu silme)

### Eşik Değerleri Paneli
- config.py'den okunan 12 parametre: duman eşiği, IR sıcaklık, vision conf, füzyon alarm/clear, engel mesafe, batarya düşük/kritik, füzyon ağırlıkları, sürüş hızı

---

## 3. Canlı Video İzleme

Dashboard, M4 modülüne gömülü **MJPEG stream sunucusu**na (`m4_vision/vision.py` içinde `_MjpegServer`) proxy yapar:

- **Port:** 8080 (env: `SEEFIRE_STREAM_PORT`)
- **Kare hızı:** 20 FPS (env: `SEEFIRE_STREAM_FPS`)
- **JPEG kalitesi:** 70 (env: `SEEFIRE_STREAM_JPEG_QUALITY`)
- **Aktifleştirme:** `SEEFIRE_STREAM=1` ortam değişkeni ile `main.py` başlatılır
- Stream adresi: `http://<ip>:8080/stream`
- Dashboard bu akışı `<img>` etiketi ile tarayıcıya gömer; sayfa yenilenmeden canlı kalır
- Hiçbir ek web framework (Flask, FastAPI vb.) kullanılmaz — tamamen Python stdlib

Dashboard otomatik olarak `status.stream_port` değerini okuyarak kamera img src'ini oluşturur.

---

## 4. Durum Kontrolü ve Manuel Sürüş

### Pasif İzleme Modu (varsayılan — `--mock-manual` veya `--manual-live` olmadan)
- Dashboard **salt okunur**dur
- M7 SQLite veritabanını saniyede bir poll ederek günceller
- Hiçbir GPIO'ya dokunmaz

### Mock Manuel Mod (`--mock-manual`)
- GPIO gerektirmez, herhangi bir geliştirme makinesinde çalışır
- Sanal sensör değerleri sinüs dalgası ile simüle edilir
- **Klavye kumandası:**
  - <kbd>W</kbd> — ileri
  - <kbd>S</kbd> — geri
  - <kbd>A</kbd> — sola dön (dururken tank pivot)
  - <kbd>D</kbd> — sağa dön (dururken tank pivot)
  - <kbd>W</kbd> + <kbd>A</kbd> — çapraz sol-ileri
  - <kbd>W</kbd> + <kbd>D</kbd> — çapraz sağ-ileri
  - <kbd>Space</kbd> — acil durdur
  - <kbd>P</kbd> — snapshot al

### Live Manuel Mod (`--manual-live`)
- Gerçek GPIO, motor ve sensörlerle çalışır
- `main.py` ile **aynı anda çalıştırılmamalıdır**
- Gazlama profili: `--manual-speed-level 1-25` ile ayarlanır (varsayılan 15 → ~%60 PWM)
- 450ms watchdog: son komuttan sonra 450ms geçerse otomatik STOP

### API Endpoint'leri (programatik erişim)

| Endpoint | Metot | Dönen |
|---|---|---|
| `/api/status` | GET | Sistem durumu, sensörler, füzyon skoru |
| `/api/events?limit=N` | GET | Son N olay |
| `/api/snapshots?limit=N` | GET | Snapshot listesi |
| `/api/config` | GET | config.py eşik değerleri |
| `/api/snapshot/<dosya>` | GET | JPEG dosyası |
| `/api/snapshots/clear` | POST | Tüm snapshot dosyalarını sil |
| `/api/manual/command` | POST | Manuel sürüş komutu (JSON: `{"command": "FORWARD"}`) |
| `/api/manual/snapshot` | POST | Manuel snapshot çek |

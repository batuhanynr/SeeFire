# SeeFire Projesi - Geliştirme Günlüğü (What We Did)

Bu dosya, projede yapılan geliştirme adımlarını, alınan kararları ve tarihsel ilerlemeyi kayıt altında tutmak amacıyla oluşturulmuştur.

---

## Tarih: 5 Mayıs 2026
**Geliştirici:** Bekir Emre Sarıpınar & GitHub Copilot

### Yapılan İşlemler:

**1. Proje Analizi ve Hedef Belirleme**
- `docs/` klasöründeki proje dokümanları (`SeeFire_Interface_report.md` ve PDF formatlı güncel raporlar) incelendi.
- Bekir Emre Sarıpınar'ın sorumluluğundaki modüllerin sınırları çizildi: **M2 (Motor Control & Power)** ve **M3 (Sensor Integration)**.

**2. Batarya Konfigürasyonu Güncellemesi (`config.py`)**
- Batarya tipinin 3S LiPo'dan, **2S 18650 Li-ion** (Maksimum 8.4V, Nominal 7.4V) hücreye geçirildiği bilgisi işlendi. 
- Gerçek voltaj okuması yapabilmek için gerekli "Voltaj Bölücü" (Voltage Divider) direnç değerleri (`VDIV_R1 = 20000.0`, `VDIV_R2 = 10000.0`) ve tehlike limitleri (`BATTERY_CRIT_V = 6.4V`) `config.py` içerisine eklendi.

**3. M2 ve M3 Modülleri İçin "Sanal Geliştirme (MOCK)" Altyapısının Kurulması**
- Fiziksel robot şasisi henüz elimizde olmadığı için kodların hatasız devam edebilmesi adına **MOCK_MODE** oluşturuldu. Mac/PC ortamında Raspberry Pi pinleri olmadan sistem simüle edildi.
- **`m2_motor/motor.py`:** Motor hız limitleri (0-100), yön fonksiyonları (`motor_drive`, `motor_turn`), `set_alarm` ve `get_battery_voltage` fonksiyonlarının sanal çıktıları/matematiği yazıldı ve ana log yapısına bağlandı.
- **`m3_sensors/sensors.py`:** Analog, I2C ve GPIO üzerinden okunan sensörler (HC-SR04, MQ-2, MLX) MOCK moda entegre edildi. Navigasyon (M5) modülü için rastgele/sanal engel mesafesi üreten bir iskelet kuruldu. `read_battery_adc()` çağrısı aktifleştirilip M2'ye entegre edildi.

**4. Modüller Arası Entegrasyon Testi**
- `test_mocks.py` dosyası ile sistem test edildi.
- M2'nin doğru matematik formülüyle, M3 modülü içerisindeki sanal ADC kanalından veriyi alıp `7.4V` okuyabildiği, sensörlerin sahte "16.8cm, 26.2cm" uzaklıklar döndürdüğü ve takımın diğer üyeleri (özellikle Navigation ve FSM ekipleri) için altyapının %100 hazır olduğu görüldü.

**5. Donanım ve Tasarım Değişiklikleri (Ahmet Furkan Tarafından Tamamlananlar)**
Bu bölümde, proje dokümantasyonu ile fiziksel gerçeklik arasındaki uyuşmazlıkları gidermek amacıyla belirtilen *kesinleşmiş* donanım değişiklikleri listelenmiştir:

* **SBC (Ana Kart):** Raspberry Pi 5 8GB'den vazgeçilip, **Raspberry Pi 4 4GB** kullanılmasına karar verildi.
* **Ultrasonik Sensör (HC-SR04):** Sensör sayısı 2'den **3'e çıkarıldı** (Ön, Sağ, Sol). Her bir Echo pini için 1kΩ + 2kΩ voltaj bölücü dirençleri eklendi. (Pin ataması `config.py` içine dahil edildi).
* **Güç Kaynağı:** 3S hazır LiPo yerine, **2S 18650 Li-ion Pack (2600 mAh, BMS'li)** hazırlandı ve XT60 Pigtail ile bağlantısı tamamlandı.
* **Kaldırılan Sensörler:** MPU6050 (IMU) ve DHT22 sensörleri stabilite ve proje kapsamına uygun olmaması sebebiyle tasarımdan tamamen **çıkartıldı**.
* **Eklenen Diğer Donanımlar:**
  - Aktif Soğutucu (Heatsink + Fan - YOLO yükü için).
  - USB-C Kablo (Buck converter'dan Pi'yi 5V beslemek için).
  - 8.4V Şarj Adaptörü ve Rocker Switch.

*(Not: Rapor PDF'leri, Appendix A GPIO Pin listesi, Malzeme Tablosu, Malzeme Riskleri ve config sabit limitleri de bu yeni güncellemeler doğrultusunda güncellenmiştir.)*

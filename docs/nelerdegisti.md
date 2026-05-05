# SeeFire Projesi - Plan ve Gerçekleşen Arasındaki Değişiklikler (Deviations from Original Report)

Bu belge, `SeeFire_Module_Documentation_Report.md` (ve ilgili PDF) dokümanında planlanan ilk tasarım ile mevcut **main** dalındaki güncel kod mimarisi ve donanım bileşenleri arasındaki farklılıkları listelemek için oluşturulmuştur. 

Yeni bir rapor yazılacağı zaman veya başka bir AI asistanı mevcut durumu analiz edeceği zaman **bu belgedeki bilgiler güncel doğru (source of truth)** olarak kabul edilmelidir.

---

## 1. Donanım ve Sensör Değişiklikleri (Hardware & Sensors)

| Bileşen | Orijinal Plan (Rapordaki) | Güncel Durum (Kodlanan) | Değişiklik Nedeni / Avantajı |
| :--- | :--- | :--- | :--- |
| **Ultrasonik Sensör** | 2 adet (Ön ve Sağ) | **3 adet** (Sol, Orta, Sağ) | Sadece duvar takibi yapmak yerine, robotun çevresindeki engelleri daha geniş bir açıyla (ön, sağ, sol) algılayıp sıkışmasını engellemek. |
| **ADC Entegresi** | MCP3008 (10-bit) | **MCP3208 (12-bit)** | M3 modülünde (MQ-2 ve Batarya) daha yüksek hassasiyet. Okuma değerleri 1023 üzerinden değil, 4095 üzerinden yapılıyor. |
| **Batarya & Voltaj** | LiPo 2S (Sadece Vcc beslemesi) | **2S (Li-ion/LiPo)** ve aktif voltaj izleme | Batarya sağlığını korumak için 20k/10k voltaj bölücü kullanıldı (max 8.4V). Kritik sınır (6.4V) altına düşünce M6 karar motoru "CRITICAL_STOP" durumuna geçiyor. |

---

## 2. Navigasyon ve Karar Mantığı (M5 & M6)

### 2.1. Keşif Stratejisi (Navigation Strategy)
*   **Eski Plan:** Sadece "Right-hand wall-following" (sağ duvarı takip ederek rastgele odada dolanma).
*   **Yeni Plan:** Alperen'in geliştirmeleri sonrası **"Sector-Based Traverse" (Sektör ve Rota Bazlı İlerleme)** mantığına geçildi.
*   **Nasıl Çalışır:** Robot belirli hedeflere (waypoints) sahip (`config.WAYPOINTS`). Robot bir sektörün içinde hareket ederken belirlenen **orta noktalarda (midpoint) kesinlikle durup fotoğraf çekiyor**. Engellerden (`ObstacleAvoidance`) kaçınsa bile bu orta noktaya geri dönmeye çalışıyor.

### 2.2. Sensör Filtreleme
*   Orijinal planda tekil okuma varken, güncel koda gürültü ve hatalı yankıları engellemek için **Medyan Filtreleme** eklendi. `get_navigation_sensors_filtered(samples=3)` fonksiyonu arka arkaya 3 ölçüm alıp ortadaki değeri kabul ederek çok daha stabil bir mesafe ölçümü sağlar.

---

## 3. Yazılım Mimarisi ve Geliştirme Ortamı

### 3.1. Mock Mode Mimarisi
*   Raporda sadece Raspberry Pi üzerinde çalışacak bir koddandan bahsediliyor. Ancak geliştirme sürecini hızlandırmak (ve farklı işletim sistemlerinde kod yazabilmek) için projeye çok kapsamlı bir **MOCK_MODE** eklendi.
*   `RPi.GPIO`, `smbus2`, `spidev` gibi Raspberry Pi'ye özgü kütüphaneler ortamda bulunmuyorsa, sistem çökmez. Bunların yerine rastgele sensör değerleri üreten simülasyon fonksiyonları devreye girer. Tüm modüller (M2, M3, vb.) bilgisayar üzerinde hiçbir donanım bağlı olmadan test edilebilir.

---

## Özet Olarak Sonraki Rapor İçin Notlar
1.  **Sistem mimarisi (M1'den M7'ye kadar modüller)** konsept olarak aynı kaldı. Ancak yazılımın çalışma şekli çok daha defansif, çevreyi daha iyi algılayan (3 sensör) ve planlı hareket eden (Waypoint/Sektör algosu) bir hale geldi.
2.  M2 kısmına bataryayı anlık ölçüp sistemi kurtarma yeteneği eklendi.
3.  Kod, ilk rapordaki gibi doğrudan sensöre körü körüne güvenmek yerine verileri medyana alarak filtreleyip FSM'e besleyecek kadar olgunlaştı.
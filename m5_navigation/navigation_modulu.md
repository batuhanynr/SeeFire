# Navigation Module — Updated Design Note

Bu belge, `M5 Navigation` modülünün **güncel** davranışını açıklar. Eski taslaklarda geçen `Arduino`, `wall-following`, `occupancy grid`, `explore -> patrol` gibi kavramlar bu dosyada yalnızca tarihsel karşılaştırma amacıyla anılır; mevcut Python kodunun çalışma modeli bunlar değildir.

## 1. Amaç

M5'in amacı, robotu önceden tanımlanmış bir rota üzerinde güvenli biçimde ilerletmektir.

Bu rota:
- robot tarafından çıkarılmaz
- çalışma sırasında öğrenilmez
- harita üretmez
- takım tarafından önceden tanımlanır

Mevcut yaklaşım şu fikre dayanır:
- harita statiktir
- rota güneyden kuzeye tek ana eksen üzerinde tanımlıdır
- rota sektörlere ayrılmıştır
- her sektör içinde belirli kontrol noktaları vardır
- robot başlangıç konumunu doğrulamadan harekete başlamaz

## 2. Orijinal SeeFire Raporuna Göre Değişen Kısım

`SeeFire_Module_Documentation_Report` içinde navigasyon tarafı daha genel ve keşif odaklı tanımlanmıştı:
- bilinmeyen alanı dolaşma
- sağ duvar takibi
- occupancy grid çıkarma
- keşif tamamlanınca patrol moduna geçme

Kodda uygulanan güncel yaklaşım daha deterministik ve daha sınırlı bir problemdir:
- harita zaten bellidir
- rota zaten bellidir
- robotun görevi o rota üzerinde ilerlemektir
- engel çıkarsa geçici bir bypass manevrası uygulanır
- sonrasında robot rota çizgisine geri oturtulur

Bu değişiklik SeeFire fikrini bozmaz; yalnızca navigasyonu sadeleştirir ve saha davranışını daha öngörülebilir hale getirir.

## 3. Donanım Varsayımları

Bu doküman için geçerli mimari:
- **Arduino yok**
- **seri haberleşme yok**
- tüm motor/sensör I/O işlemleri doğrudan Raspberry Pi üzerindedir
- encoder pulse sayımı Raspberry Pi GPIO interrupt mantığıyla yapılır

Navigasyonda kullanılan temel donanımlar:
- `HC-SR04 left`
- `HC-SR04 front`
- `HC-SR04 right`
- teker encoder bilgisi
- USB kamera

Navigasyonun doğrudan kullanmadığı ama sistem seviyesinde var olan bileşenler:
- MQ-2
- MLX90614
- alarm LED / buzzer

## 4. Rota Modeli

Rota `config.WAYPOINTS` ile tanımlanır:

```python
WAYPOINTS = [
    (100, 1),
    (200, 2),
    (300, 3),
]
```

Her tuple şu anlamdadır:
- `target_north_cm`: başlangıç noktasından itibaren kuzey yönünde ulaşılması gereken toplam mesafe
- `sector_id`: bu hedefin ait olduğu sektör numarası

Örnek yorum:
- `(100, 1)` -> 1. sektör sonu, başlangıçtan 100 cm kuzey
- `(200, 2)` -> 2. sektör sonu, başlangıçtan 200 cm kuzey

M5 için önemli nokta şudur: bu rota mutlak kuzey yönünde tanımlanmış bir ilerleme referansıdır. Yan kaçışlar veya bypass manevraları gerçek kuzey ilerleyişi olarak sayılmaz.

## 5. Sektör Kavramı

Her sektör iki kritik noktaya sahiptir:
- **midpoint**
- **waypoint / sector end**

Midpoint şu formülle hesaplanır:

```python
sector_midpoint_cm = current_cm + (target_cm - current_cm) / 2.0
```

Buradaki amaç:
- sektörün ortasında bir kontrol anı yaratmak
- görüntü alma veya üst seviye karar akışına hook vermek
- robot engelden dolayı hafif detour yapsa bile bu kontrol noktasını kaçırmamak

Bu nedenle midpoint mantığı navigasyon döngüsünün yalnızca düz yol kısmında değil, obstacle bypass sırasında da korunur.

## 6. Başlangıç Konum Doğrulama

Robot hareket etmeden önce fiziksel olarak beklenen hatta yerleştirilmiş olmalıdır. Bunu doğrulamak için sol ve sağ HC-SR04 sensörleri kullanılır.

Referans sabitler:
- `START_LEFT_CM`
- `START_RIGHT_CM`
- `POSITION_TOLERANCE_CM`

Doğrulama mantığı:

```python
left_err = abs(reading.left_cm - START_LEFT_CM)
right_err = abs(reading.right_cm - START_RIGHT_CM)
```

Eğer bu iki hata tolerans dışında kalırsa:
- robot navigasyona başlamaz
- `RuntimeError` fırlatılır

Bu adım kritiktir çünkü mevcut sistem SLAM yapmıyor. Başlangıç pozu yanlışsa encoder tabanlı tüm ilerleme hesabı anlamsız hale gelir.

## 7. Konum Kaynağı: Encoder Öncelikli Yaklaşım

Mevcut mimaride kuzey yönündeki ilerleme için ana kaynak encoder verisidir.

Yan sensörlerin rolü sınırlıdır:
- başlangıçta konum doğrulama
- bypass sonrası lateral fine-tune
- turn-direction fallback kararı

Yan sensörler sürekli konum integrasyonu için kullanılmaz. Bunun nedeni:
- HC-SR04 gürültüsü
- yüzey yansıma farkları
- her anda duvar referansı garanti olmaması

Bu yüzden M5 için “asıl mesafe”:
- `m2_motor.get_total_distance_cm()`

olur.

## 8. Ana Navigasyon Döngüsü

`NavigationController.run()` şu sırayı takip eder:

1. Başlangıç konumunu doğrula
2. `WAYPOINTS` listesindeki her sektörü sırayla işle
3. Sektör midpoint'ini hesapla
4. Hedef mesafeye ulaşana kadar adım adım ilerle
5. Her iterasyonda midpoint geçildi mi kontrol et
6. Front sensörü oku
7. Yol açıksa `STEP_DISTANCE_CM` kadar ilerle
8. Yol kapalıysa obstacle avoidance çağır
9. Sektör sonunda waypoint snapshot tetikle

Pseudo-flow:

```text
for each sector:
  while total_distance < target_cm:
    check_midpoint()
    read front sensor
    if clear:
      drive forward one step
    else:
      run obstacle bypass
  trigger waypoint snapshot
```

Bu yapı özellikle şunları sağlar:
- midpoint hassasiyeti
- kısa adımlarla güvenli engel kontrolü
- bypass sırasında toplam kuzey ilerleyişin yönetilebilir kalması

## 9. Snapshot Hook Mantığı

M5 görüntüyü kendi başına kalıcı dosyaya yazmaz. Bunun yerine üst katmana bir olay bildirir:

```python
snapshot_callback(label)
```

Şu etiketler kullanılır:
- `sector-{id}-midpoint`
- `sector-{id}-waypoint`

Eğer callback verilmemişse M5 basit fallback olarak `m4_vision.capture_frame()` çağırır. Ancak bu sadece “frame al” davranışıdır; tam logging/persistence orkestrasyonu değildir.

Bu tasarım M5'i daha modüler tutar:
- navigasyon snapshot anını bilir
- ama snapshot'ın nasıl işlendiğini bilmek zorunda kalmaz

## 10. Engel Tespiti

Engel tespiti için birincil sensör:
- `front_cm`

Temel eşik:
- `OBSTACLE_THRESHOLD_CM`

Karar:
- `front_cm > threshold` -> yol açık
- `front_cm <= threshold` -> obstacle avoidance

Front sensör geçersiz veya anlamsız bir değer döndürürse mevcut kod güvenli tarafta kalmak için küçük adım mantığıyla ilerlemeyi sürdürür.

## 11. Engel Kaçınma Stratejisi

Obstacle avoidance şu problemi çözer:
- robot ana hatta kuzeye gidiyor
- önünde engel var
- geçici olarak yan tarafa çıkar
- engelin yanından geçer
- tekrar ana kuzey hattına döner

Akış:

1. Dönüş yönünü seç
2. Seçilen yöne 90 derece dön
3. Yanal geçiş yap
4. Aynı yanal mesafeyi encoder ile geri oyna
5. Kuzey yönüne geri dön
6. Kuzey progress sayacını restore et
7. Lateral fine-tune uygula

Buradaki önemli tasarım kararı:
- bypass sırasında sağa veya sola gidilen fiziksel yan mesafe, “kuzeye ilerledim” sayılmaz
- bu yüzden `north_distance_before` saklanır
- manevra bitince `set_total_distance_cm(north_distance_before)` ile geri yazılır

Bu, sektör midpoint kontrolünün kuzey eksenine göre anlamlı kalmasını sağlar.

## 12. Dönüş Yönü Nasıl Seçiliyor?

Birincil yöntem:
- `m4_vision.determine_turn_direction()`

Bu fonksiyon:
- kameradan frame alır
- lower-half ROI üzerinde basit bir edge/gap mantığı çalıştırır
- daha açık tarafı `LEFT` veya `RIGHT` olarak döndürür

Eğer kamera karar veremezse fallback devreye girer:
- `left_cm` ve `right_cm` karşılaştırılır
- daha açık olan taraf seçilir

Yani karar zinciri şöyledir:

```text
camera hint -> ultrasonic fallback
```

## 13. Clearance Sensörü Neden Yöne Göre Değişiyor?

Bu konu önemli çünkü eski kısa versiyonda bu detay yeterince görünür değildi.

Robot sağa dönerse:
- robot doğuya bakar
- engel robotun sol tarafında kalır
- bu yüzden clearance için `left_cm` izlenir

Robot sola dönerse:
- robot batıya bakar
- engel robotun sağ tarafında kalır
- bu yüzden clearance için `right_cm` izlenir

Bu nedenle güncel kod şu mantığı uygular:
- bypass `RIGHT` -> `left_cm`
- bypass `LEFT` -> `right_cm`

Bu ayrım yapılmazsa sistem yanlış sensöre bakıp:
- engeli erken bitmiş sanabilir
- hiç bitmemiş sanabilir
- güvenlik cap'ine kadar sürüklenebilir

## 14. Bypass Sonrası Rota Çizgisine Geri Dönüş

Yan geçişte katedilen mesafe küçük adımlarla toplanır:

```python
traveled += SIDE_STEP_CM
```

Daha sonra bu aynı mesafe tekrar yürünür ve robot ana hatta geri alınır.

Burada özellikle encoder tercih edilir. Çünkü geri dönüş anında çevrede başka duvarlar veya yansımalar olabilir; ultrasonik sensörlerle doğrudan “tam aynı çizgiye döndüm” demek pratikte daha kırılgandır.

Dolayısıyla mantık:
- yandan ne kadar gittiysem
- aynı kadar geri gel

şeklindedir.

## 15. Bypass Sonrası İnce Ayar

Encoder tabanlı geri dönüş deterministik olsa da slip olabilir. Bu yüzden `PositionVerifier.verify_and_correct()` çağrılır.

Bu fonksiyon:
- tekrar sol/sağ referansları okur
- `START_LEFT_CM` ile farkı hesaplar
- tolerans dışındaysa küçük bir lateral adım uygular

Bu düzeltme büyük bir yeniden lokalizasyon değildir; sadece ana rota çizgisine yakınlığı korumak için kullanılan pratik bir fine-tune adımıdır.

## 16. Median Filter Neden Var?

`M3` tarafındaki `get_navigation_sensors_filtered()` fonksiyonu özellikle şu durumlar için yararlıdır:
- tek ölçümlük yankı sıçramaları
- yüzeyden kaynaklanan anlık yanlış okuma
- bypass sırasında clearance kararının gürültüden etkilenmesi

Bu yüzden M5:
- düz gidişte gerekirse hızlı raw okuma kullanabilir
- yön kararı ve bypass clearance gibi hassas noktalarda filtreli veriden faydalanır

## 17. Kod Dosyaları ve Sorumluluk Dağılımı

### `navigation.py`
- sektör döngüsü
- midpoint/waypoint logic
- front sensor ile ana ilerleme kararı
- snapshot hook tetikleme

### `obstacle.py`
- engel yönü seçimi
- 90 derece dönüşler
- yanal bypass
- route line restore

### `position.py`
- başlangıç doğrulama
- bypass sonrası lateral correction

Bu ayrım modül içi sorumlulukları sade tutar.

## 18. Mevcut Sınırlamalar

Şu anki tasarımın bilinen sınırları:
- M6 henüz gerçek FSM olarak bağlı değil
- M4 tarafında yangın/smoke inference henüz entegre değil
- encoder kalibrasyonu sahada ayarlanmalı
- static route yaklaşımı, keşif yapabilen genel bir mobil robot değildir

Yani M5 bugünkü haliyle kontrollü bir rota izleme çözümüdür; genel amaçlı otonom navigasyon çözümü değildir.

## 19. Sonuç

M5'in bugünkü rolü net olarak şudur:
- statik rota üzerinde ilerle
- başlangıç pozunu doğrula
- sektör bazlı kontrol noktalarını kaçırma
- engeli yandan geç
- ana hatta geri dön
- encoder ile ilerlemeyi yönet

Bu yaklaşım, eski explore/map-generation tasarımına göre daha sade, daha uygulanabilir ve mevcut repo durumuyla daha uyumludur.

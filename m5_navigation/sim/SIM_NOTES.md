# M5 Simülatörü — Kullanım Notları

Robotun navigasyon algoritmasını dev makinende (Mac/Linux/Windows) Raspberry Pi olmadan adım adım izleyebilirsin. Mock mode otomatik devreye girer.

---

## Hızlı Başlangıç

Proje kök dizininde (`/Users/alperen/Desktop/SeeFire`) komut çalıştır.

### Canlı pencere (önerilen — adım adım görmek için)

```bash
python3 -m m5_navigation.sim.demo single
```

Matplotlib penceresi açılır. Robot her motor komutu sonrası bir frame ilerler. Pencerede:
- **Siyah dikdörtgen:** harita sınırları (duvarlar)
- **Kırmızı kutular:** engeller
- **Mavi daire + lacivert ok:** robot ve baktığı yön
- **Gri ışınlar:** sol / ön / sağ ultrasonik sensörlerin gördüğü mesafe
- **Yeşil çizgi:** şimdiye kadar gezdiği yol (trajectory)
- **Üstte başlık:** `[frame_no/toplam] yapılan_eylem` + sensör okumaları

### GIF olarak kaydet

```bash
python3 -m m5_navigation.sim.demo single --save run.gif
```

GIF mevcut dizinde oluşur. Slack/WhatsApp/PR'a kolayca eklenebilir.

### Frame hızını ayarla

```bash
python3 -m m5_navigation.sim.demo single --interval 500
```

`--interval` = frame başına milisaniye. Varsayılan **300**.
- **600-1000:** çok yavaş, her adımı tek tek inceleyebilirsin
- **300:** normal
- **100-150:** hızlı oynat

---

## Mevcut Senaryolar

| Komut | Ne gösterir |
|---|---|
| `python3 -m m5_navigation.sim.demo single` | Koridor ortasında tek engel. Robot temiz bypass yapar. |
| `python3 -m m5_navigation.sim.demo wall` | Engel sağ duvara yapışık. RIGHT yönü tıkanır → retreat → LEFT'ten başarır. |
| `python3 -m m5_navigation.sim.demo blocked` | Engel tüm koridoru kaplıyor. İki yön de tıkalı → `ObstacleBlockedError` raise, robot güvenli durur. |
| `python3 -m m5_navigation.sim.demo multi` | 3 sektörlü rota, 2 engel. Her sektörde 1 tarama (toplam 3 × 4 = 12 snapshot). Tarama 3 farklı durumda fire eder: bypass içinde (S1), bypass biter bitmez off-route (S2), normal route (S3). |

---

## Logging ile İzleme

Animasyon penceresi açılırken terminalde de algoritmanın her kararı log'lanır:

```
[NAV] Verifying start position...
Start position OK: left=30.0 cm, right=30.0 cm
[SECTOR 1] Start. Target=150.0 cm, midpoint=75.0 cm
[OBSTACLE] front=20.0 cm — initiating avoidance.
[OBSTACLE] D0=20.0 cm. Bypass direction: LEFT
[OBSTACLE] Side-pass cleared after 15.0 cm (right_cm=170.0 > 35.0).
[OBSTACLE] Forward-pass acquired obstacle at 20.0 cm (right_cm=5.0).
[OBSTACLE] Forward-pass released after 40.0 cm (right_cm=45.0 > 35.0).
[WAYPOINT] Sector 1 end.
```

`acquired/released` mesajları forward-pass state machine'in iki fazını gösterir (engeli ilk gördü vs. arkada bıraktı).

### 4-Yön Tarama (Sektör Midpoint'lerinde)

Robot, her sektörün **tam ortasına** ulaştığında durup 4 yöne kamera taraması yapar (yangın/duman tespiti için). Log'da şöyle görünür:

```
[SCAN] sector-1-midpoint-N
[SCAN] sector-1-midpoint-E
[SCAN] sector-1-midpoint-S
[SCAN] sector-1-midpoint-W
```

Animasyonda 4 ardışık 90° sağ dönüş gözükür (toplam 360° → robot baştaki yönüne döner). Engel bypass'i sırasında forward-pass içinde midpoint geçilirse robot route hattında değil (örn. x=15) olabilir; tarama yine yapılır, alan kapsama amacı korunur.

**Waypoint'lerde** (sektör sonu) sadece tek frame snapshot vardır, 4-yön tarama değil.

---

## Kendi Senaryonu Yaz

`m5_navigation/sim/demo.py` içine kopyala ya da inline Python:

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from m5_navigation.sim import World, Obstacle, Robot, install_mock_drivers, animate
from m5_navigation.navigation import NavigationController
from m5_navigation.obstacle import ObstacleBlockedError

w = World(
    width=60.0, height=300.0,
    obstacles=[
        Obstacle(x=20.0, y=70.0,  w=20.0, h=15.0),   # 1. engel
        Obstacle(x=15.0, y=160.0, w=25.0, h=20.0),   # 2. engel
    ],
    robot=Robot(x=30.0, y=0.0, heading_deg=90.0),
    turn_hint=None,   # None = ultrasonic karar versin; "LEFT" / "RIGHT" zorla
)
install_mock_drivers(w)

try:
    NavigationController(snapshot_callback=w.snapshot_event).run(
        waypoints=[(100.0, 1), (250.0, 2)]
    )
except ObstacleBlockedError as e:
    print("ABORT:", e)
    w.snapshot_event("ABORT")

animate(w)                 # canlı pencere
# animate(w, save_path="custom.gif")   # gif olarak kaydet
```

### Parametre notları

- **`World(width, height)`** — cm cinsinden harita boyutları. Robot başlangıçta sol/sağ duvardan 30 cm uzakta olmalı (config'deki `START_LEFT_CM`/`START_RIGHT_CM`). Yani `width=60`, robot `x=30` veya `width=100`, robot `x=30` ya da `x=70`.
- **`Obstacle(x, y, w, h)`** — sol-alt köşe + genişlik + yükseklik.
- **`Robot(x, y, heading_deg)`** — `heading_deg=90` kuzey demek; sim baştan beri buna göre.
- **`turn_hint`** — kamera modülünün ne döneceğini zorlar. `"LEFT"` / `"RIGHT"` ile bypass yönünü test edebilirsin. `None` → ultrasonic karar verir.
- **`waypoints=[(target_y_cm, sector_id), ...]`** — robot bu Y koordinatlarına sırayla varır, her sektörde midpoint + waypoint snapshot tetiklenir.

---

## Tek Frame Tek Tek İncelemek

Pencere açıkken matplotlib araç çubuğundan animasyonu durdurabilirsin. Ama daha temizi: `interval_ms=1000` ile yavaşlat. Ya da kod içinde `world.frames` listesine eriş:

```python
for i, f in enumerate(w.frames):
    print(f"[{i:3d}] {f.label:35s}  ({f.x:6.1f},{f.y:6.1f}) hdg={f.heading_deg:5.1f}  "
          f"L={f.left_cm:6.1f} F={f.front_cm:6.1f} R={f.right_cm:6.1f}")
```

Bu, animasyonun text trace'idir. Bir frame'i yakaladığında oraya breakpoint koyup geometri matematiğini elle doğrulayabilirsin.

---

## Sorun Giderme

| Sorun | Çözüm |
|---|---|
| `matplotlib not installed` | `pip3 install --user matplotlib pillow` |
| `No such file or directory: runtime_data` (gif save) | `mkdir -p runtime_data` ya da `--save ./out.gif` (kök dizine kaydet) |
| Pencere açılmıyor (SSH üzerinden) | `--save out.gif` kullan, sonra dosyayı yerel makinene aktar |
| Senaryo sonsuz döngüye giriyor | Algoritma bug'u ihtimali var. `Ctrl+C` ile durdur, logları incele. (Geçmişte böyle bir bug yakalanıp `_forward_pass_obstacle` ile düzeltilmişti.) |
| "Start position out of tolerance" | World boyutu yanlış. `width = 2 × START_LEFT_CM` olmalı (default: 60 cm). |

---

## Sim Mimari Notu

- `m5_navigation/sim/world.py` — 2D ground-truth + ray-cast geometri
- `m5_navigation/sim/mock_drivers.py` — m2_motor / m3_sensors / m4_vision modüllerini world'e patch
- `m5_navigation/sim/visualizer.py` — matplotlib `FuncAnimation`
- `m5_navigation/sim/demo.py` — hazır senaryolar + CLI

`install_mock_drivers(world)` çağrıldıktan SONRA `NavigationController` import edilmeli (driver patch'leri ondan önce yerine oturmuş olsun). `demo.py` bunu zaten doğru sırayla yapıyor.

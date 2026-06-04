# SeeFire Proje Sunumu - Hazırlık Notları

## Demo Komutu
```bash
python demo.py
```

## Modül Durumu (Test Sonuçları)

| Modül | Test Durumu | Pass/Fail |
|-------|-------------|-----------|
| **M2 Motor** | ✅ Çalışıyor | 6/6 passed |
| **M3 Sensörler** | ✅ Çalışıyor | 6/6 passed |
| **M4 Vision** | ⚠️ Kısmi | 0 tests (YOLO integration pending) |
| **M5 Navigasyon** | ✅ Çalışıyor | 13/14 passed (1 minor failure) |
| **M6 Decision** | ⚠️ Kısmi | 0 tests (implemented but no tests) |
| **M7 Logging** | ✅ Çalışıyor | 13/13 passed |

## Sunumda Gösterilecek Özellikler

### M1: Konfigürasyon
- Waypoint-based rotalar (3 sektör)
- Fusion weights (Vision: 0.5, Smoke: 0.3, IR: 0.2)
- Alarm threshold'ları

### M2: Motor Kontrol
- L298N driver kontrolü
- Battery monitoring (7.4V nominal)
- Encoder tick okuma

### M3: Sensör Entegrasyonu
- MQ-2 smoke sensor
- MLX90614 IR temperature
- HC-SR04 x3 (Left, Front, Right)
- Median-filtered okumalar
- Obstacle detection

### M4: Vision
- Kamera frame capture
- YOLOv8n model (fire_yolov8n.onnx)
- Turn direction hint

### M5: Navigasyon
- Waypoint-based seyahat
- Obstacle bypass (sol/sağ karar)
- 3-yönlü tarama
- Encoder odometri

### M6: Decision Engine (FSM)
- States: INIT → NAVIGATE → VERIFY → ALARM → STOP
- Fusion score calculation
- State transitions

### M7: Logging
- SQLite (WAL mode)
- Event logging
- Map persistence
- Snapshot save/load

## Tek Run Komutu
```bash
SEEFIRE_FORCE_MOCK=1 python demo.py
```

## Veri Çıktıları
- `./demo_data/seefire.db` - SQLite veritabanı
- `./demo_data/map.json` - Harita verisi
- `./demo_data/snapshots/` - Kamera snapshot'ları

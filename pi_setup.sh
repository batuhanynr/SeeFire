#!/bin/bash
# ============================================================
# SeeFire — Raspberry Pi Kurulum & Deploy Script
# Pi'de çalıştır: bash pi_setup.sh
# ============================================================
set -e

PI_REPO="https://github.com/batuhanynr/SeeFire.git"
PROJECT_DIR="$HOME/SeeFire"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     SeeFire Pi Kurulum Başlıyor...       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Sistem paketleri ─────────────────────────────────────
echo "[ 1/6 ] Sistem paketleri güncelleniyor..."
sudo apt-get update -y -q
sudo apt-get install -y -q \
    python3-pip python3-venv git \
    python3-opencv \
    python3-numpy \
    python3-smbus \
    i2c-tools \
    libatlas-base-dev \
    libopenblas-dev

echo "       ✓ Sistem paketleri hazır"

# ── 2. Kod çek ──────────────────────────────────────────────
echo "[ 2/6 ] GitHub'dan kod çekiliyor..."
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    git pull
    echo "       ✓ git pull tamamlandı"
else
    git clone "$PI_REPO" "$PROJECT_DIR"
    echo "       ✓ git clone tamamlandı"
fi
cd "$PROJECT_DIR"

# ── 3. Python sanal ortam & pip paketleri ───────────────────
echo "[ 3/6 ] Python bağımlılıkları kuruluyor..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv --system-site-packages
fi
source .venv/bin/activate

# Temel paketler (opencv zaten apt ile geldi)
pip install -q --upgrade pip
pip install -q \
    smbus2 \
    spidev \
    RPi.GPIO \
    Pillow \
    pytest

# PyTorch (CPU-only, Pi için hafif versiyon)
echo "       PyTorch CPU kuruluyor (birkaç dakika sürebilir)..."
pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Ultralytics (YOLO)
pip install -q ultralytics

echo "       ✓ Python bağımlılıkları hazır"

# ── 4. Model klasörü ────────────────────────────────────────
echo "[ 4/6 ] Model klasörü kontrol ediliyor..."
mkdir -p m4_vision/models
mkdir -p runtime_data/snapshots

if [ -f "m4_vision/models/fire_yolov8n.pt" ]; then
    echo "       ✓ fire_yolov8n.pt mevcut"
else
    echo "       ⚠ fire_yolov8n.pt bulunamadı!"
    echo "       → Modeli şu komutla kopyala (PC'den):"
    echo "         rsync -avz m4_vision/models/ raspberry@$(hostname -I | awk '{print $1}'):~/SeeFire/m4_vision/models/"
fi

if [ -f "m4_vision/models/obstacle_yolov8n.pt" ]; then
    echo "       ✓ obstacle_yolov8n.pt mevcut"
else
    echo "       ⚠ obstacle_yolov8n.pt bulunamadı!"
    echo "       → İndiriliyor (COCO yolov8n)..."
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(); import shutil; shutil.move('yolov8n.pt', 'm4_vision/models/obstacle_yolov8n.pt')" 2>/dev/null || \
    python3 -c "
from urllib.request import urlretrieve
print('yolov8n.pt indiriliyor...')
urlretrieve('https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt', 'm4_vision/models/obstacle_yolov8n.pt')
print('İndirildi.')
"
    echo "       ✓ obstacle_yolov8n.pt hazır"
fi

# ── 5. I2C & kamera kontrol ─────────────────────────────────
echo "[ 5/6 ] Donanım kontrolleri..."

# I2C etkin mi?
if ls /dev/i2c-* &>/dev/null; then
    echo "       ✓ I2C aktif"
    echo "       I2C cihazları: $(i2cdetect -y 1 2>/dev/null | grep -o '5a\|68\|60' | tr '\n' ' ')"
else
    echo "       ⚠ I2C bulunamadı — raspi-config'den etkinleştir (Interface Options → I2C)"
fi

# Kamera var mı?
if python3 -c "import cv2; c=cv2.VideoCapture(0); print('Kamera:', c.isOpened()); c.release()" 2>/dev/null | grep -q "True"; then
    echo "       ✓ Kamera açılıyor"
else
    echo "       ⚠ Kamera açılamadı — USB kamera takılı mı?"
fi

# ── 6. Ortam değişkenleri ────────────────────────────────────
echo "[ 6/6 ] Çalıştırma ayarları..."
cat > "$PROJECT_DIR/.env" << 'ENVEOF'
# SeeFire runtime env
# Mock mod için: SEEFIRE_FORCE_MOCK=1
# PC'den canlı görüntü için: SEEFIRE_STREAM=1
SEEFIRE_FORCE_MOCK=0
SEEFIRE_STREAM=1
SEEFIRE_STREAM_PORT=8080
ENVEOF
echo "       ✓ .env dosyası oluşturuldu"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         KURULUM TAMAMLANDI ✓             ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "ÇALIŞTIRMAK İÇİN:"
echo "  cd ~/SeeFire"
echo "  source .venv/bin/activate"
echo "  python3 main.py"
echo ""
echo "MOCK MODDA TEST (GPIO olmadan):"
echo "  SEEFIRE_FORCE_MOCK=1 python3 main.py"
echo ""
echo "PC'DEN CANLI GÖRÜNTÜ (kamera açıkken):"
PI_IP=$(hostname -I | awk '{print $1}')
echo "  Tarayıcıdan aç: http://${PI_IP}:8080/"
echo ""

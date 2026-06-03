#!/usr/bin/env python3
"""
SeeFire M4 - Canlı Kamera Testi
Çalıştır: python3 live_camera_test.py
Kapat   : pencerede 'q' veya ESC
"""
import os
import sys
import subprocess
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("SEEFIRE_FORCE_MOCK", None)

import cv2
import m4_vision.vision as vm
from m4_vision.vision import _letterbox_crop, VisionM4

vm.CV_AVAILABLE = True
v = VisionM4()

# --- Kamera seçimi ---
CAMERA_INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else None

def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap if cap.isOpened() else None

if CAMERA_INDEX is not None:
    cap = open_camera(CAMERA_INDEX)
    if cap is None:
        print(f"Kamera {CAMERA_INDEX} açılamadı.")
        sys.exit(1)
    # Warm-up: kamera başlangıçta birkaç siyah frame verir
    print(f"Kamera {CAMERA_INDEX} ısınıyor...", end="", flush=True)
    for _ in range(20):
        cap.read()
        time.sleep(0.05)
    print(" hazır.")
else:
    print("Mevcut kameralar:")
    cap = None
    for i in range(6):
        c = open_camera(i)
        if c:
            w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"  [{i}] {w}x{h}")
            if cap is None and i > 0:   # dahili FaceTime'ı atla
                cap = c
            elif cap is None and i == 0:
                cap = c                  # başka yoksa dahiliyi kullan
            else:
                c.release()
    print(f"Kullanılan kamera: {CAMERA_INDEX}")

# --- Ses ---
import tempfile, struct, wave, math

def _make_siren_wav(path: str):
    """Yangın sireni tonu: 880Hz↔1200Hz arası 3 kez sweep, 1.5 sn."""
    rate = 44100
    duration = 1.5
    n = int(rate * duration)
    data = []
    for i in range(n):
        t = i / rate
        # Her 0.5 sn'de bir frekans yukarı-aşağı salınır
        freq = 880 + 320 * math.sin(2 * math.pi * t * 2)
        sample = int(32767 * math.sin(2 * math.pi * freq * t))
        data.append(sample)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f'<{n}h', *data))

_SIREN_WAV = os.path.join(tempfile.gettempdir(), "seefire_alarm.wav")
_make_siren_wav(_SIREN_WAV)

_sound_lock = threading.Lock()
_last_beep = 0.0
BEEP_INTERVAL = 2.0

def beep():
    global _last_beep
    now = time.time()
    with _sound_lock:
        if now - _last_beep < BEEP_INTERVAL:
            return
        _last_beep = now

    def _play():
        # Siren sesi x2 + sesli uyarı
        subprocess.run(["afplay", "-v", "5", _SIREN_WAV], capture_output=True)
        subprocess.run(["say", "-v", "Bad News", "-r", "140", "Fire detected!"],
                       capture_output=True)
    threading.Thread(target=_play, daemon=True).start()

# --- Ana döngü ---
FIRE_THRESH = 0.25
cv2.namedWindow("SeeFire M4 - Live", cv2.WINDOW_NORMAL)
cv2.resizeWindow("SeeFire M4 - Live", 640, 480)

print("Pencere açıldı. Çıkış: 'q' veya ESC")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame alınamadı!")
        break

    frame320 = _letterbox_crop(frame.copy(), 320, 240)
    show = cv2.resize(frame320, (640, 480), interpolation=cv2.INTER_NEAREST)

    fire_conf, smoke_conf, fire_side = vm._run_yolo(frame320)
    turn = v.determine_turn_direction(frame=frame320)

    if fire_conf >= FIRE_THRESH:
        beep()
        cv2.rectangle(show, (0, 0), (639, 479), (0, 0, 255), 4)

    color_fire = (0, 0, 255) if fire_conf >= FIRE_THRESH else (0, 255, 0)
    cv2.putText(show, f"Fire: {fire_conf:.2f}  Smoke: {smoke_conf:.2f}",
                (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color_fire, 2)
    cv2.putText(show, f"Turn: {turn or 'none'}",
                (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 2)
    if fire_side:
        cv2.putText(show, f"Fire side: {fire_side}",
                    (10, 116), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

    cv2.imshow("SeeFire M4 - Live", show)
    key = cv2.waitKey(30) & 0xFF
    if key in (ord('q'), 27):
        break

cap.release()
cv2.destroyAllWindows()
print("Kapatıldı.")

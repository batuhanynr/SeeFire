#!/usr/bin/env python3
"""
SeeFire - Motor Odometrisi Kalibrasyon Aracı

Bu araç robotu hedeflenen mesafe (varsayılan: 500 cm) kadar ileri sürer,
encoderlardan okunan toplam tick sayısını ekrana basar ve
gerçekte gidilen mesafeye göre config.py'de güncellenmesi gereken
ENCODER_TICKS_PER_CM değerini hesaplar.
"""

import sys
import time
import logging

# Log seviyesini ayarla
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import config
    import m2_motor
except ImportError:
    print("Hata: SeeFire modülleri yüklenemedi. Bu betiği proje kök dizininde çalıştırın.")
    sys.exit(1)

def run_calibration(target_cm=500.0):
    print("====================================================")
    print("         SeeFire Odometri Kalibrasyon Aracı          ")
    print("====================================================")
    print(f"Hedeflenen Sürüş Mesafesi: {target_cm} cm (5 metre)")
    print(f"Mevcut Kalibrasyon Eşiği (ENCODER_TICKS_PER_CM): {config.ENCODER_TICKS_PER_CM}")
    print("----------------------------------------------------")
    print("HAZIRLIK: Robotu düz ve engelsiz bir alana koyun.")
    print("Başlamak için ENTER'a basın (durdurmak için Ctrl+C)...")
    input()

    print("[KALİBRASYON] Donanım başlatılıyor...")
    if not m2_motor.init_hardware():
        print("Hata: Donanım başlatılamadı!")
        sys.exit(1)

    print(f"[KALİBRASYON] Sürüş başlıyor. Hedef: {target_cm} cm...")
    time.sleep(1.0)

    # Encoderları sıfırla ve sür
    m2_motor.reset_encoder_window()
    m2_motor.drive_distance_cm(target_cm)
    m2_motor.stop()

    print("[KALİBRASYON] Sürüş tamamlandı. Duruldu.")
    time.sleep(0.5)

    # Ticks oku
    left_ticks, right_ticks = m2_motor.get_encoder_ticks()
    avg_ticks = (left_ticks + right_ticks) / 2.0

    print("\n---------------- Sonuçlar ----------------")
    print(f"Sol Teker Ticks  : {left_ticks}")
    print(f"Sağ Teker Ticks : {right_ticks}")
    print(f"Ortalama Ticks  : {avg_ticks}")
    print("------------------------------------------")
    print("\nŞimdi lütfen robotun başladığı nokta ile durduğu nokta arasındaki")
    print("GERÇEK mesafeyi (cm cinsinden) ölçün.")
    
    try:
        measured_cm = float(input("Ölçülen Gerçek Mesafe (cm): "))
        if measured_cm <= 0:
            raise ValueError("Mesafe sıfırdan büyük olmalıdır.")
        
        # Yeni değeri hesapla: ticks / gerçek mesafe
        new_ticks_per_cm = avg_ticks / measured_cm
        
        print("\n================ HESAPLANAN DEĞER ================")
        print(f"Yeni ENCODER_TICKS_PER_CM değeri: {new_ticks_per_cm:.4f}")
        print("==================================================")
        print("\nBu değeri config.py dosyasındaki şu satırla güncelleyin:")
        print(f"ENCODER_TICKS_PER_CM = {new_ticks_per_cm:.4f}")
        print("\nArdından değişiklikleri deploy edin.")
    except ValueError:
        print("Geçersiz ölçüm girdiniz. Kalibrasyon sonlandırıldı.")
    finally:
        m2_motor.cleanup()

if __name__ == "__main__":
    target = 500.0
    if len(sys.argv) > 1:
        try:
            target = float(sys.argv[1])
        except ValueError:
            pass
    run_calibration(target)

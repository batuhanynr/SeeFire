#!/usr/bin/env python3
"""
SeeFire — YOLOv8 Model ONNX Export Utility
==========================================
Bu araç, PyTorch (.pt) formatındaki YOLO modellerini daha yüksek performans (FPS) 
ve daha düşük CPU kullanımı için ONNX formatına dönüştürür.
"""
import os
import sys

def main():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     SeeFire — YOLO ONNX Export Yardımcı Programı           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    # 1. Ultralytics ve PyTorch Kontrolü
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Hata: 'ultralytics' kütüphanesi yüklü değil.")
        print("Model export etmek için 'pip install ultralytics' çalıştırmalısınız.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "m4_vision", "models")

    models = {
        "fire_yolov8n.pt": "Yangın/Duman Tespit Modeli",
        "obstacle_yolov8n.pt": "Engel Tespit Modeli"
    }

    for model_name, desc in models.items():
        pt_path = os.path.join(models_dir, model_name)
        onnx_path = pt_path.replace(".pt", ".onnx")

        print(f"\n---> {desc} ({model_name}) işleniyor...")

        if not os.path.exists(pt_path):
            print(f"Hata: {pt_path} bulunamadı. Lütfen model dosyasının varlığından emin olun.")
            continue

        print(f"Model yükleniyor: {pt_path}")
        try:
            model = YOLO(pt_path)
            print("ONNX formatına dışa aktarılıyor (Bu işlem biraz sürebilir)...")
            # ONNX modelini 12. opset ile dışa aktar (RPi ONNX runtime ile mükemmel uyumluluk için)
            model.export(format="onnx", opset=12)
            print(f"Başarılı! Model şuraya kaydedildi: {onnx_path}")
        except Exception as e:
            print(f"Model dışa aktarılırken hata oluştu: {e}")

    print("\nİşlem tamamlandı. ONNX modelleri başarıyla oluşturuldu!")
    print("Artık Raspberry Pi üzerinde 'pip install onnxruntime' kurarak daha yüksek FPS alabilirsiniz.")

if __name__ == "__main__":
    main()

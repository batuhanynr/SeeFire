# M4_VISION — AI & Vision Pipeline

One-sentence purpose: Runs a YOLOv8n INT8 fire/smoke detection model on USB webcam frames in a background thread and exposes the latest inference result to M6.

**Author:** Emre Can Tuncer (200104004115), Semih Sarkoca (220104004038) 
**Module ID:** M4  
**Version:** 0.1

---

## Dependencies

| Dependency | Type | Notes |
|---|---|---|
| opencv-python ≥ 4.8.0 | Python package | Frame capture and preprocessing |
| ultralytics ≥ 8.0.0 | Python package | YOLOv8n model loading and inference |
| numpy ≥ 1.24.0 | Python package | Array operations |
| Pillow ≥ 9.5.0 | Python package | Image encode/decode |
| YOLOv8n INT8 model file | Model | Fine-tuned on Roboflow fire/smoke dataset |
| USB webcam | Hardware | 15–20 FPS at 320×320 px |
| Raspberry Pi 4 (4 GB) | Hardware | ~1.0–1.3 GB peak RAM usage |

> M4 has **no dependency on M1–M3**. It can be developed and tested using pre-recorded video footage.

---

## Quick-Start Integration Example

```c
#include "m4_vision.h"

int main(void) {
    // Start inference pipeline (spawns background thread)
    if (m4_start_pipeline() != M4_OK) {
        return -1;
    }

    // Poll latest result (called by M6 on every FSM iteration)
    m4_vision_result_t result;
    if (m4_get_latest_result(&result) == M4_OK && result.detection_count > 0) {
        for (int i = 0; i < result.detection_count; i++) {
            if (result.detections[i].confidence > M4_CONF_THRESHOLD) {
                // Notify M6: possible fire/smoke detected
            }
        }
    }

    // Capture JPEG snapshot (called by M6 only in ALARM state)
    uint8_t jpeg_buf[65536];
    uint32_t jpeg_len = 0;
    m4_capture_snapshot(jpeg_buf, sizeof(jpeg_buf), &jpeg_len);

    m4_stop_pipeline();
    return 0;
}
```

---

## API Summary

| Function | Parameters | Returns | Notes |
|---|---|---|---|
| `m4_start_pipeline()` | — | `m4_status_t` | Loads model, opens camera, starts thread |
| `m4_stop_pipeline()` | — | `m4_status_t` | Joins thread, releases camera |
| `m4_get_latest_result(result_out)` | `m4_vision_result_t *` | `m4_status_t` | Thread-safe; non-blocking |
| `m4_capture_snapshot(buf, buf_size, out_len)` | `uint8_t *`, `uint32_t`, `uint32_t *` | `m4_status_t` | JPEG encode of current frame |
| `m4_is_running(running_out)` | `bool *` | `m4_status_t` | Query pipeline status |

---

## Known Limitations & TODOs

- INT8 quantisation may reduce detection accuracy for small smoke plumes; performance benchmarking on actual RPi 4 hardware is pending.
- JPEG snapshot buffer size is currently fixed; dynamic allocation planned for v0.2.
- Only "fire" and "smoke" classes are supported; model retraining required for additional hazard classes.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-01 | Initial draft: pipeline control, detection structs, snapshot API |

# M4 Vision

Current purpose: camera access and obstacle turn-direction hinting for M5.

## Implemented Today

- `init()`
- `capture_frame()`
- `determine_turn_direction()`
- `close()`

`determine_turn_direction()` uses a simple OpenCV edge-based heuristic:
- capture frame
- focus on lower half of the image
- compare left/right visible gap
- return `"LEFT"`, `"RIGHT"`, or `None`

If OpenCV/Numpy are unavailable, M4 stays importable and returns `None`, so navigation can fall back to ultrasonic-only logic.

## Not Implemented Yet

- YOLO fire/smoke inference pipeline
- thread-safe latest-result API for M6
- alarm snapshot orchestration

Older README text that described a fully live YOLO pipeline is design intent, not current repository behavior.

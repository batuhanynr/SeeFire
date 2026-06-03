"""M4 Vision unit tests.

All tests run without a physical camera or YOLO model.
CV-present tests use numpy to synthesise synthetic frames.
Mock-mode tests force CV_AVAILABLE=False via module patching.
"""
import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import m4_vision.vision as vision_module
from m4_vision.vision import VisionM4, _letterbox_crop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frame(w: int = 320, h: int = 240, fill: int = 128):
    """Return a solid-colour BGR numpy frame."""
    import numpy as np
    return np.full((h, w, 3), fill, dtype="uint8")


def _with_mock_cv(fn):
    """Decorator: runs *fn* with CV_AVAILABLE forced to False."""
    import functools

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        orig = vision_module.CV_AVAILABLE
        vision_module.CV_AVAILABLE = False
        try:
            fn(self, *args, **kwargs)
        finally:
            vision_module.CV_AVAILABLE = orig

    return wrapper


# ---------------------------------------------------------------------------
# Mock-mode tests (no camera, no OpenCV required)
# ---------------------------------------------------------------------------

class TestVisionM4MockMode(unittest.TestCase):

    @_with_mock_cv
    def test_init_mock_returns_true(self):
        v = VisionM4()
        self.assertTrue(v.init())

    @_with_mock_cv
    def test_capture_frame_mock_returns_none(self):
        v = VisionM4()
        v.init()
        self.assertIsNone(v.capture_frame())

    @_with_mock_cv
    def test_determine_turn_direction_mock_returns_none(self):
        v = VisionM4()
        self.assertIsNone(v.determine_turn_direction())

    @_with_mock_cv
    def test_determine_turn_direction_with_frame_mock_returns_none(self):
        """Even if a frame object is passed, mock mode should return None."""
        v = VisionM4()
        self.assertIsNone(v.determine_turn_direction(frame=object()))

    @_with_mock_cv
    def test_get_fire_confidence_default_is_zero(self):
        v = VisionM4()
        self.assertEqual(v.get_fire_confidence(), 0.0)

    @_with_mock_cv
    def test_get_smoke_confidence_default_is_zero(self):
        v = VisionM4()
        self.assertEqual(v.get_smoke_confidence(), 0.0)

    @_with_mock_cv
    def test_close_no_crash_in_mock(self):
        v = VisionM4()
        v.init()
        v.close()  # must not raise

    @_with_mock_cv
    def test_thread_not_started_in_mock(self):
        v = VisionM4()
        v.init()
        self.assertIsNone(v._thread)


# ---------------------------------------------------------------------------
# _letterbox_crop tests (pure numpy, no camera)
# ---------------------------------------------------------------------------

class TestLetterboxCrop(unittest.TestCase):

    def setUp(self):
        try:
            import numpy as np  # noqa: F401
            import cv2  # noqa: F401
        except ImportError:
            self.skipTest("OpenCV/numpy not installed")

    def test_already_correct_size_unchanged(self):
        import numpy as np
        frame = np.zeros((240, 320, 3), dtype="uint8")
        out = _letterbox_crop(frame, 320, 240)
        self.assertEqual(out.shape, (240, 320, 3))

    def test_wider_source_cropped_to_target(self):
        """640×480 → 320×240: result must be exactly the target size."""
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype="uint8")
        out = _letterbox_crop(frame, 320, 240)
        self.assertEqual(out.shape, (240, 320, 3))

    def test_tall_source_cropped_to_target(self):
        """320×480 (portrait) → 320×240: no crash, correct size."""
        import numpy as np
        frame = np.zeros((480, 320, 3), dtype="uint8")
        out = _letterbox_crop(frame, 320, 240)
        self.assertEqual(out.shape, (240, 320, 3))

    def test_widescreen_source_cropped_to_target(self):
        """640×360 (16:9) → 320×240 (4:3): no squish, correct size."""
        import numpy as np
        frame = np.zeros((360, 640, 3), dtype="uint8")
        out = _letterbox_crop(frame, 320, 240)
        self.assertEqual(out.shape, (240, 320, 3))

    def test_pixel_values_preserved_in_crop(self):
        """A solid centre patch should survive INTER_AREA downsampling."""
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype="uint8")
        # 20×20 green block centred at (240, 320) — large enough to survive 0.5× downscale
        frame[230:250, 310:330] = [0, 255, 0]
        out = _letterbox_crop(frame, 320, 240)
        cy, cx = out.shape[0] // 2, out.shape[1] // 2
        self.assertEqual(out[cy, cx].tolist(), [0, 255, 0])


# ---------------------------------------------------------------------------
# determine_turn_direction logic tests (synthetic frames)
# ---------------------------------------------------------------------------

class TestDetermineTurnDirection(unittest.TestCase):

    def setUp(self):
        try:
            import numpy as np  # noqa: F401
            import cv2  # noqa: F401
        except ImportError:
            self.skipTest("OpenCV/numpy not installed")
        if os.environ.get("SEEFIRE_FORCE_MOCK") == "1":
            self.skipTest("Force-mock env set")

    def _turn(self, frame) -> str:
        orig = vision_module.CV_AVAILABLE
        vision_module.CV_AVAILABLE = True
        try:
            v = VisionM4()
            return v.determine_turn_direction(frame=frame)
        finally:
            vision_module.CV_AVAILABLE = orig

    def test_blank_frame_returns_none(self):
        """No edges → no obstacle detected → None."""
        import numpy as np
        frame = np.zeros((240, 320, 3), dtype="uint8")
        self.assertIsNone(self._turn(frame))

    def test_obstacle_on_right_returns_left(self):
        """Dense horizontal stripes on right half → more edge pixels right → 'LEFT'."""
        import numpy as np
        frame = np.zeros((240, 320, 3), dtype="uint8")
        # Horizontal lines every 10px on the right half → many Canny edges on right
        frame[::10, 160:, :] = 255
        result = self._turn(frame)
        self.assertEqual(result, "LEFT")

    def test_obstacle_on_left_returns_right(self):
        """Dense horizontal stripes on left half → more edge pixels left → 'RIGHT'."""
        import numpy as np
        frame = np.zeros((240, 320, 3), dtype="uint8")
        # Horizontal lines every 10px on the left half → many Canny edges on left
        frame[::10, :160, :] = 255
        result = self._turn(frame)
        self.assertEqual(result, "RIGHT")


# ---------------------------------------------------------------------------
# Thread-safety: yolo_result updated atomically
# ---------------------------------------------------------------------------

class TestYoloResultThreadSafety(unittest.TestCase):

    def test_result_dict_is_read_under_lock(self):
        v = VisionM4()
        # Manually set result, simulate concurrent read
        v._yolo_result = {"fire_conf": 0.85, "smoke_conf": 0.42}
        results = []

        def reader():
            for _ in range(100):
                results.append(v.get_fire_confidence())

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(all(r == 0.85 for r in results))

    def test_smoke_confidence_reflects_stored_value(self):
        v = VisionM4()
        v._yolo_result = {"fire_conf": 0.0, "smoke_conf": 0.73}
        self.assertAlmostEqual(v.get_smoke_confidence(), 0.73)


# ---------------------------------------------------------------------------
# Module-level singleton API
# ---------------------------------------------------------------------------

class TestModuleLevelAPI(unittest.TestCase):

    def test_module_functions_callable(self):
        import m4_vision
        for fn_name in ("init", "capture_frame", "determine_turn_direction",
                        "close", "get_fire_confidence", "get_smoke_confidence"):
            fn = getattr(m4_vision, fn_name)
            self.assertTrue(callable(fn), f"{fn_name} is not callable")

    def test_fire_confidence_returns_float(self):
        import m4_vision
        self.assertIsInstance(m4_vision.get_fire_confidence(), float)

    def test_smoke_confidence_returns_float(self):
        import m4_vision
        self.assertIsInstance(m4_vision.get_smoke_confidence(), float)


if __name__ == "__main__":
    unittest.main()

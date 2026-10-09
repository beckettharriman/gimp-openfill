# SPDX-License-Identifier: GPL-3.0-or-later
"""The pure geometry of the Generative Expand editor (no GTK needed)."""

import unittest

from stable_boy import ui_expand as ue
from stable_boy.ui_expand import Margins


class MarginTests(unittest.TestCase):
    def test_from_dict_clamps_and_tolerates_junk(self):
        m = Margins.from_dict({"left": 5000, "top": -3, "right": "12", "bottom": None})
        self.assertEqual(m, Margins(4096, 0, 12, 0))
        self.assertEqual(Margins.from_dict({"left": "x"}), Margins())
        self.assertEqual(Margins(1, 2, 3, 4).as_dict(), {"left": 1, "top": 2, "right": 3, "bottom": 4})

    def test_canvas_and_empty(self):
        self.assertEqual(Margins(256, 0, 256, 0).canvas(1024, 768), (1536, 768))
        self.assertTrue(Margins().is_empty())
        self.assertFalse(Margins(bottom=1).is_empty())

    def test_clamp_margin(self):
        self.assertEqual(ue.clamp_margin(-1), 0)
        self.assertEqual(ue.clamp_margin(10.6), 11)
        self.assertEqual(ue.clamp_margin(99999), ue.MAX_MARGIN)
        self.assertEqual(ue.clamp_margin(float("nan")), 0)
        self.assertEqual(ue.clamp_margin(300, limit=256), 256)


class PresetTests(unittest.TestCase):
    def test_split(self):
        self.assertEqual(ue.split(100, 0), (0, 100))
        self.assertEqual(ue.split(101, 1), (50, 51))
        self.assertEqual(ue.split(100, 2), (100, 0))
        self.assertEqual(ue.split(-5, 1), (0, 0))

    def test_wide_preset_on_landscape_adds_width(self):
        # 1024 x 768 (4:3) to 16:9: the height stays, the width becomes 1366
        m = ue.preset_margins(1024, 768, "16:9", "center")
        self.assertEqual(m.canvas(1024, 768), (1366, 768))
        self.assertEqual((m.left, m.right, m.top, m.bottom), (171, 171, 0, 0))

    def test_tall_preset_adds_height_with_anchor(self):
        m = ue.preset_margins(1024, 768, "9:16", "top")
        w, h = m.canvas(1024, 768)
        self.assertEqual(w, 1024)
        self.assertAlmostEqual(w / h, 9 / 16, places=2)
        self.assertEqual((m.top, m.left, m.right), (0, 0, 0))
        self.assertEqual(m.bottom, h - 768)

    def test_every_ratio_contains_the_image_and_matches(self):
        for pid, _label, ratio in ue.PRESETS:
            if ratio is None:
                continue
            for size in ((1024, 768), (768, 1024), (512, 512), (1920, 1080), (300, 2000)):
                m = ue.preset_margins(*size, pid)
                w, h = m.canvas(*size)
                self.assertGreaterEqual(w, size[0])
                self.assertGreaterEqual(h, size[1])
                self.assertFalse(m.is_empty(), (pid, size))
                self.assertLess(abs(w / h - ratio[0] / ratio[1]), 0.01, (pid, size, w, h))

    def test_original_and_equal_ratio_grow(self):
        m = ue.preset_margins(1000, 500, "original")
        self.assertEqual(m.canvas(1000, 500), (1250, 625))
        self.assertEqual(m, Margins(125, 62, 125, 63))
        square = ue.preset_margins(512, 512, "1:1", "bottom-right")
        self.assertEqual(square, Margins(128, 128, 0, 0))

    def test_custom_and_unknown(self):
        self.assertIsNone(ue.preset_margins(100, 100, "custom"))
        self.assertIsNone(ue.preset_margins(100, 100, "nope"))

    def test_limit_is_respected(self):
        m = ue.preset_margins(4096, 512, "9:16", "top")
        self.assertEqual(m.bottom, ue.MAX_MARGIN)

    def test_reanchor_keeps_totals(self):
        m = Margins(10, 20, 90, 0)
        self.assertEqual(ue.reanchor(m, "top-left"), Margins(0, 0, 100, 20))
        self.assertEqual(ue.reanchor(m, "center"), Margins(50, 10, 50, 10))
        self.assertEqual(ue.reanchor(m, "bottom-right"), Margins(100, 20, 0, 0))

    def test_anchor_of(self):
        self.assertEqual(ue.anchor_of(Margins(0, 0, 256, 0)), "left")
        self.assertEqual(ue.anchor_of(Margins(256, 0, 0, 256)), "top-right")
        self.assertEqual(ue.anchor_of(Margins(5, 5, 7, 7)), "center")
        self.assertEqual(ue.anchor_of(Margins(), "bottom-left"), "bottom-left")
        self.assertEqual(ue.anchor_of(Margins(0, 0, 10, 0), "bottom-right"), "bottom-left")

    def test_matching_preset(self):
        m = ue.preset_margins(1024, 768, "16:9", "left")
        self.assertEqual(ue.matching_preset(1024, 768, m, "left"), "16:9")
        self.assertEqual(ue.matching_preset(1024, 768, Margins(1, 0, 0, 0), "center"), "custom")


class LayoutTests(unittest.TestCase):
    def test_image_fits_thumb_and_canvas_is_centred(self):
        v = ue.fit_view(600, 380, 1024, 768, Margins())
        self.assertAlmostEqual(v.iw, 360)
        self.assertAlmostEqual(v.ih, 270)
        self.assertAlmostEqual(v.fx + v.fw / 2, 300)
        self.assertAlmostEqual(v.fy + v.fh / 2, 190)
        self.assertEqual((v.fx, v.fy, v.fw, v.fh), (v.ix, v.iy, v.iw, v.ih))

    def test_large_margins_shrink_the_view(self):
        v = ue.fit_view(600, 380, 1024, 768, Margins(2048, 0, 2048, 0))
        self.assertLessEqual(v.fw, 600 - 2 * ue.PAD + 1e-6)
        self.assertGreaterEqual(v.fx, ue.PAD - 1e-6)
        self.assertAlmostEqual(v.ix - v.fx, 2048 * v.scale)

    def test_view_at_keeps_image_still(self):
        v = ue.view_at(0.5, 100, 50, 400, 200, Margins(40, 0, 0, 20))
        self.assertEqual((v.ix, v.iy, v.iw, v.ih), (100, 50, 200, 100))
        self.assertEqual((v.fx, v.fy, v.fw, v.fh), (80, 50, 220, 110))


class HitTests(unittest.TestCase):
    def setUp(self):
        # frame from (100, 50) to (400, 250)
        self.v = ue.view_at(1.0, 150, 50, 250, 200, Margins(50, 0, 0, 0))

    def test_corners_and_edges(self):
        self.assertEqual(ue.hit_test(self.v, 101, 52), "top-left")
        self.assertEqual(ue.hit_test(self.v, 398, 249), "bottom-right")
        self.assertEqual(ue.hit_test(self.v, 405, 150), "right")
        self.assertEqual(ue.hit_test(self.v, 104, 120), "left")
        self.assertEqual(ue.hit_test(self.v, 250, 46), "top")
        self.assertEqual(ue.hit_test(self.v, 250, 255), "bottom")

    def test_misses(self):
        self.assertIsNone(ue.hit_test(self.v, 250, 150))  # inside
        self.assertIsNone(ue.hit_test(self.v, 20, 150))  # far left
        self.assertIsNone(ue.hit_test(self.v, 400, 300))  # below the right edge

    def test_zero_size_frame_still_has_handles(self):
        v = ue.view_at(1.0, 100, 100, 50, 50, Margins())
        self.assertEqual(ue.hit_test(v, 151, 125), "right")
        self.assertEqual(set(ue.handle_points(v)), set(ue.HANDLES))
        self.assertEqual(set(ue.CURSORS), set(ue.HANDLES))


class DragTests(unittest.TestCase):
    def test_outward_adds_and_snaps(self):
        start = Margins(0, 0, 0, 0)
        self.assertEqual(ue.drag_margins(start, "right", 50, 0, 0.5), Margins(0, 0, 104, 0))
        self.assertEqual(ue.drag_margins(start, "left", -50, 7, 0.5), Margins(104, 0, 0, 0))
        self.assertEqual(ue.drag_margins(start, "top", 0, -10, 0.25), Margins(0, 40, 0, 0))
        self.assertEqual(ue.drag_margins(start, "bottom-right", 32, 16, 0.5), Margins(0, 0, 64, 32))
        self.assertEqual(ue.drag_margins(start, "top-left", -32, -16, 0.5), Margins(64, 32, 0, 0))

    def test_inward_and_limits(self):
        start = Margins(100, 0, 100, 0)
        self.assertEqual(ue.drag_margins(start, "right", -500, 0, 1.0), Margins(100, 0, 0, 0))
        self.assertEqual(ue.drag_margins(start, "left", -99999, 0, 1.0).left, ue.MAX_MARGIN)
        self.assertEqual(ue.drag_margins(start, "left", -500, 0, 1.0, limit=256).left, 256)

    def test_other_sides_keep_exact_values(self):
        start = Margins(13, 7, 0, 0)
        self.assertEqual(ue.drag_margins(start, "right", 40, 0, 1.0), Margins(13, 7, 40, 0))
        self.assertEqual(ue.drag_margins(start, "nonsense", 40, 0, 1.0), start)
        self.assertEqual(ue.drag_margins(start, "right", 40, 0, 0), start)


class StateTests(unittest.TestCase):
    def test_initial_values(self):
        s = ue.ExpandState(1024, 768, Margins(256, 0, 256, 0))
        self.assertEqual(s.anchor, "center")
        self.assertEqual(s.preset, "custom")
        self.assertEqual(s.canvas, (1536, 768))

    def test_preset_then_anchor_then_drag(self):
        calls = []
        s = ue.ExpandState(1024, 768, Margins(), listener=lambda: calls.append(1))
        s.apply_preset("16:9")
        self.assertEqual(s.preset, "16:9")
        self.assertEqual(s.canvas, (1366, 768))
        s.set_anchor("left")
        self.assertEqual(s.margins, Margins(0, 0, 342, 0))
        self.assertEqual(s.preset, "16:9")
        s.set_side("top", 64)
        self.assertEqual(s.preset, "custom")
        self.assertEqual(s.anchor, "bottom-left")
        self.assertEqual(len(calls), 3)

    def test_custom_keeps_margins_and_unknowns_are_ignored(self):
        s = ue.ExpandState(800, 600, Margins(10, 0, 10, 0))
        s.apply_preset("custom")
        self.assertEqual(s.margins, Margins(10, 0, 10, 0))
        s.apply_preset("bogus")
        s.set_anchor("bogus")
        s.set_side("middle", 5)
        self.assertEqual(s.margins, Margins(10, 0, 10, 0))

    def test_setting_the_preset_margins_by_hand_selects_it(self):
        s = ue.ExpandState(1024, 768, Margins())
        s.set_margins(ue.preset_margins(1024, 768, "1:1", "center"))
        self.assertEqual(s.preset, "1:1")

    def test_no_listener_call_without_change(self):
        calls = []
        s = ue.ExpandState(100, 100, Margins(8, 0, 0, 0), listener=lambda: calls.append(1))
        s.set_side("left", 8)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

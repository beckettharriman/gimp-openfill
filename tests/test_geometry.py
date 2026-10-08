# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from stable_boy import geometry as g


class RectTests(unittest.TestCase):
    def test_intersect_and_contains(self):
        a, b = g.Rect(0, 0, 100, 100), g.Rect(50, 50, 100, 100)
        self.assertEqual(a.intersect(b), g.Rect(50, 50, 50, 50))
        self.assertTrue(a.contains(g.Rect(10, 10, 20, 20)))
        self.assertFalse(a.contains(b))
        self.assertTrue(g.Rect(0, 0, 0, 5).is_empty())

    def test_relative_to(self):
        self.assertEqual(g.Rect(30, 40, 5, 5).relative_to(g.Rect(10, 10, 100, 100)), g.Rect(20, 30, 5, 5))


class ContextRectTests(unittest.TestCase):
    image = g.Rect(0, 0, 2000, 1500)

    def test_small_selection_gets_minimum_context(self):
        ctx = g.context_rect(g.Rect(900, 700, 40, 40), self.image, g.SD15)
        self.assertEqual(ctx.size, (512, 512))
        self.assertTrue(ctx.contains(g.Rect(900, 700, 40, 40)))
        self.assertTrue(self.image.contains(ctx))

    def test_padding_scales_with_selection(self):
        sel = g.Rect(500, 500, 600, 400)
        ctx = g.context_rect(sel, self.image, g.SD15)
        pad = round(600 * 0.35)
        self.assertEqual(ctx.size, (600 + 2 * pad, 400 + 2 * pad))
        self.assertTrue(ctx.contains(sel))

    def test_clamped_to_image_edges(self):
        ctx = g.context_rect(g.Rect(0, 0, 30, 30), self.image, g.SDXL)
        self.assertEqual(ctx, g.Rect(0, 0, 768, 768))
        ctx = g.context_rect(g.Rect(1990, 1490, 10, 10), self.image, g.SD15)
        self.assertEqual((ctx.right, ctx.bottom), (2000, 1500))

    def test_image_smaller_than_minimum(self):
        small = g.Rect(0, 0, 300, 200)
        ctx = g.context_rect(g.Rect(10, 10, 50, 50), small, g.SD15)
        self.assertEqual(ctx, small)

    def test_empty_selection_rejected(self):
        with self.assertRaises(ValueError):
            g.context_rect(g.Rect(0, 0, 0, 0), self.image, g.SD15)


class WorkingSizeTests(unittest.TestCase):
    def test_identity_when_in_range(self):
        ws = g.working_size(640, 512, g.SD15)
        self.assertEqual((ws.width, ws.height, ws.scale), (640, 512, 1.0))

    def test_downscale_large_region(self):
        ws = g.working_size(2000, 1500, g.SD15)
        self.assertEqual(ws.width, 768)
        self.assertEqual(ws.height % 8, 0)
        self.assertLessEqual(ws.height, 768)

    def test_upscale_small_region_capped(self):
        ws = g.working_size(200, 100, g.SD15)
        self.assertLessEqual(ws.width / 200, 2.0 + 1e-9)
        self.assertEqual(ws.width % 8, 0)
        ws = g.working_size(300, 200, g.SD15)
        self.assertEqual((ws.width, ws.height), (600, 400))

    def test_upscale_never_exceeds_max_side(self):
        ws = g.working_size(700, 300, g.SD15)
        self.assertLessEqual(max(ws.width, ws.height), 768)

    def test_sdxl_profile(self):
        ws = g.working_size(3000, 2000, g.SDXL)
        self.assertEqual(ws.width, 1024)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            g.working_size(0, 10, g.SD15)


class ExpandTests(unittest.TestCase):
    def test_single_side(self):
        plan = g.plan_expand(800, 600, 256, 0, 0, 0, g.SD15)
        self.assertEqual((plan.new_width, plan.new_height), (1056, 600))
        self.assertEqual((plan.offset_x, plan.offset_y), (256, 0))
        self.assertEqual(plan.grows, (True, False, False, False))
        self.assertEqual(plan.keep_rect, g.Rect(288, 0, 768, 600))
        self.assertEqual(plan.fill_rect, g.Rect(0, 0, 288, 600))
        self.assertTrue(plan.context.contains(plan.fill_rect))
        self.assertTrue(g.Rect(0, 0, 1056, 600).contains(plan.context))

    def test_all_sides_fill_is_canvas(self):
        plan = g.plan_expand(400, 400, 50, 50, 50, 50, g.SD15)
        self.assertEqual(plan.fill_rect, g.Rect(0, 0, 500, 500))
        self.assertEqual(plan.keep_rect, g.Rect(82, 82, 336, 336))

    def test_mask_marks_new_area_and_overlap(self):
        plan = g.plan_expand(800, 600, 256, 0, 0, 0, g.SD15)
        mask = g.mask_for_expand(plan)
        ctx = plan.context
        self.assertEqual(len(mask), ctx.area)
        # new border column -> 255; overlap band -> 255; untouched old pixels -> 0
        self.assertEqual(mask[0], 255)
        self.assertEqual(mask[(256 + 10) - ctx.x], 255)
        self.assertEqual(mask[(256 + 40) - ctx.x], 0)

    def test_rejects_bad_margins(self):
        with self.assertRaises(ValueError):
            g.plan_expand(100, 100, 0, 0, 0, 0, g.SD15)
        with self.assertRaises(ValueError):
            g.plan_expand(100, 100, -1, 0, 0, 0, g.SD15)


class MiscTests(unittest.TestCase):
    def test_round_to_multiple(self):
        self.assertEqual(g.round_to_multiple(515, 8), 512)
        self.assertEqual(g.round_to_multiple(3, 8), 8)

    def test_seed(self):
        self.assertEqual(g.seed_or_random(7), 7)
        import random
        self.assertEqual(g.seed_or_random(-1, random.Random(1)), random.Random(1).randrange(0, 2**32 - 1))

    def test_timeout_has_floor(self):
        self.assertGreaterEqual(g.estimate_timeout(1, 1, 1000), 120)
        self.assertGreater(g.estimate_timeout(50, 4, 1024 * 1024), g.estimate_timeout(10, 1, 1024 * 1024))


if __name__ == "__main__":
    unittest.main()

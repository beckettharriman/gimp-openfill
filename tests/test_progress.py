# SPDX-License-Identifier: GPL-3.0-or-later
import json
import struct
import unittest

from stable_boy import progress as pr


class PreviewFrameTests(unittest.TestCase):
    def test_preview_image_jpeg_and_png(self):
        jpeg = struct.pack(">II", 1, 1) + b"\xff\xd8\xff" + b"x" * 10
        f = pr.parse_preview_frame(jpeg)
        self.assertEqual(f.mime, "image/jpeg")
        self.assertTrue(f.data.startswith(b"\xff\xd8"))
        png = struct.pack(">II", 1, 2) + b"\x89PNG" + b"y" * 10
        self.assertEqual(pr.parse_preview_frame(png).mime, "image/png")

    def test_preview_with_metadata(self):
        meta = json.dumps({"image_type": "image/png", "node_id": "sampler"}).encode()
        payload = struct.pack(">II", 4, len(meta)) + meta + b"\x89PNGdata"
        f = pr.parse_preview_frame(payload)
        self.assertEqual(f.mime, "image/png")
        self.assertEqual(f.metadata["node_id"], "sampler")
        self.assertEqual(f.data, b"\x89PNGdata")

    def test_ignores_text_and_truncated_frames(self):
        self.assertIsNone(pr.parse_preview_frame(struct.pack(">I", 3) + b"hello"))
        self.assertIsNone(pr.parse_preview_frame(b"\x00\x00"))
        self.assertIsNone(pr.parse_preview_frame(struct.pack(">II", 1, 1)))  # no image bytes
        self.assertIsNone(pr.parse_preview_frame(struct.pack(">II", 4, 999) + b"{}"))  # bad length


class EtaTests(unittest.TestCase):
    def test_linear_progress_estimates_remaining(self):
        eta = pr.Eta()
        self.assertIsNone(eta.update(0.0, 0.0))        # below threshold
        self.assertIsNone(eta.update(2.0, 0.1))        # first sample sets the baseline
        remaining = eta.update(4.0, 0.3)               # 0.2 per 2 s -> 0.7 left = 7 s
        self.assertAlmostEqual(remaining, 7.0, places=5)
        later = eta.update(6.0, 0.5)                   # damped toward 5 s
        self.assertLess(later, 7.0)
        self.assertGreater(later, 5.0)

    def test_restart_when_fraction_goes_backwards(self):
        eta = pr.Eta()
        eta.update(1.0, 0.5)
        eta.update(2.0, 0.6)
        self.assertIsNone(eta.update(3.0, 0.1))  # new phase: baseline reset
        self.assertIsNotNone(eta.update(4.0, 0.2))

    def test_format_duration(self):
        self.assertEqual(pr.format_duration(None), "--:--")
        self.assertEqual(pr.format_duration(0), "0:00")
        self.assertEqual(pr.format_duration(65), "1:05")
        self.assertEqual(pr.format_duration(3725), "1:02:05")


class ThrottleTests(unittest.TestCase):
    def test_admits_at_most_one_frame_per_interval(self):
        now = [0.0]
        t = pr.FrameThrottle(0.25, clock=lambda: now[0])
        self.assertTrue(t.admit())
        now[0] = 0.1
        self.assertFalse(t.admit())
        now[0] = 0.2
        self.assertFalse(t.admit())
        now[0] = 0.26
        self.assertTrue(t.admit())
        self.assertEqual((t.admitted, t.dropped), (2, 2))

    def test_fit_within(self):
        self.assertEqual(pr.fit_within(1024, 512, 320), (320, 160))
        self.assertEqual(pr.fit_within(200, 100, 320), (200, 100))
        self.assertEqual(pr.fit_within(0, 0, 320), (1, 1))

    def test_download_row(self):
        text = pr.download_row({"file": "inpaint/big-lama.pt", "done": 50 * 1048576, "total": 200 * 1048576,
                                "speed": 5 * 1048576})
        self.assertEqual(text, "big-lama.pt  25%  5.0 MB/s")
        self.assertIn("...", pr.download_row({"model_id": "x"}))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path

from stable_boy.config import Paths, Settings, comfy_layout


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            s = Settings(steps=31, cfg=5.5, autostart=False, checkpoint="x.ckpt")
            s.save(path)
            loaded = Settings.load(path)
            self.assertEqual((loaded.steps, loaded.cfg, loaded.autostart, loaded.checkpoint),
                             (31, 5.5, False, "x.ckpt"))

    def test_missing_or_broken_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(Settings.load(path).steps, Settings().steps)
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(Settings.load(path).backend, "comfyui")

    def test_unknown_keys_and_coercion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"steps": "40", "autostart": "false", "cfg": 3, "bogus": 1}),
                            encoding="utf-8")
            s = Settings.load(path)
            self.assertEqual(s.steps, 40)
            self.assertFalse(s.autostart)
            self.assertEqual(s.cfg, 3.0)
            self.assertFalse(hasattr(s, "bogus"))

    def test_model_for(self):
        s = Settings(sdxl_checkpoint="sdxl.safetensors", fooocus_head="h", fooocus_patch="p")
        self.assertEqual(s.model_for("fast").arch, "sd15")
        q = s.model_for("quality")
        self.assertEqual(q.arch, "sdxl")
        self.assertTrue(q.uses_fooocus)
        s.sdxl_checkpoint = ""
        self.assertEqual(s.model_for("quality").arch, "sd15")

    def test_active_url(self):
        s = Settings(backend="a1111", a1111_url="http://x:1")
        self.assertEqual(s.active_url, "http://x:1")


class PathsTests(unittest.TestCase):
    def test_layout(self):
        p = Paths.for_profile("/gimp/3.2")
        self.assertEqual(p.config.name, "config.json")
        self.assertEqual(p.state.parent.name, "stable-boy")
        self.assertEqual(p.temp, p.base / "tmp")


class ComfyLayoutTests(unittest.TestCase):
    def test_portable_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(comfy_layout(root))
            (root / "python_embeded").mkdir()
            (root / "python_embeded" / "python.exe").write_bytes(b"")
            (root / "ComfyUI").mkdir()
            (root / "ComfyUI" / "main.py").write_text("")
            layout = comfy_layout(root)
            self.assertEqual(layout["main"], root / "ComfyUI" / "main.py")
            self.assertEqual(layout["cwd"], root)

    def test_checkout_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("")
            layout = comfy_layout(root)
            self.assertEqual(layout["main"], root / "main.py")


if __name__ == "__main__":
    unittest.main()

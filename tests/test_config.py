# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path

from stable_boy.config import Paths, Settings, comfy_layout
from stable_boy.log import RedactingFilter, get_logger, redact

TOKEN = "hf_abcdefghijklmnopqrstuvwxyz0123456789"


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            s = Settings(steps=31, cfg=5.5, autostart=False, checkpoint="x.ckpt")
            s.save(path)
            loaded = Settings.load(path)
            self.assertEqual(
                (loaded.steps, loaded.cfg, loaded.autostart, loaded.checkpoint), (31, 5.5, False, "x.ckpt")
            )

    def test_missing_or_broken_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(Settings.load(path).steps, Settings().steps)
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(Settings.load(path).backend, "comfyui")

    def test_unknown_keys_and_coercion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"steps": "40", "autostart": "false", "cfg": 3, "bogus": 1}), encoding="utf-8")
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


class TokenStorageTests(unittest.TestCase):
    def test_token_roundtrips_through_config_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = Paths.for_profile(tmp).ensure()
            s = Settings(hf_token=TOKEN)
            s.save(paths.config)
            self.assertEqual(Settings.load(paths.config).hf_token, TOKEN)
            self.assertEqual(json.loads(paths.config.read_text(encoding="utf-8"))["hf_token"], TOKEN)
            # nothing else in the profile folder holds it
            others = [p for p in paths.base.rglob("*") if p.is_file() and p != paths.config]
            for other in others:
                self.assertNotIn(TOKEN, other.read_text(encoding="utf-8", errors="replace"), other)

    def test_token_not_in_repr(self):
        s = Settings(hf_token=TOKEN)
        self.assertNotIn(TOKEN, repr(s))
        self.assertNotIn(TOKEN, str(s))

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_config_is_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            Settings(hf_token=TOKEN).save(path)
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_redact(self):
        self.assertNotIn(TOKEN, redact(f"token {TOKEN} here"))
        self.assertEqual(redact("Authorization: Bearer abc.def"), "Authorization: Bearer [redacted]")
        self.assertNotIn("secretvalue", redact('{"hf_token": "secretvalue", "steps": 25}'))
        self.assertIn('"steps": 25', redact('{"hf_token": "secretvalue", "steps": 25}'))
        self.assertEqual(redact("plain message, 25 steps"), "plain message, 25 steps")

    def test_logger_redacts_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = get_logger(Path(tmp) / "x.log", name="stable-boy-test-redact")
            stream = io.StringIO()
            extra = logging.StreamHandler(stream)
            log.addHandler(extra)
            try:
                log.info("settings: %s", {"hf_token": TOKEN})
                log.info("header Bearer %s", TOKEN)
            finally:
                log.removeHandler(extra)
                for h in list(log.handlers):
                    h.close()
                    log.removeHandler(h)
            self.assertNotIn(TOKEN, stream.getvalue())
            self.assertIn("[redacted]", stream.getvalue())
            self.assertTrue(any(isinstance(f, RedactingFilter) for f in log.filters))


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

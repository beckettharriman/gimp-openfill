# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
import tempfile
import unittest
from pathlib import Path

from stable_boy import catalog as cat

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "models" / "catalog.json"


class ShippedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.entries = cat.load_catalog(CATALOG)

    def test_loads_and_has_required_entries(self):
        ids = {e.id for e in self.entries}
        for required in ("sd15-inpainting", "sdxl-base", "fooocus-inpaint-patch", "juggernaut-xl-v9",
                         "flux1-fill-dev-gguf-q4", "qwen-image-edit-2511-gguf-q4", "lama-big", "mat-places512"):
            self.assertIn(required, ids)

    def test_every_entry_is_well_formed(self):
        for e in self.entries:
            self.assertTrue(e.license_name and e.license_url.startswith("https://"), e.id)
            self.assertTrue(e.page.startswith("https://"), e.id)
            self.assertIn(e.source_type, cat.SOURCE_TYPES)
            if e.source_type == "community-quantization":
                self.assertTrue(e.uploader, e.id)
            for f in e.files:
                self.assertTrue(f.url.startswith("https://huggingface.co/") or f.url.startswith("https://github.com/"), f.url)
                self.assertTrue(f.size and f.size > 0, f.dest)
                self.assertIn("/", f.dest)
            for n in e.requires_nodes:
                self.assertEqual(len(n.commit), 40, n.folder)

    def test_gated_flags(self):
        flux = cat.by_id(self.entries, "flux1-fill-dev-gguf-q4")
        self.assertTrue(flux.gated)
        self.assertTrue(flux.file_by_role("vae").gated)
        self.assertFalse(flux.file_by_role("unet").gated)
        self.assertFalse(cat.by_id(self.entries, "mat-places512").gated)

    def test_gguf_tiers_require_gguf_nodes(self):
        for mid in ("flux1-fill-dev-gguf-q4", "qwen-image-edit-2511-gguf-q4"):
            folders = [n.folder for n in cat.by_id(self.entries, mid).requires_nodes]
            self.assertIn("ComfyUI-GGUF", folders)

    def test_search_paths(self):
        paths = cat.catalog_search_paths(REPO / "gimp-stable-boy")
        self.assertEqual(paths[1], CATALOG)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(CATALOG.read_text(encoding="utf-8"))

    def _expect(self, mutate, fragment):
        data = copy.deepcopy(self.data)
        mutate(data)
        with self.assertRaises(cat.CatalogError) as ctx:
            cat.parse_catalog(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_duplicate_id(self):
        self._expect(lambda d: d["models"].append(copy.deepcopy(d["models"][0])), "duplicate")

    def test_bad_tier_capability_template(self):
        self._expect(lambda d: d["models"][0].__setitem__("tier", "ultra"), "tier")
        self._expect(lambda d: d["models"][0]["capabilities"].append("fly"), "capability")
        self._expect(lambda d: d["models"][0].__setitem__("template", "nope"), "template")

    def test_unsafe_dest_and_http_url(self):
        self._expect(lambda d: d["models"][0]["files"][0].__setitem__("dest", "../x.ckpt"), "unsafe dest")
        self._expect(lambda d: d["models"][0]["files"][0].__setitem__("url", "http://x/y"), "https")

    def test_bad_sha_and_commit(self):
        self._expect(lambda d: d["models"][0]["files"][0].__setitem__("sha256", "abc"), "sha256")
        self._expect(lambda d: d["models"][1]["requires_nodes"][0].__setitem__("commit", "12"), "pinned commit")

    def test_unknown_dependency(self):
        self._expect(lambda d: d["models"][1].__setitem__("requires_models", ["ghost"]), "unknown model")


class StatusTests(unittest.TestCase):
    def test_install_status_and_label(self):
        entries = cat.load_catalog(CATALOG)
        mat = cat.by_id(entries, "mat-places512")
        sdxl = cat.by_id(entries, "sdxl-base")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            nodes = Path(tmp) / "custom_nodes"
            st = cat.install_status(mat, root, nodes)
            self.assertFalse(st.installed)
            self.assertEqual(st.label, "Available")
            (root / "inpaint").mkdir(parents=True)
            (root / "inpaint" / "MAT_Places512_G_fp16.safetensors.part").write_bytes(b"x")
            self.assertEqual(cat.install_status(mat, root, nodes).label, "Partial")
            f = mat.files[0]
            with open(root / f.dest, "wb") as fh:
                fh.truncate(f.size)
            st = cat.install_status(mat, root, nodes)
            self.assertTrue(st.installed)
            self.assertEqual(st.label, "Needs node")
            (nodes / "comfyui-inpaint-nodes").mkdir(parents=True)
            self.assertEqual(cat.install_status(mat, root, nodes).label, "Installed")
            # companion model requirement
            (root / "checkpoints").mkdir(exist_ok=True)
            with open(root / sdxl.files[0].dest, "wb") as fh:
                fh.truncate(sdxl.files[0].size)
            st = cat.install_status(sdxl, root, nodes, entries)
            self.assertEqual(st.label, "Needs model")
            self.assertEqual(st.missing_models, ["fooocus-inpaint-patch"])

    def test_wrong_size_counts_as_missing(self):
        entries = cat.load_catalog(CATALOG)
        mat = cat.by_id(entries, "mat-places512")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inpaint").mkdir()
            (root / mat.files[0].dest).write_bytes(b"short")
            self.assertFalse(cat.install_status(mat, root, None).installed)

    def test_server_listing(self):
        entries = cat.load_catalog(CATALOG)
        sd15 = cat.by_id(entries, "sd15-inpainting")
        with tempfile.TemporaryDirectory() as tmp:
            st = cat.install_status(sd15, Path(tmp), None, server_files=["sd-v1-5-inpainting.ckpt"])
            self.assertTrue(st.seen_by_server)
            st = cat.install_status(sd15, Path(tmp), None, server_files=[])
            self.assertFalse(st.seen_by_server)


class ModelSpecTests(unittest.TestCase):
    def test_specs(self):
        entries = cat.load_catalog(CATALOG)
        spec = cat.model_spec_for(cat.by_id(entries, "juggernaut-xl-v9"), entries)
        self.assertEqual(spec.checkpoint, "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors")
        self.assertEqual(spec.fooocus_patch, "inpaint_v26.fooocus.patch")
        self.assertTrue(spec.uses_fooocus)
        flux = cat.model_spec_for(cat.by_id(entries, "flux1-fill-dev-gguf-q4"), entries)
        self.assertEqual((flux.unet, flux.clip2, flux.vae), ("flux1-fill-dev-Q4_0.gguf", "clip_l.safetensors", "ae.safetensors"))
        self.assertEqual(flux.effective_template, "flux_fill")
        lama = cat.model_spec_for(cat.by_id(entries, "lama-big"), entries)
        self.assertTrue(lama.prompt_free)
        with self.assertRaises(cat.CatalogError):
            cat.model_spec_for(cat.by_id(entries, "fooocus-inpaint-patch"), entries)

    def test_human_size(self):
        self.assertEqual(cat.human_size(0), "?")
        self.assertEqual(cat.human_size(4265437280), "4.0 GB")
        self.assertEqual(cat.human_size(52602), "51 KB")


if __name__ == "__main__":
    unittest.main()

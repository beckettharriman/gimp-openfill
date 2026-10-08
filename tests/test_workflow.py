# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from stable_boy import workflow as w
from stable_boy.backend import InpaintRequest, ModelSpec, Sampling, Txt2ImgRequest


def _req(**overrides) -> InpaintRequest:
    base = dict(image_png=b"", mask_png=b"", width=600, height=400, work_width=768, work_height=512,
                prompt="a red fox", negative="blurry", model=ModelSpec("sd15.ckpt"),
                sampling=Sampling(steps=20, batch=1, seed=5))
    base.update(overrides)
    return InpaintRequest(**base)


def _links(graph: dict, node_id: str) -> dict:
    return {k: v for k, v in graph[node_id]["inputs"].items() if isinstance(v, list)}


class InpaintGraphTests(unittest.TestCase):
    def test_sd15_graph_core_nodes_only(self):
        graph = w.build_inpaint(_req(), "sb/i.png", "sb/m.png", 123, w.Capabilities(False))
        classes = {n["class_type"] for n in graph.values()}
        self.assertNotIn("INPAINT_ExpandMask", classes)
        self.assertIn("GrowMask", classes)
        self.assertIn("InpaintModelConditioning", classes)
        self.assertIn("DifferentialDiffusion", classes)
        self.assertEqual(graph["sampler"]["inputs"]["seed"], 123)
        self.assertEqual(graph["sampler"]["inputs"]["latent_image"], ["encode", 2])
        self.assertEqual(graph["load_image"]["inputs"]["image"], "sb/i.png")
        self.assertEqual(graph[w.OUTPUT_NODE]["class_type"], "SaveImage")
        # scaled in and back out
        self.assertEqual(graph["image_scale"]["inputs"]["width"], 768)
        self.assertEqual(graph["out_scale"]["inputs"]["width"], 600)

    def test_sd15_with_inpaint_nodes(self):
        graph = w.build_inpaint(_req(grow=10, feather=20), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["mask_grow"]["class_type"], "INPAINT_ExpandMask")
        self.assertEqual(graph["mask_grow"]["inputs"]["grow"], 10)
        self.assertEqual(graph["mask_grow"]["inputs"]["blur"], 20)
        self.assertEqual(graph["preblur"]["class_type"], "INPAINT_MaskedBlur")
        self.assertEqual(graph["encode"]["inputs"]["pixels"], ["preblur", 0])
        self.assertEqual(graph["encode"]["inputs"]["mask"], ["mask_stable", 0])

    def test_expand_mode_prefills_with_border_fill(self):
        graph = w.build_inpaint(_req(mode="expand"), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["prefill"]["inputs"]["fill"], "navier-stokes")
        self.assertEqual(graph["preblur"]["inputs"]["image"], ["prefill", 0])

    def test_prefill_disabled(self):
        graph = w.build_inpaint(_req(prefill=False), "i", "m", 1, w.Capabilities(True))
        self.assertNotIn("preblur", graph)
        self.assertEqual(graph["encode"]["inputs"]["pixels"], ["image_scale", 0])

    def test_no_scaling_when_sizes_match(self):
        graph = w.build_inpaint(_req(work_width=600, work_height=400), "i", "m", 1, w.Capabilities(False))
        self.assertNotIn("image_scale", graph)
        self.assertNotIn("out_scale", graph)
        self.assertEqual(graph["decode"]["inputs"]["samples"], ["sampler", 0])
        self.assertEqual(graph[w.OUTPUT_NODE]["inputs"]["images"], ["decode", 0])

    def test_sdxl_fooocus_path(self):
        model = ModelSpec("sdxl.safetensors", "sdxl", "head.pth", "v26.patch")
        graph = w.build_inpaint(_req(model=model), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["encode"]["class_type"], "INPAINT_VAEEncodeInpaintConditioning")
        self.assertEqual(graph["fooocus"]["inputs"]["latent"], ["encode", 2])
        self.assertEqual(graph["sampler"]["inputs"]["model"], ["fooocus", 0])
        self.assertEqual(graph["sampler"]["inputs"]["latent_image"], ["encode", 3])
        self.assertEqual(graph["fooocus_patch"]["inputs"]["patch"], "v26.patch")

    def test_sdxl_without_nodes_falls_back_to_core(self):
        model = ModelSpec("sdxl.safetensors", "sdxl", "head.pth", "v26.patch")
        graph = w.build_inpaint(_req(model=model), "i", "m", 1, w.Capabilities(False))
        self.assertEqual(graph["encode"]["class_type"], "InpaintModelConditioning")
        self.assertNotIn("fooocus", graph)

    def test_batch_repeats_latent(self):
        graph = w.build_inpaint(_req(sampling=Sampling(batch=3)), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["batch"]["inputs"]["amount"], 3)
        self.assertEqual(graph["sampler"]["inputs"]["latent_image"], ["batch", 0])

    def test_all_links_resolve(self):
        for caps in (w.Capabilities(True), w.Capabilities(False)):
            graph = w.build_inpaint(_req(sampling=Sampling(batch=2)), "i", "m", 1, caps)
            for node_id in graph:
                for link in _links(graph, node_id).values():
                    self.assertIn(link[0], graph, f"{node_id} links to missing {link[0]}")

    def test_total_steps(self):
        graph = w.build_inpaint(_req(sampling=Sampling(steps=33)), "i", "m", 1, w.Capabilities(False))
        self.assertEqual(w.total_steps(graph), 33)


class Txt2ImgGraphTests(unittest.TestCase):
    def test_graph(self):
        req = Txt2ImgRequest(768, 512, "p", "n", ModelSpec("x.ckpt"), Sampling(batch=2, steps=12))
        graph = w.build_txt2img(req, 9)
        self.assertEqual(graph["latent"]["inputs"], {"width": 768, "height": 512, "batch_size": 2})
        self.assertEqual(graph["sampler"]["inputs"]["denoise"], 1.0)
        self.assertEqual(graph["sampler"]["inputs"]["seed"], 9)
        self.assertEqual(w.total_steps(graph), 12)


class ErrorDescriptionTests(unittest.TestCase):
    def test_describe_node_errors(self):
        graph = {"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        errors = {"ckpt": {"errors": [{"message": "Value not in list", "details": "ckpt_name: 'x' not in []",
                                       "extra_info": {"input_name": "ckpt_name"}}]}}
        text = w.describe_node_errors(errors, graph)
        self.assertIn("CheckpointLoaderSimple", text)
        self.assertIn("ckpt_name", text)
        self.assertEqual(w.describe_node_errors({}, graph), "")


if __name__ == "__main__":
    unittest.main()

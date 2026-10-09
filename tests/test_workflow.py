# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from stable_boy import geometry as g
from stable_boy import png
from stable_boy import workflow as w
from stable_boy.backend import InpaintRequest, ModelSpec, Sampling, Txt2ImgRequest


def _req(**overrides) -> InpaintRequest:
    base = dict(
        image_png=b"",
        mask_png=b"",
        width=600,
        height=400,
        work_width=768,
        work_height=512,
        prompt="a red fox",
        negative="blurry",
        model=ModelSpec("sd15.ckpt"),
        sampling=Sampling(steps=20, batch=1, seed=5),
    )
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
        self.assertEqual(graph["mask_grow"]["inputs"]["blur"], 10)  # blur is capped at grow
        lama = ModelSpec(arch="inpaint_model", inpaint_model="big-lama.pt")
        hard = w.build_inpaint(_req(grow=10, feather=20, model=lama), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(hard["mask_grow"]["inputs"]["blur"], 0)  # removal models get a hard mask
        self.assertEqual(graph["preblur"]["class_type"], "INPAINT_MaskedBlur")
        self.assertEqual(graph["encode"]["inputs"]["pixels"], ["preblur", 0])
        self.assertEqual(graph["encode"]["inputs"]["mask"], ["mask_stable", 0])

    def test_expand_mode_prefills_with_border_fill(self):
        graph = w.build_inpaint(_req(mode="expand"), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["prefill"]["inputs"]["fill"], "navier-stokes")
        self.assertEqual(graph["preblur"]["inputs"]["image"], ["prefill", 0])

    def test_color_match_uses_untouched_pixels_as_reference(self):
        graph = w.build_inpaint(_req(), "i", "m", 1, w.Capabilities(True))
        cm = graph["color_match"]["inputs"]
        self.assertEqual(cm["target"], ["decode", 0])
        self.assertEqual(cm["reference"], ["image_scale", 0])
        self.assertEqual(cm["exclude_mask"], ["mask_stable", 0])
        self.assertEqual(graph["out_scale"]["inputs"]["image"], ["color_match", 0])
        off = w.build_inpaint(_req(color_match=0.0), "i", "m", 1, w.Capabilities(True))
        self.assertNotIn("color_match", off)
        core = w.build_inpaint(_req(), "i", "m", 1, w.Capabilities(False))
        self.assertNotIn("color_match", core)

    def test_removal_intent_prefills_from_the_border(self):
        graph = w.build_inpaint(_req(prefill_style="border"), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(graph["prefill"]["class_type"], "INPAINT_MaskedFill")
        self.assertEqual(graph["prefill"]["inputs"]["fill"], "navier-stokes")
        self.assertEqual(graph["preblur"]["inputs"]["image"], ["prefill", 0])
        default = w.build_inpaint(_req(), "i", "m", 1, w.Capabilities(True))
        self.assertNotIn("prefill", default)  # plain fill keeps the blur-only prefill

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


class TemplateSelectionTests(unittest.TestCase):
    def test_select_builder(self):
        self.assertIs(w.select_builder("sd15_inpaint"), w.build_inpaint)
        self.assertIs(w.select_builder("sdxl_fooocus"), w.build_inpaint)
        self.assertIs(w.select_builder("flux_fill"), w.build_flux_fill)
        self.assertIs(w.select_builder("qwen_edit"), w.build_qwen_edit)
        self.assertIs(w.select_builder("inpaint_model"), w.build_removal)
        with self.assertRaises(ValueError):
            w.select_builder("nope")

    def test_effective_template_from_arch(self):
        self.assertEqual(ModelSpec("x.ckpt").effective_template, "sd15_inpaint")
        self.assertEqual(ModelSpec("x", arch="flux").effective_template, "flux_fill")
        self.assertEqual(ModelSpec("x", template="qwen_edit", arch="sd15").effective_template, "qwen_edit")
        self.assertTrue(ModelSpec(arch="inpaint_model").prompt_free)

    def test_build_fill_dispatches_on_active_model(self):
        sd = w.build_fill(_req(), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(sd["ckpt"]["class_type"], "CheckpointLoaderSimple")
        flux = ModelSpec(
            arch="flux",
            unet="flux1-fill-dev-Q4_0.gguf",
            clip1="t5.gguf",
            clip2="clip_l.safetensors",
            vae="ae.safetensors",
        )
        fx = w.build_fill(_req(model=flux, sampling=Sampling(cfg=30.0, steps=20)), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(fx["unet"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(fx["clip"]["class_type"], "DualCLIPLoaderGGUF")
        self.assertEqual(fx["clip"]["inputs"]["type"], "flux")
        self.assertEqual(fx["guidance"]["inputs"]["guidance"], 30.0)
        self.assertEqual(fx["sampler"]["inputs"]["cfg"], 1.0)
        self.assertEqual(fx["encode"]["class_type"], "InpaintModelConditioning")
        self.assertEqual(fx["sampler"]["inputs"]["model"], ["diff", 0])

    def test_flux_safetensors_uses_core_loaders(self):
        flux = ModelSpec(
            arch="flux",
            unet="flux1-fill-dev.safetensors",
            clip1="t5xxl_fp8_e4m3fn.safetensors",
            clip2="clip_l.safetensors",
            vae="ae.safetensors",
        )
        fx = w.build_fill(_req(model=flux), "i", "m", 1, w.Capabilities(False))
        self.assertEqual(fx["unet"]["class_type"], "UNETLoader")
        self.assertEqual(fx["unet"]["inputs"]["weight_dtype"], "fp8_e4m3fn")
        self.assertEqual(fx["clip"]["class_type"], "DualCLIPLoader")

    def test_qwen_edit_graph(self):
        qwen = ModelSpec(
            arch="qwen_image",
            unet="qwen-image-edit-2511-Q4_K_M.gguf",
            clip1="qwen_2.5_vl_7b_fp8_scaled.safetensors",
            vae="qwen_image_vae.safetensors",
        )
        g = w.build_fill(_req(model=qwen, prompt="replace the box with a bench"), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(g["clip"]["class_type"], "CLIPLoader")
        self.assertEqual(g["clip"]["inputs"]["type"], "qwen_image")
        self.assertEqual(g["pos"]["class_type"], "TextEncodeQwenImageEditPlus")
        self.assertEqual(g["pos"]["inputs"]["image1"], ["image_scale", 0])
        self.assertEqual(g["noise_mask"]["inputs"]["mask"], ["mask_stable", 0])
        self.assertEqual(g["sampler"]["inputs"]["cfg"], 2.5)
        self.assertEqual(g["sampler"]["inputs"]["model"], ["cfgnorm", 0])

    def test_removal_graph_has_no_prompt_nodes(self):
        lama = ModelSpec(arch="inpaint_model", inpaint_model="big-lama.pt")
        g = w.build_fill(_req(model=lama), "i", "m", 7, w.Capabilities(True))
        classes = {n["class_type"] for n in g.values()}
        self.assertNotIn("CLIPTextEncode", classes)
        self.assertNotIn("KSampler", classes)
        self.assertEqual(g["inpaint_model"]["inputs"]["model_name"], "big-lama.pt")
        self.assertEqual(g["remove"]["inputs"]["seed"], 7)
        self.assertEqual(g[w.OUTPUT_NODE]["inputs"]["images"], ["out_scale", 0])
        with self.assertRaises(ValueError):
            w.build_fill(_req(model=lama), "i", "m", 7, w.Capabilities(False))

    def test_sdxl_checkpoint_swap(self):
        jug = ModelSpec(
            "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
            "sdxl",
            "fooocus_inpaint_head.pth",
            "inpaint_v26.fooocus.patch",
            template="sdxl_fooocus",
        )
        g = w.build_fill(_req(model=jug), "i", "m", 1, w.Capabilities(True))
        self.assertEqual(g["ckpt"]["inputs"]["ckpt_name"], "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors")
        self.assertEqual(g["fooocus"]["class_type"], "INPAINT_ApplyFooocusInpaint")

    def test_txt2img_rejects_non_txt2img_models(self):
        for spec in (ModelSpec(arch="flux", unet="u"), ModelSpec(arch="inpaint_model", inpaint_model="l")):
            with self.assertRaises(ValueError):
                w.build_txt2img(Txt2ImgRequest(512, 512, "p", "n", spec), 1)

    def test_all_links_resolve_in_new_templates(self):
        specs = [
            ModelSpec(arch="flux", unet="u.gguf", clip1="t.gguf", clip2="c", vae="v"),
            ModelSpec(arch="qwen_image", unet="u.gguf", clip1="c", vae="v"),
            ModelSpec(arch="inpaint_model", inpaint_model="l"),
        ]
        for spec in specs:
            graph = w.build_fill(_req(model=spec, sampling=Sampling(batch=2)), "i", "m", 1, w.Capabilities(True))
            for node_id in graph:
                for link in _links(graph, node_id).values():
                    self.assertIn(link[0], graph, f"{spec.arch}: {node_id} -> {link[0]}")


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
        errors = {
            "ckpt": {
                "errors": [
                    {
                        "message": "Value not in list",
                        "details": "ckpt_name: 'x' not in []",
                        "extra_info": {"input_name": "ckpt_name"},
                    }
                ]
            }
        }
        text = w.describe_node_errors(errors, graph)
        self.assertIn("CheckpointLoaderSimple", text)
        self.assertIn("ckpt_name", text)
        self.assertEqual(w.describe_node_errors({}, graph), "")


class ModelDisplayNameTests(unittest.TestCase):
    def test_packaging_details_are_dropped(self):
        self.assertEqual(
            w.model_display_name("FLUX.1 Fill [dev] (first-party safetensors, fp8 at load time)"), "FLUX.1 Fill [dev]"
        )
        self.assertEqual(w.model_display_name("MAT Places512 (fp16) - prompt-free object removal"), "MAT Places512")
        self.assertEqual(w.model_display_name("LaMa (big-lama) - prompt-free object removal"), "LaMa")
        self.assertEqual(
            w.model_display_name("Juggernaut XL v9 (RunDiffusion Photo v2, with Fooocus inpaint patch)"),
            "Juggernaut XL v9",
        )

    def test_plain_names_are_kept(self):
        self.assertEqual(w.model_display_name("Stable Diffusion 1.5 Inpainting"), "Stable Diffusion 1.5 Inpainting")
        self.assertEqual(w.model_display_name("  FLUX.1 Fill [dev] GGUF Q4_0  "), "FLUX.1 Fill [dev] GGUF Q4_0")

    def test_never_empty(self):
        self.assertEqual(w.model_display_name("(fp16)"), "(fp16)")
        self.assertEqual(w.model_display_name(""), "")


class ProbeSafePngTests(unittest.TestCase):
    def _strip_mask(self):
        # the outpaint mask that PyAV's format probe took for MPEG-TS
        plan = g.plan_expand(1920, 1440, 0, 0, 256, 0, g.SDXL)
        return png.encode(plan.context.width, plan.context.height, g.mask_for_expand(plan), 1)

    def test_padding_fills_probe_window_and_keeps_header(self):
        data = self._strip_mask()
        safe = w.probe_safe_png(data)
        self.assertEqual(png.read_header(safe), png.read_header(data))
        self.assertEqual(safe[37:41], b"tEXt")
        self.assertEqual(len(safe), len(data) + 12 + len(b"Comment") + 1 + w.PROBE_PADDING)
        # nothing but the signature and IHDR is recognisable in the first 2048 bytes
        self.assertNotIn(0x47, safe[41 + 8 : 2048])
        self.assertTrue(safe.endswith(data[33:]))

    def test_idempotent_and_ignores_non_png(self):
        safe = w.probe_safe_png(self._strip_mask())
        self.assertEqual(w.probe_safe_png(safe), safe)
        self.assertEqual(w.probe_safe_png(b"not a png"), b"not a png")


if __name__ == "__main__":
    unittest.main()

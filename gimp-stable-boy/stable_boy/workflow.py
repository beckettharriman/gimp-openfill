# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""ComfyUI workflow builders (API "prompt" format).

The graphs are assembled in code so the user never sees ComfyUI. Node ids
are short stable strings; ``/prompt`` errors reference them and are mapped
back to readable messages by the backend.

Graph shapes are documented in ``docs/design.md``. The builders only need
core ComfyUI nodes; when the optional ``comfyui-inpaint-nodes`` package is
present (``Capabilities.inpaint_nodes``) they use its better mask and
pre-fill nodes and can apply the Fooocus SDXL inpaint patch.
"""

from __future__ import annotations

from dataclasses import dataclass

from .backend import InpaintRequest, Txt2ImgRequest

OUTPUT_NODE = "save"


@dataclass(frozen=True)
class Capabilities:
    inpaint_nodes: bool = False


class Graph:
    """Tiny helper that numbers nodes and produces the API-format dict."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}

    def add(self, node_id: str, class_type: str, **inputs) -> str:
        if node_id in self.nodes:
            raise ValueError(f"duplicate node id {node_id}")
        self.nodes[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id

    @staticmethod
    def out(node_id: str, index: int = 0) -> list:
        return [node_id, index]

    def to_dict(self) -> dict:
        return dict(self.nodes)


def _checkpoint(g: Graph, name: str) -> tuple[list, list, list]:
    g.add("ckpt", "CheckpointLoaderSimple", ckpt_name=name)
    return g.out("ckpt", 0), g.out("ckpt", 1), g.out("ckpt", 2)


def _prompts(g: Graph, clip: list, prompt: str, negative: str) -> tuple[list, list]:
    g.add("pos", "CLIPTextEncode", text=prompt, clip=clip)
    g.add("neg", "CLIPTextEncode", text=negative, clip=clip)
    return g.out("pos"), g.out("neg")


def _scale_image(g: Graph, node_id: str, image: list, width: int, height: int) -> list:
    g.add(node_id, "ImageScale", image=image, upscale_method="lanczos",
          width=width, height=height, crop="disabled")
    return g.out(node_id)


def _prepare_mask(g: Graph, mask_image: list, req: InpaintRequest, caps: Capabilities) -> list:
    """Mask image (gray PNG loaded as IMAGE) -> grown, feathered MASK."""
    if req.needs_scaling:
        mask_image = _scale_image(g, "mask_scale", mask_image, req.work_width, req.work_height)
    g.add("mask", "ImageToMask", image=mask_image, channel="red")
    mask = g.out("mask")
    grow = max(0, int(req.grow))
    blur = max(0, int(req.feather))
    if caps.inpaint_nodes:
        if grow or blur:
            g.add("mask_grow", "INPAINT_ExpandMask", mask=mask, grow=grow, blur=blur,
                  blur_type="gaussian")
            mask = g.out("mask_grow")
        g.add("mask_stable", "INPAINT_StabilizeMask", mask=mask, epsilon=0.01)
        return g.out("mask_stable")
    if grow:
        g.add("mask_grow", "GrowMask", mask=mask, expand=grow, tapered_corners=True)
        mask = g.out("mask_grow")
    if blur:
        g.add("mask_img", "MaskToImage", mask=mask)
        radius = max(1, min(31, blur // 2))
        g.add("mask_blur", "ImageBlur", image=g.out("mask_img"), blur_radius=radius,
              sigma=max(1.0, blur / 3.0))
        g.add("mask_soft", "ImageToMask", image=g.out("mask_blur"), channel="red")
        mask = g.out("mask_soft")
    return mask


def _prefill(g: Graph, image: list, mask: list, req: InpaintRequest, caps: Capabilities) -> list:
    """Hide the old content under the mask so the sampler starts from a neutral
    image instead of the object being removed (fill) or hard transparent
    pixels (expand)."""
    if not (req.prefill and caps.inpaint_nodes):
        return image
    if req.mode == "expand":
        mode = req.prefill_mode if req.prefill_mode in ("navier-stokes", "telea", "neutral") else "navier-stokes"
        g.add("prefill", "INPAINT_MaskedFill", image=image, mask=mask, fill=mode, falloff=0)
        g.add("preblur", "INPAINT_MaskedBlur", image=g.out("prefill"), mask=mask, blur=65,
              falloff=0)
        return g.out("preblur")
    g.add("preblur", "INPAINT_MaskedBlur", image=image, mask=mask, blur=65, falloff=9)
    return g.out("preblur")


def build_inpaint(req: InpaintRequest, image_ref: str, mask_ref: str, seed: int,
                  caps: Capabilities, filename_prefix: str = "stable-boy/fill") -> dict:
    """Build the inpaint / outpaint graph.

    ``image_ref`` and ``mask_ref`` are the names returned by ``/upload/image``
    (``subfolder/filename``). Returns the API-format prompt dict.
    """
    g = Graph()
    model, clip, vae = _checkpoint(g, req.model.checkpoint)
    positive, negative = _prompts(g, clip, req.prompt, req.negative)

    g.add("load_image", "LoadImage", image=image_ref)
    g.add("load_mask", "LoadImage", image=mask_ref)
    image = g.out("load_image", 0)
    if req.needs_scaling:
        image = _scale_image(g, "image_scale", image, req.work_width, req.work_height)
    mask = _prepare_mask(g, g.out("load_mask", 0), req, caps)
    image = _prefill(g, image, mask, req, caps)

    g.add("diff", "DifferentialDiffusion", model=model)
    model = g.out("diff")

    use_fooocus = req.model.uses_fooocus and caps.inpaint_nodes
    if use_fooocus:
        g.add("encode", "INPAINT_VAEEncodeInpaintConditioning", positive=positive,
              negative=negative, vae=vae, pixels=image, mask=mask)
        g.add("fooocus_patch", "INPAINT_LoadFooocusInpaint", head=req.model.fooocus_head,
              patch=req.model.fooocus_patch)
        g.add("fooocus", "INPAINT_ApplyFooocusInpaint", model=model,
              patch=g.out("fooocus_patch"), latent=g.out("encode", 2))
        model = g.out("fooocus")
        latent = g.out("encode", 3)
    else:
        g.add("encode", "InpaintModelConditioning", positive=positive, negative=negative,
              vae=vae, pixels=image, mask=mask, noise_mask=True)
        latent = g.out("encode", 2)
    positive, negative = g.out("encode", 0), g.out("encode", 1)

    batch = max(1, int(req.sampling.batch))
    if batch > 1:
        g.add("batch", "RepeatLatentBatch", samples=latent, amount=batch)
        latent = g.out("batch")

    g.add("sampler", "KSampler", model=model, positive=positive, negative=negative,
          latent_image=latent, seed=int(seed), steps=int(req.sampling.steps),
          cfg=float(req.sampling.cfg), sampler_name=req.sampling.sampler,
          scheduler=req.sampling.scheduler, denoise=float(req.sampling.denoise))
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    out = g.out("decode")
    if caps.inpaint_nodes and req.color_match > 0:
        # Correct the global brightness/color drift of the decoded image using
        # the untouched pixels outside the mask as the reference.
        reference = g.out("image_scale") if req.needs_scaling else g.out("load_image", 0)
        g.add("color_match", "INPAINT_ColorMatch", target=out, reference=reference,
              exclude_mask=mask, strength=float(req.color_match))
        out = g.out("color_match")
    if req.needs_scaling:
        out = _scale_image(g, "out_scale", out, req.width, req.height)
    g.add(OUTPUT_NODE, "SaveImage", images=out, filename_prefix=filename_prefix)
    return g.to_dict()


def build_txt2img(req: Txt2ImgRequest, seed: int, filename_prefix: str = "stable-boy/txt2img") -> dict:
    g = Graph()
    model, clip, vae = _checkpoint(g, req.model.checkpoint)
    positive, negative = _prompts(g, clip, req.prompt, req.negative)
    g.add("latent", "EmptyLatentImage", width=int(req.width), height=int(req.height),
          batch_size=max(1, int(req.sampling.batch)))
    g.add("sampler", "KSampler", model=model, positive=positive, negative=negative,
          latent_image=g.out("latent"), seed=int(seed), steps=int(req.sampling.steps),
          cfg=float(req.sampling.cfg), sampler_name=req.sampling.sampler,
          scheduler=req.sampling.scheduler, denoise=1.0)
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    g.add(OUTPUT_NODE, "SaveImage", images=g.out("decode"), filename_prefix=filename_prefix)
    return g.to_dict()


def total_steps(graph: dict) -> int:
    """Sum of sampler steps in a graph (for progress estimation)."""
    return sum(int(n["inputs"].get("steps", 0)) for n in graph.values()
               if n["class_type"] in ("KSampler", "KSamplerAdvanced"))


def describe_node_errors(node_errors: dict, graph: dict) -> str:
    """Turn ComfyUI ``node_errors`` into one readable line per problem."""
    lines = []
    for node_id, info in (node_errors or {}).items():
        class_type = graph.get(node_id, {}).get("class_type", node_id)
        for err in info.get("errors", []):
            msg = err.get("message", "")
            details = err.get("details", "")
            extra = err.get("extra_info", {}) or {}
            name = extra.get("input_name")
            text = f"{class_type}: {msg}"
            if name:
                text += f" ({name})"
            if details:
                text += f" - {details}"
            lines.append(text)
    return "\n".join(lines)

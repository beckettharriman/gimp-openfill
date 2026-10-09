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

import zlib
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
    g.add(node_id, "ImageScale", image=image, upscale_method="lanczos", width=width, height=height, crop="disabled")
    return g.out(node_id)


def _prepare_mask(g: Graph, mask_image: list, req: InpaintRequest, caps: Capabilities) -> list:
    """Mask image (gray PNG loaded as IMAGE) -> grown, feathered MASK."""
    if req.needs_scaling:
        mask_image = _scale_image(g, "mask_scale", mask_image, req.work_width, req.work_height)
    g.add("mask", "ImageToMask", image=mask_image, channel="red")
    mask = g.out("mask")
    grow = max(0, int(req.grow))
    # The blur must not exceed the growth, otherwise a small selection never
    # reaches mask value 1.0 and the model only partially repaints it. The
    # LaMa/MAT node wants a hard mask: no blur at all.
    hard = req.model.effective_template == "inpaint_model"
    blur = 0 if hard else max(0, min(int(req.feather), grow))
    if caps.inpaint_nodes:
        if grow or blur:
            g.add("mask_grow", "INPAINT_ExpandMask", mask=mask, grow=grow, blur=blur, blur_type="gaussian")
            mask = g.out("mask_grow")
        g.add("mask_stable", "INPAINT_StabilizeMask", mask=mask, epsilon=0.01)
        return g.out("mask_stable")
    if grow:
        g.add("mask_grow", "GrowMask", mask=mask, expand=grow, tapered_corners=True)
        mask = g.out("mask_grow")
    if blur:
        g.add("mask_img", "MaskToImage", mask=mask)
        radius = max(1, min(31, blur // 2))
        g.add("mask_blur", "ImageBlur", image=g.out("mask_img"), blur_radius=radius, sigma=max(1.0, blur / 3.0))
        g.add("mask_soft", "ImageToMask", image=g.out("mask_blur"), channel="red")
        mask = g.out("mask_soft")
    return mask


def _prefill(g: Graph, image: list, mask: list, req: InpaintRequest, caps: Capabilities) -> list:
    """Hide the old content under the mask so the sampler starts from a neutral
    image instead of the object being removed (fill) or hard transparent
    pixels (expand)."""
    if not (req.prefill and caps.inpaint_nodes):
        return image
    if req.mode == "expand" or req.prefill_style == "border":
        # Fill the hole from its border so nothing of the removed object (its
        # colour, its blurred shape) survives into the sampler's starting image.
        mode = req.prefill_mode if req.prefill_mode in ("navier-stokes", "telea", "neutral") else "navier-stokes"
        g.add("prefill", "INPAINT_MaskedFill", image=image, mask=mask, fill=mode, falloff=0)
        g.add("preblur", "INPAINT_MaskedBlur", image=g.out("prefill"), mask=mask, blur=65, falloff=0)
        return g.out("preblur")
    g.add("preblur", "INPAINT_MaskedBlur", image=image, mask=mask, blur=65, falloff=9)
    return g.out("preblur")


def build_inpaint(
    req: InpaintRequest,
    image_ref: str,
    mask_ref: str,
    seed: int,
    caps: Capabilities,
    filename_prefix: str = "stable-boy/fill",
) -> dict:
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
        g.add(
            "encode",
            "INPAINT_VAEEncodeInpaintConditioning",
            positive=positive,
            negative=negative,
            vae=vae,
            pixels=image,
            mask=mask,
        )
        g.add("fooocus_patch", "INPAINT_LoadFooocusInpaint", head=req.model.fooocus_head, patch=req.model.fooocus_patch)
        g.add(
            "fooocus",
            "INPAINT_ApplyFooocusInpaint",
            model=model,
            patch=g.out("fooocus_patch"),
            latent=g.out("encode", 2),
        )
        model = g.out("fooocus")
        latent = g.out("encode", 3)
    else:
        g.add(
            "encode",
            "InpaintModelConditioning",
            positive=positive,
            negative=negative,
            vae=vae,
            pixels=image,
            mask=mask,
            noise_mask=True,
        )
        latent = g.out("encode", 2)
    positive, negative = g.out("encode", 0), g.out("encode", 1)

    batch = max(1, int(req.sampling.batch))
    if batch > 1:
        g.add("batch", "RepeatLatentBatch", samples=latent, amount=batch)
        latent = g.out("batch")

    g.add(
        "sampler",
        "KSampler",
        model=model,
        positive=positive,
        negative=negative,
        latent_image=latent,
        seed=int(seed),
        steps=int(req.sampling.steps),
        cfg=float(req.sampling.cfg),
        sampler_name=req.sampling.sampler,
        scheduler=req.sampling.scheduler,
        denoise=float(req.sampling.denoise),
    )
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    out = g.out("decode")
    if caps.inpaint_nodes and req.color_match > 0:
        # Correct the global brightness/color drift of the decoded image using
        # the untouched pixels outside the mask as the reference.
        reference = g.out("image_scale") if req.needs_scaling else g.out("load_image", 0)
        g.add(
            "color_match",
            "INPAINT_ColorMatch",
            target=out,
            reference=reference,
            exclude_mask=mask,
            strength=float(req.color_match),
        )
        out = g.out("color_match")
    if req.needs_scaling:
        out = _scale_image(g, "out_scale", out, req.width, req.height)
    g.add(OUTPUT_NODE, "SaveImage", images=out, filename_prefix=filename_prefix)
    return g.to_dict()


# Generative Expand prompts. With an empty prompt the positive stays empty and
# the negative steers away from what the model otherwise invents around a
# finished-looking picture: a frame, a border, a vignette or new subjects.
# The old default (a "seamless continuation of the surrounding background"
# positive and no frame terms) made the SDXL tier paint a matted picture frame
# around the old image (docs/evidence/daytime-2026-10-09/expand/README.md).
EXPAND_NEGATIVE = "new objects, people, text, frame, border, vignette, watermark, blurry"
# Appended to a user's own negative: only the frame terms, so a prompt that asks
# for people or text is not contradicted.
EXPAND_FRAME_NEGATIVE = "frame, border, vignette, picture in picture, watermark"


def expand_prompts(prompt: str, negative: str) -> tuple[str, str]:
    """Positive and negative prompt of a Generative Expand.

    Empty prompt ("continue the scene"): empty positive, ``EXPAND_NEGATIVE``
    plus the user's negative. A user prompt is kept and ``EXPAND_FRAME_NEGATIVE``
    is appended to the user's negative.
    """
    prompt, negative = (prompt or "").strip(), (negative or "").strip()
    extra = EXPAND_FRAME_NEGATIVE if prompt else EXPAND_NEGATIVE
    return prompt, f"{negative}, {extra}" if negative else extra


# Guidance of a Generative Expand on the SDXL tier (Fooocus inpaint patch). With
# the empty "continue the scene" positive the guidance only pushes away from the
# negative; at the general default 7 the new border came back over-saturated
# with hard bands (a bright turf strip, grey backdrop bands on a white product
# shot), at 4 (the Fooocus default) it blends. SD 1.5 keeps the setting.
EXPAND_SDXL_CFG = 4.0


def expand_cfg(arch: str, cfg: float) -> float:
    """Sampler guidance for an expand: at most ``EXPAND_SDXL_CFG`` on the SDXL tier."""
    return min(float(cfg), EXPAND_SDXL_CFG) if arch == "sdxl" else float(cfg)


def _is_gguf(name: str) -> bool:
    return name.lower().endswith(".gguf")


def _flux_loaders(g: Graph, spec) -> tuple[list, list, list]:
    """UNet / dual CLIP / VAE loaders for FLUX, GGUF or safetensors as needed."""
    if _is_gguf(spec.unet):
        g.add("unet", "UnetLoaderGGUF", unet_name=spec.unet)
    else:
        g.add("unet", "UNETLoader", unet_name=spec.unet, weight_dtype="fp8_e4m3fn")
    if _is_gguf(spec.clip1) or _is_gguf(spec.clip2):
        g.add("clip", "DualCLIPLoaderGGUF", clip_name1=spec.clip1, clip_name2=spec.clip2, type="flux")
    else:
        g.add("clip", "DualCLIPLoader", clip_name1=spec.clip1, clip_name2=spec.clip2, type="flux")
    g.add("vae", "VAELoader", vae_name=spec.vae)
    return g.out("unet"), g.out("clip"), g.out("vae")


def _load_inputs(g: Graph, req: InpaintRequest, image_ref: str, mask_ref: str, caps: Capabilities) -> tuple[list, list]:
    g.add("load_image", "LoadImage", image=image_ref)
    g.add("load_mask", "LoadImage", image=mask_ref)
    image = g.out("load_image", 0)
    if req.needs_scaling:
        image = _scale_image(g, "image_scale", image, req.work_width, req.work_height)
    mask = _prepare_mask(g, g.out("load_mask", 0), req, caps)
    return image, mask


def _finish(g: Graph, req: InpaintRequest, out: list, mask: list, caps: Capabilities, filename_prefix: str) -> dict:
    if caps.inpaint_nodes and req.color_match > 0:
        reference = g.out("image_scale") if req.needs_scaling else g.out("load_image", 0)
        g.add(
            "color_match",
            "INPAINT_ColorMatch",
            target=out,
            reference=reference,
            exclude_mask=mask,
            strength=float(req.color_match),
        )
        out = g.out("color_match")
    if req.needs_scaling:
        out = _scale_image(g, "out_scale", out, req.width, req.height)
    g.add(OUTPUT_NODE, "SaveImage", images=out, filename_prefix=filename_prefix)
    return g.to_dict()


def build_flux_fill(
    req: InpaintRequest,
    image_ref: str,
    mask_ref: str,
    seed: int,
    caps: Capabilities,
    filename_prefix: str = "stable-boy/flux",
) -> dict:
    """FLUX.1 Fill: UNet (GGUF or fp8) + T5/CLIP-L + FLUX VAE, InpaintModelConditioning,
    FluxGuidance, cfg 1.0."""
    g = Graph()
    model, clip, vae = _flux_loaders(g, req.model)
    positive, negative = _prompts(g, clip, req.prompt, req.negative)
    g.add("guidance", "FluxGuidance", conditioning=positive, guidance=float(req.sampling.cfg or 30.0))
    positive = g.out("guidance")
    image, mask = _load_inputs(g, req, image_ref, mask_ref, caps)
    image = _prefill(g, image, mask, req, caps)
    g.add("diff", "DifferentialDiffusion", model=model)
    g.add(
        "encode",
        "InpaintModelConditioning",
        positive=positive,
        negative=negative,
        vae=vae,
        pixels=image,
        mask=mask,
        noise_mask=True,
    )
    latent = g.out("encode", 2)
    batch = max(1, int(req.sampling.batch))
    if batch > 1:
        g.add("batch", "RepeatLatentBatch", samples=latent, amount=batch)
        latent = g.out("batch")
    g.add(
        "sampler",
        "KSampler",
        model=g.out("diff"),
        positive=g.out("encode", 0),
        negative=g.out("encode", 1),
        latent_image=latent,
        seed=int(seed),
        steps=int(req.sampling.steps),
        cfg=1.0,
        sampler_name="euler",
        scheduler="normal",
        denoise=float(req.sampling.denoise),
    )
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    return _finish(g, req, g.out("decode"), mask, caps, filename_prefix)


def build_qwen_edit(
    req: InpaintRequest,
    image_ref: str,
    mask_ref: str,
    seed: int,
    caps: Capabilities,
    filename_prefix: str = "stable-boy/qwen",
) -> dict:
    """Qwen-Image-Edit (2509/2511 class): instruction-driven edit of the context
    region, limited to the mask with a latent noise mask."""
    g = Graph()
    spec = req.model
    if _is_gguf(spec.unet):
        g.add("unet", "UnetLoaderGGUF", unet_name=spec.unet)
    else:
        g.add("unet", "UNETLoader", unet_name=spec.unet, weight_dtype="default")
    if _is_gguf(spec.clip1):
        g.add("clip", "CLIPLoaderGGUF", clip_name=spec.clip1, type="qwen_image")
    else:
        g.add("clip", "CLIPLoader", clip_name=spec.clip1, type="qwen_image")
    g.add("vae", "VAELoader", vae_name=spec.vae)
    model, clip, vae = g.out("unet"), g.out("clip"), g.out("vae")
    g.add("shift", "ModelSamplingAuraFlow", model=model, shift=3.0)
    g.add("cfgnorm", "CFGNorm", model=g.out("shift"), strength=1.0)
    model = g.out("cfgnorm")
    image, mask = _load_inputs(g, req, image_ref, mask_ref, caps)
    g.add("pos", "TextEncodeQwenImageEditPlus", clip=clip, prompt=req.prompt, vae=vae, image1=image)
    g.add("neg", "TextEncodeQwenImageEditPlus", clip=clip, prompt=req.negative or "", vae=vae, image1=image)
    g.add("encode", "VAEEncode", pixels=image, vae=vae)
    g.add("noise_mask", "SetLatentNoiseMask", samples=g.out("encode"), mask=mask)
    latent = g.out("noise_mask")
    batch = max(1, int(req.sampling.batch))
    if batch > 1:
        g.add("batch", "RepeatLatentBatch", samples=latent, amount=batch)
        latent = g.out("batch")
    g.add(
        "sampler",
        "KSampler",
        model=model,
        positive=g.out("pos"),
        negative=g.out("neg"),
        latent_image=latent,
        seed=int(seed),
        steps=int(req.sampling.steps),
        cfg=float(req.sampling.cfg if 1.0 < req.sampling.cfg <= 5.0 else 2.5),
        sampler_name="euler",
        scheduler="simple",
        denoise=float(req.sampling.denoise),
    )
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    return _finish(g, req, g.out("decode"), mask, caps, filename_prefix)


def build_removal(
    req: InpaintRequest,
    image_ref: str,
    mask_ref: str,
    seed: int,
    caps: Capabilities,
    filename_prefix: str = "stable-boy/remove",
) -> dict:
    """Prompt-free removal with LaMa / MAT through comfyui-inpaint-nodes."""
    if not caps.inpaint_nodes:
        raise ValueError("prompt-free removal needs comfyui-inpaint-nodes on the server")
    g = Graph()
    image, mask = _load_inputs(g, req, image_ref, mask_ref, caps)
    g.add("inpaint_model", "INPAINT_LoadInpaintModel", model_name=req.model.inpaint_model)
    g.add(
        "remove",
        "INPAINT_InpaintWithModel",
        inpaint_model=g.out("inpaint_model"),
        image=image,
        mask=mask,
        seed=int(seed),
    )
    out = g.out("remove")
    if req.needs_scaling:
        out = _scale_image(g, "out_scale", out, req.width, req.height)
    g.add(OUTPUT_NODE, "SaveImage", images=out, filename_prefix=filename_prefix)
    return g.to_dict()


BUILDERS = {
    "sd15_inpaint": build_inpaint,
    "sdxl_fooocus": build_inpaint,
    "flux_fill": build_flux_fill,
    "qwen_edit": build_qwen_edit,
    "inpaint_model": build_removal,
}


def select_builder(template: str):
    """Return the graph builder for a catalog template id."""
    try:
        return BUILDERS[template]
    except KeyError:
        raise ValueError(f"unknown workflow template '{template}'") from None


def build_fill(
    req: InpaintRequest,
    image_ref: str,
    mask_ref: str,
    seed: int,
    caps: Capabilities,
    filename_prefix: str = "stable-boy/fill",
) -> dict:
    """Dispatch on the active model's template."""
    return select_builder(req.model.effective_template)(req, image_ref, mask_ref, seed, caps, filename_prefix)


def build_txt2img(req: Txt2ImgRequest, seed: int, filename_prefix: str = "stable-boy/txt2img") -> dict:
    g = Graph()
    if req.model.effective_template == "flux_fill":
        raise ValueError("FLUX.1 Fill is an inpainting model; use it for Generative Fill or Expand")
    if req.model.effective_template in ("qwen_edit", "inpaint_model"):
        raise ValueError("the active model does not support text to image")
    model, clip, vae = _checkpoint(g, req.model.checkpoint)
    positive, negative = _prompts(g, clip, req.prompt, req.negative)
    g.add(
        "latent",
        "EmptyLatentImage",
        width=int(req.width),
        height=int(req.height),
        batch_size=max(1, int(req.sampling.batch)),
    )
    g.add(
        "sampler",
        "KSampler",
        model=model,
        positive=positive,
        negative=negative,
        latent_image=g.out("latent"),
        seed=int(seed),
        steps=int(req.sampling.steps),
        cfg=float(req.sampling.cfg),
        sampler_name=req.sampling.sampler,
        scheduler=req.sampling.scheduler,
        denoise=1.0,
    )
    g.add("decode", "VAEDecode", samples=g.out("sampler"), vae=vae)
    g.add(OUTPUT_NODE, "SaveImage", images=g.out("decode"), filename_prefix=filename_prefix)
    return g.to_dict()


def total_steps(graph: dict) -> int:
    """Sum of sampler steps in a graph (for progress estimation)."""
    return sum(
        int(n["inputs"].get("steps", 0)) for n in graph.values() if n["class_type"] in ("KSampler", "KSamplerAdvanced")
    )


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# ComfyUI's LoadImage decodes uploads with PyAV (FFmpeg), which guesses the file
# format from the first 2048 bytes. A mask with identical rows (an outpaint
# strip) deflates into a periodic byte stream that the MPEG-TS probe scores
# higher than PNG, and the load fails with "End of file". A text chunk of
# spaces right after IHDR fills the probe window, so only the PNG signature
# is recognisable there.
PROBE_PADDING = 2048


def probe_safe_png(data: bytes) -> bytes:
    """Return ``data`` with a tEXt chunk of ``PROBE_PADDING`` spaces inserted after IHDR.

    Decoders ignore the chunk; the pixels are unchanged. Input that is not a PNG
    starting with IHDR, or already padded, is returned as is.
    """
    if not data.startswith(_PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return data
    end_ihdr = 8 + 12 + int.from_bytes(data[8:12], "big")
    if data[end_ihdr + 4 : end_ihdr + 8] == b"tEXt":
        return data
    body = b"Comment\x00" + b" " * PROBE_PADDING
    chunk = len(body).to_bytes(4, "big") + b"tEXt" + body + (zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF).to_bytes(4, "big")
    return data[:end_ihdr] + chunk + data[end_ihdr:]


def model_display_name(name: str) -> str:
    """The user-facing part of a catalog model name.

    Catalog names carry packaging details for the Models tab, e.g. "FLUX.1 Fill
    [dev] (first-party safetensors, fp8 at load time)" or "MAT Places512 (fp16)
    - prompt-free object removal". Messages about a missing or running model
    only need the model itself: everything from the first " (" or " - " on is
    dropped. A name that would become empty is returned unchanged.
    """
    text = (name or "").strip()
    for marker in (" (", " - "):
        index = text.find(marker)
        if index > 0:
            text = text[:index]
    return text.strip() or (name or "").strip()


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

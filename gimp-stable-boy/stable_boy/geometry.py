# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure geometry helpers: context regions, working sizes, outpaint canvases.

No GIMP imports. Every function here is unit-tested under system Python.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def intersect(self, other: Rect) -> Rect:
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.right, other.right), min(self.bottom, other.bottom)
        return Rect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def contains(self, other: Rect) -> bool:
        return self.x <= other.x and self.y <= other.y and self.right >= other.right and self.bottom >= other.bottom

    def translate(self, dx: int, dy: int) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def relative_to(self, origin: Rect) -> Rect:
        """This rectangle expressed in the coordinate system of ``origin``."""
        return Rect(self.x - origin.x, self.y - origin.y, self.width, self.height)


@dataclass(frozen=True)
class ModelProfile:
    """Resolution limits of a model family."""

    name: str
    min_side: int  # the model gets unhappy below this (SD 1.5: 512)
    max_side: int  # longest side we send to the model
    min_context: int  # minimum context region size cropped from the image
    multiple: int = 8  # latent alignment


# min_context is deliberately small: a tiny selection gets a tight crop that is
# then UPSCALED to min_side so the object fills a useful part of the frame
# (A1111 "inpaint at full resolution" behaviour), instead of a 768 px crop in
# which a 40 px object is 5 % of the image and gets painted as a blur.
SD15 = ModelProfile("sd15", min_side=512, max_side=768, min_context=192)
SDXL = ModelProfile("sdxl", min_side=768, max_side=1024, min_context=256)
FLUX = ModelProfile("flux", min_side=768, max_side=1024, min_context=256, multiple=16)
QWEN = ModelProfile("qwen_image", min_side=768, max_side=1024, min_context=256, multiple=16)
# LaMa/MAT work best on native-resolution pixels: a 512 px context at 1:1,
# no upscaling (texture scale would not match the surroundings otherwise).
# The removal node runs MAT on a fixed 512 px square (it pads the crop to a
# square and resizes it with nearest-neighbour sampling), so anything larger
# than 512 px is thrown away there with aliasing; the graph downscales with
# lanczos to 512 instead and the node then works 1:1.
INPAINT_MODEL = ModelProfile("inpaint_model", min_side=256, max_side=512, min_context=512)
PROFILES = {"sd15": SD15, "sdxl": SDXL, "flux": FLUX, "qwen_image": QWEN, "inpaint_model": INPAINT_MODEL}


def round_to_multiple(value: int, multiple: int) -> int:
    """Round ``value`` to the nearest multiple, never below ``multiple``."""
    return max(multiple, round(value / multiple) * multiple)


def clamp_rect(rect: Rect, bounds: Rect) -> Rect:
    """Move ``rect`` inside ``bounds`` if possible, shrink it if it is larger."""
    width = min(rect.width, bounds.width)
    height = min(rect.height, bounds.height)
    x = min(max(rect.x, bounds.x), bounds.right - width)
    y = min(max(rect.y, bounds.y), bounds.bottom - height)
    return Rect(x, y, width, height)


def context_rect(
    selection: Rect, image: Rect, profile: ModelProfile, padding_ratio: float = 1.0, min_padding: int = 32
) -> Rect:
    """Grow the selection into the region the model will see.

    The margin on each side is ``padding_ratio`` times the selection's larger
    side (so the context is about three times the selection), at least
    ``min_padding`` pixels and at least ``profile.min_context`` in total when
    the image allows it; centered on the selection and always inside the
    image. Small selections therefore get a tight crop that ``working_size``
    upscales; large ones get a context that is downscaled.
    """
    if selection.is_empty():
        raise ValueError("selection is empty")
    pad = max(min_padding, round(max(selection.width, selection.height) * padding_ratio))
    width = max(selection.width + 2 * pad, profile.min_context)
    height = max(selection.height + 2 * pad, profile.min_context)
    cx = selection.x + selection.width / 2
    cy = selection.y + selection.height / 2
    grown = Rect(round(cx - width / 2), round(cy - height / 2), width, height)
    return clamp_rect(grown, image)


@dataclass(frozen=True)
class WorkingSize:
    width: int
    height: int
    scale: float  # working / source


def working_size(source_w: int, source_h: int, profile: ModelProfile, max_upscale: float = 8.0) -> WorkingSize:
    """Resolution to generate at for a context region of ``source_w x source_h``.

    Downscale so the longer side fits ``profile.max_side``; upscale (at most
    ``max_upscale``) so the shorter side reaches ``profile.min_side``; snap
    both sides to the model's latent multiple.
    """
    if source_w <= 0 or source_h <= 0:
        raise ValueError("source size must be positive")
    longer = max(source_w, source_h)
    shorter = min(source_w, source_h)
    scale = 1.0
    if longer > profile.max_side:
        scale = profile.max_side / longer
    elif shorter < profile.min_side:
        scale = min(max_upscale, profile.min_side / shorter)
        if longer * scale > profile.max_side:
            scale = profile.max_side / longer
    width = round_to_multiple(round(source_w * scale), profile.multiple)
    height = round_to_multiple(round(source_h * scale), profile.multiple)
    if width == source_w and height == source_h:
        return WorkingSize(width, height, 1.0)
    return WorkingSize(width, height, width / source_w)


@dataclass(frozen=True)
class ExpandPlan:
    """Result of planning a canvas expansion (outpaint)."""

    image_width: int  # original image size
    image_height: int
    new_width: int
    new_height: int
    offset_x: int  # where the old image lands inside the new canvas
    offset_y: int
    overlap: int  # band of old pixels that is regenerated for blending
    fill_rect: Rect  # bounding box of the generated area, new-canvas coords
    context: Rect  # region sent to the model, new-canvas coords

    @property
    def grows(self) -> tuple[bool, bool, bool, bool]:
        """(left, top, right, bottom)"""
        return (
            self.offset_x > 0,
            self.offset_y > 0,
            self.new_width - self.offset_x - self.image_width > 0,
            self.new_height - self.offset_y - self.image_height > 0,
        )

    @property
    def keep_rect(self) -> Rect:
        """Old pixels that are left untouched (old image minus overlap bands)."""
        left, top, right, bottom = self.grows
        x1 = self.offset_x + (self.overlap if left else 0)
        y1 = self.offset_y + (self.overlap if top else 0)
        x2 = self.offset_x + self.image_width - (self.overlap if right else 0)
        y2 = self.offset_y + self.image_height - (self.overlap if bottom else 0)
        return Rect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def plan_expand(
    image_w: int, image_h: int, left: int, top: int, right: int, bottom: int, profile: ModelProfile, overlap: int = 32
) -> ExpandPlan:
    """Plan an outpaint that grows the canvas by the given margins.

    The generated area is everything outside the old image plus an
    ``overlap`` band inside it on each growing side. The context is that
    area's bounding box grown by the usual padding, clamped to the new canvas.
    """
    if min(left, top, right, bottom) < 0:
        raise ValueError("margins must be non-negative")
    if left == top == right == bottom == 0:
        raise ValueError("at least one margin must be positive")
    new_w = image_w + left + right
    new_h = image_h + top + bottom
    canvas = Rect(0, 0, new_w, new_h)
    overlap = max(0, min(overlap, image_w // 2, image_h // 2))
    plan = ExpandPlan(image_w, image_h, new_w, new_h, left, top, overlap, canvas, canvas)
    keep = plan.keep_rect
    sides = sum(1 for m in (left, top, right, bottom) if m > 0)
    if sides >= 2:
        fill = canvas
    elif left:
        fill = Rect(0, 0, keep.x, new_h)
    elif right:
        fill = Rect(keep.right, 0, new_w - keep.right, new_h)
    elif top:
        fill = Rect(0, 0, new_w, keep.y)
    else:
        fill = Rect(0, keep.bottom, new_w, new_h - keep.bottom)
    if sides == 1:
        context = _strip_context(fill, canvas, profile, left, top, right, bottom)
    else:
        context = context_rect(fill, canvas, profile)
    return ExpandPlan(image_w, image_h, new_w, new_h, left, top, overlap, fill, context)


# Old pixels shown next to a one-sided outpaint strip, as a multiple of the
# strip's depth. The generic context (padding by the larger side) turned a
# 256 px strip along a 1440 px edge into the whole canvas, sampled at 0.47x:
# the new area became a thin, flat band in the working image.
EXPAND_CONTEXT_FACTOR = 2.0
# ...but never narrower than half the edge length: a 864x3000 strip was
# sampled at 296x1024, far below what SDXL can compose, and came back as a
# flat dark panel.
EXPAND_MIN_ASPECT = 0.5


def _strip_context(
    fill: Rect, canvas: Rect, profile: ModelProfile, left: int, top: int, right: int, bottom: int
) -> Rect:
    """Context for a single-side expansion: the strip plus a band of the old
    image as deep as ``EXPAND_CONTEXT_FACTOR`` times the strip (at least the
    model's minimum context, and at least ``EXPAND_MIN_ASPECT`` of the edge
    length), over the full length of the edge."""
    if left or right:
        depth = fill.width
        width = depth + max(profile.min_context, round(depth * EXPAND_CONTEXT_FACTOR))
        width = min(canvas.width, max(width, round(canvas.height * EXPAND_MIN_ASPECT)))
        x = 0 if left else canvas.width - width
        return Rect(x, 0, width, canvas.height)
    depth = fill.height
    height = depth + max(profile.min_context, round(depth * EXPAND_CONTEXT_FACTOR))
    height = min(canvas.height, max(height, round(canvas.width * EXPAND_MIN_ASPECT)))
    y = 0 if top else canvas.height - height
    return Rect(0, y, canvas.width, height)


# Tiers that expand several sides one side at a time. With the whole canvas as
# context, the SDXL tier (Fooocus patch) reads the old image inside a pre-filled
# ring as a picture in a frame and returns the blurred pre-fill unchanged (a
# vignette); one-sided strips work. SD 1.5 handles the ring and keeps one pass.
SEQUENTIAL_EXPAND_ARCHS = ("sdxl",)


def expand_steps(left: int, top: int, right: int, bottom: int, arch: str) -> list[tuple[int, int, int, int]]:
    """Margins (left, top, right, bottom) of each expand pass.

    One pass with all margins, except for ``SEQUENTIAL_EXPAND_ARCHS`` with two or
    more growing sides: one pass per side, left and right first so the top and
    bottom passes span the widened canvas and also fill the corners.
    """
    margins = (left, top, right, bottom)
    if arch not in SEQUENTIAL_EXPAND_ARCHS or sum(1 for m in margins if m > 0) < 2:
        return [margins]
    steps = []
    for index in (0, 2, 1, 3):
        if margins[index] > 0:
            step = [0, 0, 0, 0]
            step[index] = margins[index]
            steps.append((step[0], step[1], step[2], step[3]))
    return steps


def mask_for_expand(plan: ExpandPlan) -> bytes:
    """8-bit mask covering ``plan.context``: 255 where new content goes."""
    ctx = plan.context
    keep = plan.keep_rect
    out = bytearray(b"\xff" * (ctx.width * ctx.height))
    kx1 = max(keep.x, ctx.x) - ctx.x
    kx2 = min(keep.right, ctx.right) - ctx.x
    ky1 = max(keep.y, ctx.y) - ctx.y
    ky2 = min(keep.bottom, ctx.bottom) - ctx.y
    if kx2 > kx1 and ky2 > ky1:
        zero = bytes(kx2 - kx1)
        for y in range(ky1, ky2):
            start = y * ctx.width + kx1
            out[start : start + len(zero)] = zero
    return bytes(out)


@dataclass(frozen=True)
class MaskParams:
    """Mask sizes derived from the selection (image pixels and working pixels)."""

    grow_image: int  # dilation of the selection, image px (layer mask + model mask)
    feather_image: int  # soft edge of the layer mask, image px
    grow_work: int  # dilation sent to the model, working px
    blur_work: int  # model-side blur, working px, never larger than grow_work


def mask_params(
    selection: Rect,
    scale: float,
    grow_percent: float = 15.0,
    feather_percent: float = 6.0,
    grow_max: int = 48,
    feather_max: int = 24,
    grow_min: int = 6,
) -> MaskParams:
    """Scale mask growth and feathering with the selection instead of using fixed
    pixel radii. A fixed 24 px feather on a 38 px selection leaves no fully
    opaque pixel, so the object shows through; a few percent, capped, does not.
    The model-side blur never exceeds the growth so the original selection stays
    at mask value 1.0 (ComfyUI only treats >= 1.0 as "inpaint here")."""
    side = max(1, max(selection.width, selection.height))
    grow_image = int(max(grow_min, min(grow_max, round(side * grow_percent / 100.0))))
    feather_image = int(max(1, min(feather_max, round(side * feather_percent / 100.0))))
    grow_work = max(1, round(grow_image * scale))
    blur_work = max(0, min(grow_work, round(feather_image * scale)))
    return MaskParams(grow_image, feather_image, grow_work, blur_work)


def estimate_timeout(
    steps: int,
    batch: int,
    pixels: int,
    seconds_per_step_mpx: float = 1.5,
    floor: float = 120.0,
    model_load: float = 90.0,
) -> float:
    """Rough upper bound for a generation, used as the request timeout."""
    mpx = pixels / 1_000_000
    return max(floor, model_load + steps * batch * max(0.25, mpx) * seconds_per_step_mpx * 2)


def seed_or_random(seed: int | None, rng: random.Random | None = None) -> int:
    """Return ``seed`` unless negative/None, in which case draw a 32-bit seed."""
    if seed is not None and seed >= 0:
        return int(seed)
    return (rng or random).randrange(0, 2**32 - 1)


# Margin around the selection, as a multiple of its larger side. Removal keeps a
# wide context (texture continuation); adding prompted content works better with a
# tighter crop, where the hole is a larger part of the frame and the surroundings
# do not outvote the prompt (SD 1.5 otherwise continues a flat sky).
REMOVAL_PADDING = 1.0
PROMPT_PADDING = 0.5
# LaMa/MAT see the context at 512 px at most: a 3x context around a 400 px
# selection is shrunk 2.4x and comes back soft. A 2x context keeps the
# selection near 1:1 while still giving the model surroundings to continue.
REMOVAL_MODEL_PADDING = 0.5


def fill_padding(removal: bool, prompt_free_model: bool = False) -> float:
    if prompt_free_model:
        return REMOVAL_MODEL_PADDING
    return REMOVAL_PADDING if removal else PROMPT_PADDING


# Pre-fill of the hole before sampling, as (style, mode) for the workflow's
# INPAINT_MaskedFill. SD 1.5 needs a neutral grey hole to follow the prompt
# (it continues a border-filled sky instead); the SDXL tier with the Fooocus
# patch treats a flat grey rectangle as a separate picture and paints a framed
# photo or a hard-edged block into it, so it gets the border fill.
NEUTRAL_PREFILL_ARCHS = ("sd15",)


def prefill_for(removal: bool, strength: float, arch: str) -> tuple[str, str]:
    if removal:
        return "border", "navier-stokes"  # nothing of the removed object survives
    if strength < 1.0:
        return "blur", "navier-stokes"  # partial strength keeps the original
    if arch in NEUTRAL_PREFILL_ARCHS:
        return "border", "neutral"
    return "border", "navier-stokes"


# Longest working side for prompted SD 1.5 fills whose context is downscaled
# anyway. At 768 px (above the model's native 512) a large selection came back
# as a flat, untextured block; at 640 px the same fill has brick texture.
SD15_PROMPT_MAX_SIDE = 640


def fill_profile(profile: ModelProfile, context: Rect, arch: str, removal: bool) -> ModelProfile:
    """Profile for the working size of a fill: for a prompted SD 1.5 fill whose
    context needs no upscaling (shorter side at least ``profile.min_side``) the
    longest side is capped at ``SD15_PROMPT_MAX_SIDE``. Small contexts keep the
    full ``max_side`` so their upscale to ``min_side`` is not limited."""
    if removal or arch != "sd15" or min(context.width, context.height) < profile.min_side:
        return profile
    return replace(profile, max_side=min(profile.max_side, max(profile.min_side, SD15_PROMPT_MAX_SIDE)))


def color_match_useful(selection: Rect, context: Rect, image: Rect, min_reference: float = 0.15) -> bool:
    """Colour matching corrects the generated crop against the untouched pixels
    around the selection. Without enough of them (selection covering most of the
    context, or touching three or more canvas edges) it has no reference and
    shifts the whole result (a whole-image fill came back tinted)."""
    sel = selection.intersect(context)
    if context.area <= 0:
        return False
    if 1.0 - sel.area / context.area < min_reference:
        return False
    edges = sum(
        (
            selection.x <= image.x,
            selection.y <= image.y,
            selection.right >= image.right,
            selection.bottom >= image.bottom,
        )
    )
    return edges < 3


# Strength of the colour match for prompted fills (removal always uses 1.0).
PROMPT_COLOR_MATCH = 1.0


def color_match_strength(selection: Rect, context: Rect, image: Rect, removal: bool) -> float:
    """INPAINT_ColorMatch strength for a fill: 0 when there is no reference
    (``color_match_useful``), otherwise full for removal and
    ``PROMPT_COLOR_MATCH`` for prompted fills."""
    if not color_match_useful(selection, context, image):
        return 0.0
    return 1.0 if removal else PROMPT_COLOR_MATCH


def layer_mask_grow(mask: MaskParams, removal: bool) -> int:
    """Dilation of the selection for the GIMP layer mask.

    Removal grows the full amount so the regenerated rim of the object is
    covered. A prompted fill grows only by the feather radius (GIMP's feather
    is centred on the edge), so the mask is fully opaque over the selection and
    fades outward; growing further exposes the model's repainted context as a
    pale band around the fill. Never more than the removal grow.
    """
    if removal:
        return mask.grow_image
    return max(1, min(mask.grow_image, mask.feather_image))


def flatten_over_mean(rgba: bytes) -> bytes:
    """Composite RGBA pixels over the alpha-weighted mean colour of the visible
    ones and return opaque RGBA. Models read RGB only, so transparent pixels
    would otherwise reach them as black. Fully opaque input is returned as is."""
    alpha = rgba[3::4]
    n = len(alpha)
    if n == 0 or alpha.count(255) == n:
        return rgba
    total = sum(alpha)
    if total == 0:
        mean = (128, 128, 128)
    else:
        mean = tuple(round(sum(map(int.__mul__, rgba[c::4], alpha)) / total) for c in range(3))
    out = bytearray(len(rgba))
    for c in range(3):
        m = mean[c]
        out[c::4] = bytes(map(lambda v, a, m=m: (v * a + m * (255 - a) + 127) // 255, rgba[c::4], alpha))
    out[3::4] = b"\xff" * n
    return bytes(out)

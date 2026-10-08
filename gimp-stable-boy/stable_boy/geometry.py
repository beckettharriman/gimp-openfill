# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure geometry helpers: context regions, working sizes, outpaint canvases.

No GIMP imports. Every function here is unit-tested under system Python.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


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

    def intersect(self, other: "Rect") -> "Rect":
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.right, other.right), min(self.bottom, other.bottom)
        return Rect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def contains(self, other: "Rect") -> bool:
        return (self.x <= other.x and self.y <= other.y
                and self.right >= other.right and self.bottom >= other.bottom)

    def translate(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def relative_to(self, origin: "Rect") -> "Rect":
        """This rectangle expressed in the coordinate system of ``origin``."""
        return Rect(self.x - origin.x, self.y - origin.y, self.width, self.height)


@dataclass(frozen=True)
class ModelProfile:
    """Resolution limits of a model family."""

    name: str
    min_side: int      # the model gets unhappy below this (SD 1.5: 512)
    max_side: int      # longest side we send to the model
    min_context: int   # minimum context region size cropped from the image
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
INPAINT_MODEL = ModelProfile("inpaint_model", min_side=256, max_side=1024, min_context=512)
PROFILES = {"sd15": SD15, "sdxl": SDXL, "flux": FLUX, "qwen_image": QWEN, "inpaint_model": INPAINT_MODEL}


def round_to_multiple(value: int, multiple: int) -> int:
    """Round ``value`` to the nearest multiple, never below ``multiple``."""
    return max(multiple, int(round(value / multiple)) * multiple)


def clamp_rect(rect: Rect, bounds: Rect) -> Rect:
    """Move ``rect`` inside ``bounds`` if possible, shrink it if it is larger."""
    width = min(rect.width, bounds.width)
    height = min(rect.height, bounds.height)
    x = min(max(rect.x, bounds.x), bounds.right - width)
    y = min(max(rect.y, bounds.y), bounds.bottom - height)
    return Rect(x, y, width, height)


def context_rect(selection: Rect, image: Rect, profile: ModelProfile,
                 padding_ratio: float = 1.0, min_padding: int = 32) -> Rect:
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
    pad = max(min_padding, int(round(max(selection.width, selection.height) * padding_ratio)))
    width = max(selection.width + 2 * pad, profile.min_context)
    height = max(selection.height + 2 * pad, profile.min_context)
    cx = selection.x + selection.width / 2
    cy = selection.y + selection.height / 2
    grown = Rect(int(round(cx - width / 2)), int(round(cy - height / 2)), width, height)
    return clamp_rect(grown, image)


@dataclass(frozen=True)
class WorkingSize:
    width: int
    height: int
    scale: float  # working / source

    @property
    def is_identity(self) -> bool:
        return self.scale == 1.0


def working_size(source_w: int, source_h: int, profile: ModelProfile,
                 max_upscale: float = 8.0) -> WorkingSize:
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
    width = round_to_multiple(int(round(source_w * scale)), profile.multiple)
    height = round_to_multiple(int(round(source_h * scale)), profile.multiple)
    if width == source_w and height == source_h:
        return WorkingSize(width, height, 1.0)
    return WorkingSize(width, height, width / source_w)


@dataclass(frozen=True)
class ExpandPlan:
    """Result of planning a canvas expansion (outpaint)."""

    image_width: int     # original image size
    image_height: int
    new_width: int
    new_height: int
    offset_x: int        # where the old image lands inside the new canvas
    offset_y: int
    overlap: int         # band of old pixels that is regenerated for blending
    fill_rect: Rect      # bounding box of the generated area, new-canvas coords
    context: Rect        # region sent to the model, new-canvas coords

    @property
    def grows(self) -> tuple[bool, bool, bool, bool]:
        """(left, top, right, bottom)"""
        return (self.offset_x > 0,
                self.offset_y > 0,
                self.new_width - self.offset_x - self.image_width > 0,
                self.new_height - self.offset_y - self.image_height > 0)

    @property
    def keep_rect(self) -> Rect:
        """Old pixels that are left untouched (old image minus overlap bands)."""
        left, top, right, bottom = self.grows
        x1 = self.offset_x + (self.overlap if left else 0)
        y1 = self.offset_y + (self.overlap if top else 0)
        x2 = self.offset_x + self.image_width - (self.overlap if right else 0)
        y2 = self.offset_y + self.image_height - (self.overlap if bottom else 0)
        return Rect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def plan_expand(image_w: int, image_h: int, left: int, top: int, right: int, bottom: int,
                profile: ModelProfile, overlap: int = 32) -> ExpandPlan:
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
    context = context_rect(fill, canvas, profile)
    return ExpandPlan(image_w, image_h, new_w, new_h, left, top, overlap, fill, context)


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
            out[start:start + len(zero)] = zero
    return bytes(out)


@dataclass(frozen=True)
class MaskParams:
    """Mask sizes derived from the selection (image pixels and working pixels)."""

    grow_image: int      # dilation of the selection, image px (layer mask + model mask)
    feather_image: int   # soft edge of the layer mask, image px
    grow_work: int       # dilation sent to the model, working px
    blur_work: int       # model-side blur, working px, never larger than grow_work


def mask_params(selection: Rect, scale: float, grow_percent: float = 15.0, feather_percent: float = 6.0,
                grow_max: int = 48, feather_max: int = 24, grow_min: int = 6) -> MaskParams:
    """Scale mask growth and feathering with the selection instead of using fixed
    pixel radii. A fixed 24 px feather on a 38 px selection leaves no fully
    opaque pixel, so the object shows through; a few percent, capped, does not.
    The model-side blur never exceeds the growth so the original selection stays
    at mask value 1.0 (ComfyUI only treats >= 1.0 as "inpaint here")."""
    side = max(1, max(selection.width, selection.height))
    grow_image = int(max(grow_min, min(grow_max, round(side * grow_percent / 100.0))))
    feather_image = int(max(1, min(feather_max, round(side * feather_percent / 100.0))))
    grow_work = max(1, int(round(grow_image * scale)))
    blur_work = max(0, min(grow_work, int(round(feather_image * scale))))
    return MaskParams(grow_image, feather_image, grow_work, blur_work)


def estimate_timeout(steps: int, batch: int, pixels: int, seconds_per_step_mpx: float = 1.5,
                     floor: float = 120.0, model_load: float = 90.0) -> float:
    """Rough upper bound for a generation, used as the request timeout."""
    mpx = pixels / 1_000_000
    return max(floor, model_load + steps * batch * max(0.25, mpx) * seconds_per_step_mpx * 2)


def seed_or_random(seed: int | None, rng: random.Random | None = None) -> int:
    """Return ``seed`` unless negative/None, in which case draw a 32-bit seed."""
    if seed is not None and seed >= 0:
        return int(seed)
    return (rng or random).randrange(0, 2**32 - 1)

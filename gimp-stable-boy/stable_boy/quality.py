# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cheap quality metrics for ranking the variations of a fill.

Every candidate is compared with the original context around the selection,
on small buffers (a downsampled context, see ``caption.sample``):

- seam: gradient on the selection edge against the gradient a few pixels to
  either side (a step at the edge shows up as a ratio above 1);
- softness: Laplacian variance inside the selection against a ring outside
  it (a smeared fill is far below 1; for removal an invented object is far
  above it);
- frame: colour difference between a thin band just inside the edge and one
  just outside it (a pale frame or a pasted panel);
- colour: mean and spread of the whole inside against the ring (removal only;
  a prompted fill is supposed to differ from its surroundings);
- leak: change outside the selection, where the layer mask's feather shows
  the generated pixels.

Lower scores are better. Pure Python; no GIMP imports.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

INF = 1 << 20


@dataclass(frozen=True)
class Buffer:
    """An 8-bit interleaved pixel buffer."""

    width: int
    height: int
    data: bytes
    channels: int = 3

    def luminance(self) -> list[float]:
        c, d = self.channels, self.data
        if c < 3:
            return [d[i * c] / 255.0 for i in range(self.width * self.height)]
        return [
            (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255.0
            for i in range(0, self.width * self.height * c, c)
        ]

    def rgb(self, index: int) -> tuple[float, float, float]:
        o = index * self.channels
        if self.channels < 3:
            v = self.data[o] / 255.0
            return v, v, v
        return self.data[o] / 255.0, self.data[o + 1] / 255.0, self.data[o + 2] / 255.0


@dataclass(frozen=True)
class Score:
    seam: float  # edge gradient / gradient beside it
    lap_ratio: float  # Laplacian variance inside / ring
    frame: float  # colour step across the edge, inside band against outside band
    colour: float  # inside against ring (mean and spread)
    leak: float  # mean absolute change outside the selection
    total: float  # weighted penalty, lower is better


def signed_distance(width: int, height: int, mask: bytes, threshold: int = 128) -> list[int]:
    """Chessboard distance to the selection edge: positive outside the
    selection (mask below ``threshold``), zero or negative inside it."""
    n = width * height
    inside = [mask[i] >= threshold for i in range(n)]

    def chamfer(seed: list[bool]) -> list[int]:
        d = [0 if s else INF for s in seed]
        for y in range(height):
            row = y * width
            for x in range(width):
                i = row + x
                if d[i] == 0:
                    continue
                best = d[i]
                if x > 0:
                    best = min(best, d[i - 1] + 1)
                if y > 0:
                    best = min(best, d[i - width] + 1)
                    if x > 0:
                        best = min(best, d[i - width - 1] + 1)
                    if x < width - 1:
                        best = min(best, d[i - width + 1] + 1)
                d[i] = best
        for y in range(height - 1, -1, -1):
            row = y * width
            for x in range(width - 1, -1, -1):
                i = row + x
                best = d[i]
                if x < width - 1:
                    best = min(best, d[i + 1] + 1)
                if y < height - 1:
                    best = min(best, d[i + width] + 1)
                    if x < width - 1:
                        best = min(best, d[i + width + 1] + 1)
                    if x > 0:
                        best = min(best, d[i + width - 1] + 1)
                d[i] = best
        return d

    to_inside = chamfer(inside)  # outside pixels: distance to the selection
    to_outside = chamfer([not s for s in inside])  # inside pixels: distance to the outside
    return [to_inside[i] if not inside[i] else 1 - to_outside[i] for i in range(n)]


def _grad_lap(lum: list[float], width: int, height: int) -> tuple[list[float], list[float]]:
    grad = [0.0] * (width * height)
    lap = [0.0] * (width * height)
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            i = row + x
            up, dn, lf, rt = lum[i - width], lum[i + width], lum[i - 1], lum[i + 1]
            grad[i] = math.hypot(rt - lf, dn - up) / 2
            lap[i] = up + dn + lf + rt - 4 * lum[i]
    return grad, lap


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _var(values: list[float]) -> float:
    if not values:
        return 0.0
    m = _mean(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _colour_stats(buf: Buffer, indices: list[int]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if not indices:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    chans = list(zip(*(buf.rgb(i) for i in indices), strict=False))
    means = tuple(_mean(list(c)) for c in chans)
    spreads = tuple(math.sqrt(_var(list(c))) for c in chans)
    return means, spreads


def score(
    original: Buffer,
    candidate: Buffer,
    mask: bytes,
    removal: bool,
    distance: list[int] | None = None,
) -> Score:
    """Score ``candidate`` (the generated context) against ``original`` (the
    same context before the fill); ``mask`` has one byte per pixel, 255 inside
    the selection. Buffers must have the same size."""
    w, h = candidate.width, candidate.height
    if (original.width, original.height) != (w, h):
        raise ValueError("original and candidate differ in size")
    d = distance if distance is not None else signed_distance(w, h, mask)
    lum = candidate.luminance()
    grad, lap = _grad_lap(lum, w, h)
    interior = [y * w + x for y in range(1, h - 1) for x in range(1, w - 1)]
    edge = [i for i in interior if -1 <= d[i] <= 1]
    beside = [i for i in interior if 3 <= abs(d[i]) <= 8]
    inner = [i for i in interior if d[i] <= -2]
    ring = [i for i in interior if 2 <= d[i] <= 10]
    band_in = [i for i in interior if -4 <= d[i] <= -1]
    band_out = [i for i in interior if 2 <= d[i] <= 5]
    seam = _mean([grad[i] for i in edge]) / max(1e-6, _mean([grad[i] for i in beside])) if edge and beside else 1.0
    lap_ratio = _var([lap[i] for i in inner]) / max(1e-9, _var([lap[i] for i in ring])) if inner and ring else 1.0
    m_in, _ = _colour_stats(candidate, band_in)
    m_out, _ = _colour_stats(candidate, band_out)
    frame = math.sqrt(sum((a - b) ** 2 for a, b in zip(m_in, m_out, strict=False)))
    whole_in, s_in = _colour_stats(candidate, inner)
    m_ring, s_ring = _colour_stats(original, ring)
    colour = math.sqrt(sum((a - b) ** 2 for a, b in zip(whole_in, m_ring, strict=False))) + 0.5 * math.sqrt(
        sum((a - b) ** 2 for a, b in zip(s_in, s_ring, strict=False))
    )
    outside = [i for i in interior if d[i] >= 2]
    leak = (
        _mean([abs(a - b) for i in outside for a, b in zip(candidate.rgb(i), original.rgb(i), strict=False)])
        if outside
        else 0.0
    )
    penalty = 2.0 * max(0.0, seam - 1.0)
    penalty += 0.6 * max(0.0, -math.log(max(lap_ratio, 1e-6)))  # softer than the surroundings
    if removal:
        penalty += 0.6 * max(0.0, math.log(max(lap_ratio, 1e-6) / 1.5))  # busier: something was invented
        penalty += 3.0 * colour
    penalty += 6.0 * frame + 8.0 * leak
    return Score(seam, lap_ratio, frame, colour, leak, penalty)


def rank(original: Buffer, candidates: list[Buffer], mask: bytes, removal: bool) -> list[int]:
    """Indices of ``candidates``, best first (stable for equal scores)."""
    if len(candidates) < 2:
        return list(range(len(candidates)))
    d = signed_distance(original.width, original.height, mask)
    totals = [score(original, c, mask, removal, d).total for c in candidates]
    return sorted(range(len(candidates)), key=lambda i: (totals[i], i))


# --------------------------------------------------------------- grain -------

# Residual of a pixel against the mean of its four neighbours, for pure
# Gaussian noise of deviation s, has deviation s * sqrt(1.25).
_RESIDUAL_GAIN = math.sqrt(1.25)
# Largest local luminance range (8-bit levels) of a pixel neighbourhood that
# still counts as flat: noise is measured there, not texture or edges.
FLAT_RANGE = 24


def noise_sigma(
    width: int, height: int, data: bytes, channels: int, mask: bytes | None = None, inside: bool = False, step: int = 2
) -> float:
    """Noise deviation (8-bit levels) of the luminance in flat areas, from the
    median absolute residual against the four neighbours. With ``mask`` only
    pixels outside it (or inside it with ``inside``) count; every ``step``-th
    row and column is sampled. 0 when there are too few flat pixels."""
    c = channels
    residuals = []
    for y in range(1, height - 1, step):
        for x in range(1, width - 1, step):
            i = y * width + x
            if mask is not None and (mask[i] >= 128) != inside:
                continue

            def lum(j: int) -> float:
                o = j * c
                if c < 3:
                    return float(data[o])
                return 0.299 * data[o] + 0.587 * data[o + 1] + 0.114 * data[o + 2]

            v, up, dn, lf, rt = lum(i), lum(i - width), lum(i + width), lum(i - 1), lum(i + 1)
            if max(v, up, dn, lf, rt) - min(v, up, dn, lf, rt) > FLAT_RANGE:
                continue
            residuals.append(abs(v - (up + dn + lf + rt) / 4))
    if len(residuals) < 64:
        return 0.0
    residuals.sort()
    return 1.4826 * residuals[len(residuals) // 2] / _RESIDUAL_GAIN


def grain_to_add(ring_sigma: float, inside_sigma: float, minimum: float = 1.0) -> float:
    """Deviation of the noise that brings ``inside_sigma`` up to ``ring_sigma``
    (they add in quadrature); 0 below ``minimum`` levels (invisible)."""
    add = math.sqrt(max(0.0, ring_sigma * ring_sigma - inside_sigma * inside_sigma))
    return add if add >= minimum else 0.0


def add_grain(data: bytes, channels: int, sigma: float, seed: int = 0) -> bytes:
    """Add monochrome Gaussian noise of deviation ``sigma`` (8-bit levels) to
    the colour channels of an interleaved 8-bit buffer (alpha untouched). The
    same offset goes to R, G and B so the grain has no colour."""
    if sigma <= 0 or not data:
        return data
    n = len(data) // channels
    # 256 quantiles of the normal distribution, indexed by a random byte
    offsets = [round(sigma * _normal_quantile((k + 0.5) / 256)) for k in range(256)]
    table = bytes(max(0, min(255, v + offsets[k])) for v in range(256) for k in range(256))
    noise = random.Random(seed).randbytes(n)
    out = bytearray(data)
    colours = min(3, channels)
    for ch in range(colours):
        values = data[ch::channels]
        out[ch::channels] = bytes(map(table.__getitem__, map(int.__add__, map((256).__mul__, values), noise)))
    return bytes(out)


def _normal_quantile(p: float) -> float:
    """Inverse of the standard normal CDF (Acklam's rational approximation)."""
    a = (
        -39.69683028665376,
        220.9460984245205,
        -275.9285104469687,
        138.3577518672690,
        -30.66479806614716,
        2.506628277459239,
    )
    b = (-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572)
    c = (
        -0.007784894002430293,
        -0.3223964580411365,
        -2.400758277161838,
        -2.549732539343734,
        4.374664141464968,
        2.938163982698783,
    )
    d = (0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416)
    low = 0.02425
    if p < low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > 1 - low:
        return -_normal_quantile(1 - p)
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )

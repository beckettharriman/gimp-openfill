# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Everything that touches the GIMP API lives here.

Pixel export reads straight from GEGL buffers (no temporary exports); results
come back through ``Gimp.file_load_layer`` so GIMP's own PNG loader handles
color management.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, Gimp, Gio  # noqa: E402

from . import png  # noqa: E402
from .geometry import Rect  # noqa: E402

RGBA = "R'G'B'A u8"
GRAY = "Y u8"


class GimpIoError(RuntimeError):
    pass


# ---------------------------------------------------------------- reading ----

def image_rect(image: Gimp.Image) -> Rect:
    return Rect(0, 0, image.get_width(), image.get_height())


def selection_rect(image: Gimp.Image) -> Rect | None:
    """Bounding box of the selection, or None when nothing is selected."""
    non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
    if not non_empty:
        return None
    return Rect(x1, y1, x2 - x1, y2 - y1)


def _read_buffer(buffer: Gegl.Buffer, rect: Rect, fmt: str) -> bytes:
    region = Gegl.Rectangle.new(rect.x, rect.y, rect.width, rect.height)
    data = buffer.get(region, 1.0, fmt, Gegl.AbyssPolicy.CLAMP)
    return bytes(data)


def export_region_png(image: Gimp.Image, rect: Rect) -> bytes:
    """Composite of all visible layers inside ``rect`` as an RGBA PNG."""
    layer = Gimp.Layer.new_from_visible(image, image, "stable-boy export")
    if layer is None:
        raise GimpIoError("GIMP could not render the visible image")
    try:
        pixels = _read_buffer(layer.get_buffer(), rect, RGBA)
    finally:
        layer.delete()
    expected = rect.width * rect.height * 4
    if len(pixels) != expected:
        raise GimpIoError(f"read {len(pixels)} bytes, expected {expected}")
    return png.encode(rect.width, rect.height, pixels, 4)


def export_selection_mask_png(image: Gimp.Image, rect: Rect) -> bytes:
    """The selection channel inside ``rect`` as an 8-bit gray PNG (255 = selected)."""
    selection = image.get_selection()
    pixels = _read_buffer(selection.get_buffer(), rect, GRAY)
    expected = rect.width * rect.height
    if len(pixels) != expected:
        raise GimpIoError(f"read {len(pixels)} mask bytes, expected {expected}")
    return png.encode(rect.width, rect.height, pixels, 1)


def mask_png_from_bytes(rect: Rect, pixels: bytes) -> bytes:
    return png.encode(rect.width, rect.height, pixels, 1)


# ---------------------------------------------------------------- writing ----

def write_temp_png(data: bytes, directory: Path | None = None, prefix: str = "stable-boy-") -> Path:
    directory = Path(directory) if directory else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=".png", dir=str(directory))
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return Path(name)


def load_layer_from_png(image: Gimp.Image, data: bytes, name: str, temp_dir: Path | None = None) -> Gimp.Layer:
    path = write_temp_png(data, temp_dir)
    try:
        layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(str(path)))
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    if layer is None:
        raise GimpIoError("GIMP could not load the generated image")
    layer.set_name(name)
    if not layer.has_alpha():
        layer.add_alpha()
    return layer


class SavedSelection:
    """Context manager that snapshots the selection and restores it on exit."""

    def __init__(self, image: Gimp.Image) -> None:
        self.image = image
        self.channel: Gimp.Channel | None = None
        self.was_empty = Gimp.Selection.is_empty(image)

    def __enter__(self) -> "SavedSelection":
        if not self.was_empty:
            self.channel = Gimp.Selection.save(self.image)
        return self

    def __exit__(self, *exc) -> None:
        if self.channel is not None:
            self.image.select_item(Gimp.ChannelOps.REPLACE, self.channel)
            self.image.remove_channel(self.channel)
        else:
            Gimp.Selection.none(self.image)


def select_from_mask(image: Gimp.Image, rect: Rect, pixels: bytes) -> None:
    """Replace the selection with an 8-bit mask covering ``rect``."""
    channel = Gimp.Channel.new(image, "stable-boy mask", image.get_width(), image.get_height(),
                               100.0, Gegl.Color.new("black"))
    if channel is None:
        raise GimpIoError("GIMP could not create a temporary channel")
    buffer = channel.get_buffer()
    buffer.set(Gegl.Rectangle.new(rect.x, rect.y, rect.width, rect.height), GRAY, pixels)
    buffer.flush()
    image.insert_channel(channel, None, 0)
    try:
        image.select_item(Gimp.ChannelOps.REPLACE, channel)
    finally:
        image.remove_channel(channel)


def add_selection_mask(image: Gimp.Image, layer: Gimp.Layer, selection: Gimp.Channel | None,
                       feather: float, mask_rect: Rect | None = None,
                       mask_pixels: bytes | None = None) -> None:
    """Attach a layer mask (feathered selection or explicit mask) to ``layer``."""
    if mask_pixels is not None and mask_rect is not None:
        select_from_mask(image, mask_rect, mask_pixels)
    elif selection is not None:
        image.select_item(Gimp.ChannelOps.REPLACE, selection)
    else:
        Gimp.Selection.all(image)
    if feather > 0:
        Gimp.Selection.feather(image, feather)
    mask = layer.create_mask(Gimp.AddMaskType.SELECTION)
    layer.add_mask(mask)


def insert_results(image: Gimp.Image, images: list[bytes], origin: Rect, base_name: str,
                   feather: float, temp_dir: Path | None, use_selection_mask: bool = True,
                   group_variations: bool = True, mask_pixels: bytes | None = None) -> list[Gimp.Layer]:
    """Insert generated PNGs as layers at ``origin`` with a feathered mask.

    The mask comes from the user's selection, or from ``mask_pixels`` (an
    8-bit mask the size of ``origin``) when given. Several variations go into
    a layer group; only the first is visible. Runs inside one undo group and
    restores the user's selection.
    """
    layers: list[Gimp.Layer] = []
    image.undo_group_start()
    try:
        with SavedSelection(image) as saved:
            parent = None
            if group_variations and len(images) > 1:
                parent = Gimp.GroupLayer.new(image, base_name)
                image.insert_layer(parent, None, 0)
            for index, data in enumerate(images):
                name = base_name if len(images) == 1 else f"{base_name} ({index + 1})"
                layer = load_layer_from_png(image, data, name, temp_dir)
                layer.set_offsets(origin.x, origin.y)
                image.insert_layer(layer, parent, index)
                if use_selection_mask:
                    add_selection_mask(image, layer, saved.channel, feather, origin, mask_pixels)
                layer.set_visible(index == 0)
                layers.append(layer)
            if layers:
                image.set_selected_layers([layers[0]])
    finally:
        image.undo_group_end()
    Gimp.displays_flush()
    return layers


def resize_canvas(image: Gimp.Image, new_w: int, new_h: int, off_x: int, off_y: int) -> None:
    image.resize(new_w, new_h, off_x, off_y)


def new_image_from_pngs(images: list[bytes], base_name: str, temp_dir: Path | None) -> Gimp.Image:
    w, h, _, _ = png.read_header(images[0])
    image = Gimp.Image.new(w, h, Gimp.ImageBaseType.RGB)
    image.undo_disable()
    for index, data in enumerate(images):
        name = base_name if len(images) == 1 else f"{base_name} ({index + 1})"
        layer = load_layer_from_png(image, data, name, temp_dir)
        image.insert_layer(layer, None, index)
        layer.set_visible(index == 0)
    image.undo_enable()
    Gimp.Display.new(image)
    Gimp.displays_flush()
    return image


def profile_dir() -> str:
    return Gimp.directory()


def message(text: str) -> None:
    Gimp.message(text)


class GimpProgress:
    """Adapter from the backend progress callback to GIMP's progress bar."""

    def __init__(self, title: str) -> None:
        Gimp.progress_init(title)

    def __call__(self, fraction: float, text: str) -> None:
        if text:
            Gimp.progress_set_text(text)
        Gimp.progress_update(max(0.0, min(1.0, float(fraction))))

    def done(self) -> None:
        Gimp.progress_update(1.0)
        Gimp.progress_end()

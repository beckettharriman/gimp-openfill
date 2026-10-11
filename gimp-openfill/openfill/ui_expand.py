# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
# SPDX-License-Identifier: GPL-3.0-or-later
"""The visual canvas editor of the Generative Expand dialog.

The top half of this module is plain Python (no ``gi``) and unit tested:
the margins model, aspect-ratio presets, the 3x3 anchor, the on-screen
layout of the thumbnail and the new-canvas frame, hit-testing of the eight
handles and the drag math. The bottom half is the GTK widget
(:class:`ExpandEditor`, a ``Gtk.DrawingArea``) that only draws that state
and turns pointer events into calls of the pure functions. It is defined
only when GTK can be imported.

The procedure keeps its arguments (left, top, right, bottom in pixels), so
scripts that call Generative Expand are not affected by any of this.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

MAX_MARGIN = 4096  # the range of the left/top/right/bottom procedure arguments
SNAP = 8  # dragging snaps to multiples of this many image pixels
ORIGINAL_GROW = 0.25  # "Original" (or a preset equal to the image ratio) grows each side of the canvas by 25 %
THUMB_PX = 360  # the image thumbnail fits in this many screen pixels
PAD = 14  # screen pixels between the new-canvas frame and the widget edge
HANDLE_PX = 9  # side of a drawn handle square
HIT_PX = 9  # how far from a handle or edge the pointer may be to grab it

SIDES = ("left", "top", "right", "bottom")

# (id, label, ratio) - ratio None: "original" uses the image ratio, "custom" keeps the margins.
PRESETS: tuple[tuple[str, str, tuple[int, int] | None], ...] = (
    ("original", "Original", None),
    ("1:1", "1:1", (1, 1)),
    ("4:5", "4:5", (4, 5)),
    ("5:4", "5:4", (5, 4)),
    ("3:2", "3:2", (3, 2)),
    ("2:3", "2:3", (2, 3)),
    ("16:9", "16:9", (16, 9)),
    ("9:16", "9:16", (9, 16)),
    ("custom", "Custom", None),
)
PRESET_IDS = tuple(p[0] for p in PRESETS)

# Anchor = where the old image sits in the new canvas, as (column, row) 0..2.
ANCHORS: dict[str, tuple[int, int]] = {
    "top-left": (0, 0),
    "top": (1, 0),
    "top-right": (2, 0),
    "left": (0, 1),
    "center": (1, 1),
    "right": (2, 1),
    "bottom-left": (0, 2),
    "bottom": (1, 2),
    "bottom-right": (2, 2),
}
ANCHOR_AT = {pos: name for name, pos in ANCHORS.items()}

HANDLES = ("top-left", "top", "top-right", "right", "bottom-right", "bottom", "bottom-left", "left")
# CSS cursor names (Gdk.Cursor.new_from_name) for each handle.
CURSORS = {
    "left": "w-resize",
    "right": "e-resize",
    "top": "n-resize",
    "bottom": "s-resize",
    "top-left": "nw-resize",
    "top-right": "ne-resize",
    "bottom-left": "sw-resize",
    "bottom-right": "se-resize",
}


# ------------------------------------------------------------- margins ----


@dataclass(frozen=True)
class Margins:
    """Pixels added on each side of the image."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @classmethod
    def from_dict(cls, values: dict, limit: int = MAX_MARGIN) -> Margins:
        """From a dict with left/top/right/bottom (missing or junk values are 0), clamped."""
        out = {}
        for side in SIDES:
            try:
                out[side] = clamp_margin(int(values.get(side, 0) or 0), limit)
            except (TypeError, ValueError):
                out[side] = 0
        return cls(**out)

    def as_dict(self) -> dict[str, int]:
        return {side: getattr(self, side) for side in SIDES}

    def canvas(self, image_w: int, image_h: int) -> tuple[int, int]:
        """The new canvas size."""
        return image_w + self.left + self.right, image_h + self.top + self.bottom

    def is_empty(self) -> bool:
        return not (self.left or self.top or self.right or self.bottom)

    def replace(self, **sides: int) -> Margins:
        values = self.as_dict()
        values.update(sides)
        return Margins(**values)


def clamp_margin(value: float, limit: int = MAX_MARGIN) -> int:
    """A margin as a whole number of pixels between 0 and ``limit``."""
    if value != value:  # NaN
        return 0
    return int(max(0, min(limit, math.floor(value + 0.5))))


def clamp_margins(margins: Margins, limit: int = MAX_MARGIN) -> Margins:
    return Margins(*(clamp_margin(getattr(margins, s), limit) for s in SIDES))


# ------------------------------------------------------ presets/anchor ----


def split(extra: int, index: int) -> tuple[int, int]:
    """Split ``extra`` pixels into (before, after) for anchor column/row ``index``
    (0: image at the start, all the space after it; 1: centred; 2: at the end)."""
    extra = max(0, int(extra))
    if index <= 0:
        return 0, extra
    if index >= 2:
        return extra, 0
    before = extra // 2
    return before, extra - before


def preset_ratio(preset: str, image_w: int, image_h: int) -> tuple[int, int] | None:
    """The (width, height) ratio of ``preset``; None for "custom" or an unknown id."""
    if preset == "original":
        return (max(1, image_w), max(1, image_h))
    for pid, _label, ratio in PRESETS:
        if pid == preset:
            return ratio
    return None


def target_canvas(image_w: int, image_h: int, ratio: tuple[int, int], grow: float = ORIGINAL_GROW) -> tuple[int, int]:
    """The smallest canvas with ``ratio`` that contains the image. When the
    image already has that ratio, the canvas grows by ``grow`` on both axes
    (the ratio is kept), so a preset always adds some space."""
    rw, rh = ratio
    if image_w * rh < image_h * rw:  # image narrower than the ratio: add width
        width = math.ceil(image_h * rw / rh - 1e-9)
        if width - image_w >= 1:
            return width, image_h
    elif image_w * rh > image_h * rw:  # image wider: add height
        height = math.ceil(image_w * rh / rw - 1e-9)
        if height - image_h >= 1:
            return image_w, height
    width = image_w + max(1, round(image_w * grow))
    return width, max(image_h, round(width * image_h / image_w))


def anchor_margins(
    image_w: int, image_h: int, canvas_w: int, canvas_h: int, anchor: str, limit: int = MAX_MARGIN
) -> Margins:
    """Margins that place the image at ``anchor`` in a ``canvas_w`` x ``canvas_h`` canvas."""
    col, row = ANCHORS.get(anchor, (1, 1))
    left, right = split(canvas_w - image_w, col)
    top, bottom = split(canvas_h - image_h, row)
    return clamp_margins(Margins(left, top, right, bottom), limit)


def preset_margins(
    image_w: int, image_h: int, preset: str, anchor: str = "center", limit: int = MAX_MARGIN
) -> Margins | None:
    """Margins for an aspect-ratio preset and anchor; None for "custom"."""
    ratio = preset_ratio(preset, image_w, image_h)
    if ratio is None or image_w <= 0 or image_h <= 0:
        return None
    canvas_w, canvas_h = target_canvas(image_w, image_h, ratio)
    return anchor_margins(image_w, image_h, canvas_w, canvas_h, anchor, limit)


def reanchor(margins: Margins, anchor: str, limit: int = MAX_MARGIN) -> Margins:
    """Keep the added width and height, move the image to ``anchor``."""
    col, row = ANCHORS.get(anchor, (1, 1))
    left, right = split(margins.left + margins.right, col)
    top, bottom = split(margins.top + margins.bottom, row)
    return clamp_margins(Margins(left, top, right, bottom), limit)


def anchor_of(margins: Margins, fallback: str = "center") -> str:
    """The anchor that describes ``margins``. An axis without added space
    keeps the column or row of ``fallback``."""
    fcol, frow = ANCHORS.get(fallback, (1, 1))

    def index(before: int, after: int, keep: int) -> int:
        if before == 0 and after == 0:
            return keep
        if before == 0:
            return 0
        if after == 0:
            return 2
        return 1

    col = index(margins.left, margins.right, fcol)
    row = index(margins.top, margins.bottom, frow)
    return ANCHOR_AT[(col, row)]


def matching_preset(image_w: int, image_h: int, margins: Margins, anchor: str) -> str:
    """The preset that gives exactly ``margins`` with ``anchor``, else "custom"."""
    for pid in PRESET_IDS:
        if pid != "custom" and preset_margins(image_w, image_h, pid, anchor) == margins:
            return pid
    return "custom"


# ------------------------------------------------------------- layout -----


@dataclass(frozen=True)
class View:
    """Screen geometry: ``scale`` screen px per image px, the image rectangle
    (ix, iy, iw, ih) and the new-canvas frame (fx, fy, fw, fh)."""

    scale: float
    ix: float
    iy: float
    iw: float
    ih: float
    fx: float
    fy: float
    fw: float
    fh: float


def fit_view(
    area_w: int,
    area_h: int,
    image_w: int,
    image_h: int,
    margins: Margins,
    thumb_px: int = THUMB_PX,
    pad: int = PAD,
) -> View:
    """Scale so the image fits ``thumb_px`` and the whole new canvas fits the
    area (minus ``pad``), and centre the canvas in the area."""
    image_w, image_h = max(1, image_w), max(1, image_h)
    canvas_w, canvas_h = margins.canvas(image_w, image_h)
    room_w, room_h = max(1, area_w - 2 * pad), max(1, area_h - 2 * pad)
    scale = min(thumb_px / max(image_w, image_h), room_w / canvas_w, room_h / canvas_h)
    fx = (area_w - canvas_w * scale) / 2
    fy = (area_h - canvas_h * scale) / 2
    return view_at(scale, fx + margins.left * scale, fy + margins.top * scale, image_w, image_h, margins)


def view_at(scale: float, ix: float, iy: float, image_w: int, image_h: int, margins: Margins) -> View:
    """The view with a fixed scale and image position (used while dragging,
    so the image does not move under the pointer)."""
    return View(
        scale,
        ix,
        iy,
        image_w * scale,
        image_h * scale,
        ix - margins.left * scale,
        iy - margins.top * scale,
        (image_w + margins.left + margins.right) * scale,
        (image_h + margins.top + margins.bottom) * scale,
    )


def handle_points(view: View) -> dict[str, tuple[float, float]]:
    """Centre of each of the eight handles on the frame."""
    x0, y0 = view.fx, view.fy
    x1, y1 = view.fx + view.fw, view.fy + view.fh
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    return {
        "top-left": (x0, y0),
        "top": (xm, y0),
        "top-right": (x1, y0),
        "right": (x1, ym),
        "bottom-right": (x1, y1),
        "bottom": (xm, y1),
        "bottom-left": (x0, y1),
        "left": (x0, ym),
    }


def hit_test(view: View, x: float, y: float, tolerance: float = HIT_PX) -> str | None:
    """The handle under the pointer: a corner, else an edge (anywhere along
    it), else None. Corners win over edges so small frames stay usable."""
    best, best_d = None, None
    for name, (hx, hy) in handle_points(view).items():
        if "-" not in name:
            continue
        d = max(abs(x - hx), abs(y - hy))
        if d <= tolerance and (best_d is None or d < best_d):
            best, best_d = name, d
    if best:
        return best
    x0, y0 = view.fx, view.fy
    x1, y1 = view.fx + view.fw, view.fy + view.fh
    within_y = y0 - tolerance <= y <= y1 + tolerance
    within_x = x0 - tolerance <= x <= x1 + tolerance
    candidates = []
    if within_y:
        candidates += [(abs(x - x0), "left"), (abs(x - x1), "right")]
    if within_x:
        candidates += [(abs(y - y0), "top"), (abs(y - y1), "bottom")]
    candidates = [c for c in candidates if c[0] <= tolerance]
    return min(candidates)[1] if candidates else None


def snap(value: float, step: int = SNAP) -> int:
    """Round to the nearest multiple of ``step`` (halves round up)."""
    step = max(1, int(step))
    return math.floor(value / step + 0.5) * step


def drag_margins(
    start: Margins, handle: str, dx: float, dy: float, scale: float, limit: int = MAX_MARGIN, step: int = SNAP
) -> Margins:
    """Margins after dragging ``handle`` by (dx, dy) screen pixels from where
    the drag started with ``start``. Outward adds space, inward removes it
    (never below 0 or above ``limit``); results snap to ``step`` pixels."""
    if scale <= 0 or handle not in CURSORS:
        return start
    px, py = dx / scale, dy / scale
    values = start.as_dict()
    if "left" in handle:
        values["left"] = start.left - px
    if "right" in handle:
        values["right"] = start.right + px
    if "top" in handle:
        values["top"] = start.top - py
    if "bottom" in handle:
        values["bottom"] = start.bottom + py
    moved = {side: clamp_margin(snap(v, step), limit) if v != getattr(start, side) else v for side, v in values.items()}
    return Margins(**{s: int(v) for s, v in moved.items()})


# -------------------------------------------------------------- state -----


class ExpandState:
    """Margins, preset and anchor of the editor, kept consistent.

    Every change goes through a method here, so the dialog widgets (editor,
    preset buttons, anchor grid, spin boxes) only display this state.
    ``listener`` is called after each change.
    """

    def __init__(
        self,
        image_w: int,
        image_h: int,
        margins: Margins | None = None,
        limit: int = MAX_MARGIN,
        listener: Callable[[], None] | None = None,
    ) -> None:
        self.image_w = max(1, int(image_w))
        self.image_h = max(1, int(image_h))
        self.limit = limit
        self.margins = clamp_margins(margins or Margins(), limit)
        self.anchor = anchor_of(self.margins)
        self.preset = matching_preset(self.image_w, self.image_h, self.margins, self.anchor)
        self.listener = listener

    def _changed(self) -> None:
        if self.listener is not None:
            self.listener()

    @property
    def canvas(self) -> tuple[int, int]:
        return self.margins.canvas(self.image_w, self.image_h)

    def set_margins(self, margins: Margins) -> None:
        """A free change (drag or spin box): the preset follows the result."""
        margins = clamp_margins(margins, self.limit)
        if margins == self.margins:
            return
        self.margins = margins
        self.anchor = anchor_of(margins, self.anchor)
        self.preset = matching_preset(self.image_w, self.image_h, margins, self.anchor)
        self._changed()

    def set_side(self, side: str, value: float) -> None:
        if side in SIDES:
            self.set_margins(self.margins.replace(**{side: clamp_margin(value, self.limit)}))

    def apply_preset(self, preset: str) -> None:
        """Pick an aspect-ratio preset; "custom" keeps the margins as they are."""
        if preset not in PRESET_IDS:
            return
        self.preset = preset
        margins = preset_margins(self.image_w, self.image_h, preset, self.anchor, self.limit)
        if margins is not None:
            self.margins = margins
        self._changed()

    def set_anchor(self, anchor: str) -> None:
        """Move the image to ``anchor``, keeping the added width and height."""
        if anchor not in ANCHORS:
            return
        self.anchor = anchor
        self.margins = reanchor(self.margins, anchor, self.limit)
        if self.preset != "custom":
            margins = preset_margins(self.image_w, self.image_h, self.preset, anchor, self.limit)
            if margins is not None:
                self.margins = margins
        self._changed()


# ---------------------------------------------------------------- GTK -----

try:  # the pure part above must import without GTK (unit tests)
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk
except (ImportError, ValueError):  # pragma: no cover - no GTK in the test Python
    Gtk = None  # type: ignore[assignment]


if Gtk is not None:

    class ExpandEditor(Gtk.DrawingArea):
        """Thumbnail of the image inside the dashed frame of the new canvas.

        Drag an edge or corner handle outward to add space; the new area is
        shaded and its size is written on it. While a drag runs the scale is
        frozen (the image stays under the pointer); on release the view fits
        the new canvas again.
        """

        def __init__(self, state: ExpandState, thumbnail: object | None = None) -> None:
            super().__init__()
            self.state = state
            self.thumbnail = thumbnail  # GdkPixbuf.Pixbuf or None
            self.hover: str | None = None
            self._drag: tuple[str, float, float, Margins, View] | None = None
            self.set_size_request(560, 340)
            self.set_hexpand(True)
            self.set_can_focus(False)
            self.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.BUTTON_RELEASE_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )
            self.connect("draw", self._draw)
            self.connect("button-press-event", self._press)
            self.connect("button-release-event", self._release)
            self.connect("motion-notify-event", self._motion)
            self.connect("leave-notify-event", self._leave)

        # geometry -------------------------------------------------------

        def view(self) -> View:
            """The current view (frozen scale and image position while dragging)."""
            s = self.state
            if self._drag is not None:
                v = self._drag[4]
                return view_at(v.scale, v.ix, v.iy, s.image_w, s.image_h, s.margins)
            return fit_view(self.get_allocated_width(), self.get_allocated_height(), s.image_w, s.image_h, s.margins)

        # drag (also used by the test hooks) ----------------------------

        def begin_drag(self, handle: str, x: float, y: float) -> None:
            self._drag = (handle, x, y, self.state.margins, self.view())
            self.hover = handle

        def update_drag(self, x: float, y: float) -> None:
            if self._drag is None:
                return
            handle, x0, y0, start, view = self._drag
            self.state.set_margins(drag_margins(start, handle, x - x0, y - y0, view.scale, self.state.limit))
            self.queue_draw()

        def end_drag(self) -> None:
            self._drag = None
            self.queue_draw()

        def drag_handle_by(self, handle: str, dx: float, dy: float) -> None:
            """Test hook: drag ``handle`` by (dx, dy) screen pixels, as a user would."""
            points = handle_points(self.view())
            if handle not in points:
                return
            x, y = points[handle]
            self.begin_drag(handle, x, y)
            self.update_drag(x + dx, y + dy)
            self.end_drag()

        # events ---------------------------------------------------------

        def _set_cursor(self, handle: str | None) -> None:
            window = self.get_window()
            if window is None:
                return
            cursor = Gdk.Cursor.new_from_name(self.get_display(), CURSORS[handle]) if handle else None
            window.set_cursor(cursor)

        def _press(self, _w: Gtk.Widget, event: Gdk.EventButton) -> bool:
            if event.button != 1:
                return False
            handle = hit_test(self.view(), event.x, event.y)
            if handle is None:
                return False
            self.begin_drag(handle, event.x, event.y)
            return True

        def _release(self, _w: Gtk.Widget, event: Gdk.EventButton) -> bool:
            if event.button != 1 or self._drag is None:
                return False
            self.end_drag()
            self.hover = hit_test(self.view(), event.x, event.y)
            self._set_cursor(self.hover)
            return True

        def _motion(self, _w: Gtk.Widget, event: Gdk.EventMotion) -> bool:
            if self._drag is not None:
                self.update_drag(event.x, event.y)
                return True
            handle = hit_test(self.view(), event.x, event.y)
            if handle != self.hover:
                self.hover = handle
                self._set_cursor(handle)
                self.queue_draw()
            return False

        def _leave(self, *_: object) -> bool:
            if self._drag is None and self.hover is not None:
                self.hover = None
                self._set_cursor(None)
                self.queue_draw()
            return False

        # drawing --------------------------------------------------------

        def _draw(self, _w: Gtk.Widget, cr: object) -> bool:
            v = self.view()
            s = self.state
            m = s.margins
            # new area: shaded frame
            cr.set_source_rgba(0.18, 0.44, 0.77, 0.28)
            cr.rectangle(v.fx, v.fy, v.fw, v.fh)
            cr.fill()
            # the image
            if self.thumbnail is not None:
                cr.save()
                cr.translate(v.ix, v.iy)
                cr.scale(v.iw / max(1, self.thumbnail.get_width()), v.ih / max(1, self.thumbnail.get_height()))
                Gdk.cairo_set_source_pixbuf(cr, self.thumbnail, 0, 0)
                cr.paint()
                cr.restore()
            else:
                cr.set_source_rgb(0.42, 0.42, 0.42)
                cr.rectangle(v.ix, v.iy, v.iw, v.ih)
                cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.55)
            cr.set_line_width(1)
            cr.rectangle(v.ix + 0.5, v.iy + 0.5, v.iw - 1, v.ih - 1)
            cr.stroke()
            # amounts on the new area
            cr.set_font_size(12)
            labels = {
                "left": (v.fx, v.iy, v.ix - v.fx, v.ih, m.left),
                "right": (v.ix + v.iw, v.iy, v.fx + v.fw - v.ix - v.iw, v.ih, m.right),
                "top": (v.ix, v.fy, v.iw, v.iy - v.fy, m.top),
                "bottom": (v.ix, v.iy + v.ih, v.iw, v.fy + v.fh - v.iy - v.ih, m.bottom),
            }
            for x, y, w, h, amount in labels.values():
                if amount <= 0:
                    continue
                text = f"+{amount}"
                ext = cr.text_extents(text)
                if ext.width + 6 > w or ext.height + 6 > h:
                    continue
                cr.set_source_rgba(1, 1, 1, 0.9)
                cr.move_to(x + (w - ext.width) / 2 - ext.x_bearing, y + (h - ext.height) / 2 - ext.y_bearing)
                cr.show_text(text)
            # dashed frame of the new canvas
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.set_line_width(1.5)
            cr.set_dash([6, 4])
            cr.rectangle(v.fx + 0.75, v.fy + 0.75, v.fw - 1.5, v.fh - 1.5)
            cr.stroke()
            cr.set_dash([])
            # handles
            half = HANDLE_PX / 2
            for name, (hx, hy) in handle_points(v).items():
                active = name == self.hover
                cr.rectangle(hx - half, hy - half, HANDLE_PX, HANDLE_PX)
                if active:
                    cr.set_source_rgb(0.23, 0.50, 0.84)
                else:
                    cr.set_source_rgb(1, 1, 1)
                cr.fill_preserve()
                cr.set_source_rgb(0.1, 0.1, 0.1)
                cr.set_line_width(1)
                cr.stroke()
            return False

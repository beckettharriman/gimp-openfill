# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Variations picker: after several variations land as layers in a group, a
small window shows one thumbnail per variation. Clicking a thumbnail shows
that variation in the image and hides the others; "Keep all" leaves the
group as it is, "Discard" removes it.

GTK only. The caller passes callbacks that do the GIMP work (see
``gimp-stable-boy.py``: ``_pick_variation``), so this module stays free of
GIMP calls and is driven entirely by the result layers.
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

from .dialogs import style  # noqa: E402

THUMB = 160


class VariationPicker(Gtk.Window):
    """``thumbnails``: list of (name, GdkPixbuf or None).

    ``on_show(index)`` is called when a thumbnail is clicked (also once for
    the first one); ``on_keep_all()`` and ``on_discard()`` when those
    buttons are pressed. "Keep selected" and closing the window keep the
    current choice. ``on_closed()`` runs once at the end in every case.
    """

    def __init__(self, title: str, thumbnails: list[tuple[str, GdkPixbuf.Pixbuf | None]],
                 on_show: Callable[[int], None], on_keep_all: Callable[[], None],
                 on_discard: Callable[[], None], on_closed: Callable[[], None] | None = None) -> None:
        super().__init__(title=f"Choose a variation - {title}")
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_border_width(12)
        self._on_show = on_show
        self._on_keep_all = on_keep_all
        self._on_discard = on_discard
        self._on_closed = on_closed
        self._done = False
        self.choice = 0
        self.outcome = "keep"

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(box)
        head = Gtk.Label(xalign=0)
        head.set_markup(f"<b>{len(thumbnails)} variations are ready.</b> Click one to see it in the image.")
        box.pack_start(head, False, False, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.buttons: list[Gtk.ToggleButton] = []
        group = None
        for index, (name, pixbuf) in enumerate(thumbnails):
            button = Gtk.RadioButton.new_from_widget(group)
            group = group or button
            button.set_mode(False)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            image = Gtk.Image()
            if pixbuf is not None:
                image.set_from_pixbuf(pixbuf)
            else:
                image.set_size_request(THUMB, THUMB)
            inner.pack_start(image, False, False, 0)
            inner.pack_start(Gtk.Label(label=f"Variation {index + 1}"), False, False, 0)
            button.add(inner)
            button.set_tooltip_text(name)
            button.connect("toggled", self._toggled, index)
            row.pack_start(button, False, False, 0)
            self.buttons.append(button)
        box.pack_start(row, False, False, 0)

        hint = Gtk.Label(xalign=0)
        hint.set_markup("<small>Keep selected hides the other variations (they stay in the layer group, "
                        "so you can change your mind later). Discard removes all of them.</small>")
        hint.set_line_wrap(True)
        hint.set_max_width_chars(60)
        hint.get_style_context().add_class("dim-label")
        box.pack_start(hint, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        discard = Gtk.Button.new_with_mnemonic("_Discard")
        style(discard, "danger")
        discard.connect("clicked", self._discard)
        actions.pack_start(discard, False, False, 0)
        keep = Gtk.Button.new_with_mnemonic("_Keep selected")
        style(keep, "primary")
        keep.set_can_default(True)
        keep.connect("clicked", lambda *_: self.finish("keep"))
        actions.pack_end(keep, False, False, 0)
        keep_all = Gtk.Button.new_with_mnemonic("Keep _all")
        keep_all.connect("clicked", self._keep_all)
        actions.pack_end(keep_all, False, False, 0)
        box.pack_start(actions, False, False, 0)

        self.connect("delete-event", lambda *_: (self.finish("keep"), True)[1])
        self.connect("key-press-event", self._key)
        self.show_all()
        keep.grab_default()
        if self.buttons:
            self.buttons[0].grab_focus()

    def _toggled(self, button, index: int) -> None:
        if button.get_active() and not self._done:
            self.choice = index
            self._on_show(index)

    def _key(self, _w, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.finish("keep")
            return True
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.finish("keep")
            return True
        if Gdk.KEY_1 <= event.keyval <= Gdk.KEY_9:
            index = event.keyval - Gdk.KEY_1
            if index < len(self.buttons):
                self.buttons[index].set_active(True)
                return True
        return False

    def _keep_all(self, *_):
        self._on_keep_all()
        self.finish("keep_all")

    def _discard(self, *_):
        self._on_discard()
        self.finish("discard")

    def finish(self, outcome: str) -> None:
        if self._done:
            return
        self._done = True
        self.outcome = outcome
        self.destroy()
        if self._on_closed:
            self._on_closed()


def _play_step(picker: VariationPicker, step: str) -> bool:
    if picker._done:
        return False
    if step.isdigit() and 0 < int(step) <= len(picker.buttons):
        picker.buttons[int(step) - 1].clicked()
    elif step == "keep_all":
        picker._keep_all()
    elif step == "discard":
        picker._discard()
    elif step == "keep":
        picker.finish("keep")
    return False


def scaled(pixbuf: GdkPixbuf.Pixbuf | None, size: int = THUMB) -> GdkPixbuf.Pixbuf | None:
    if pixbuf is None:
        return None
    w, h = pixbuf.get_width(), pixbuf.get_height()
    if max(w, h) <= size:
        return pixbuf
    k = size / max(w, h)
    return pixbuf.scale_simple(max(1, int(w * k)), max(1, int(h * k)), GdkPixbuf.InterpType.BILINEAR)


def run_picker(title: str, thumbnails, on_show, on_keep_all, on_discard, autoclose_seconds: float = 0,
               test_steps: list[str] | None = None) -> str:
    """Show the picker and block (in a nested main loop) until it closes; returns the outcome.

    ``test_steps`` (test hook) is played back one step per second: a
    variation number ("1", "2", ...) clicks that thumbnail; "keep",
    "keep_all" and "discard" press the buttons.
    """
    picker = VariationPicker(title, thumbnails, on_show, on_keep_all, on_discard,
                             on_closed=lambda: Gtk.main_quit() if Gtk.main_level() > 0 else None)
    if autoclose_seconds and autoclose_seconds > 0:
        GLib.timeout_add(int(autoclose_seconds * 1000), lambda: (picker.finish("keep"), False)[1])
    for index, step in enumerate(test_steps or []):
        GLib.timeout_add(1000 * (index + 1), _play_step, picker, str(step))
    Gtk.main()
    return picker.outcome

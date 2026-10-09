# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK 3 dialogs: Generative Fill, Generative Expand, Text to Image and the
Settings window.

The dialogs know nothing about GIMP procedures. The entry point
(``gimp-stable-boy.py``) reads the procedure config into a plain ``values``
dict, runs a dialog, and writes the returned dict back into the
``Gimp.ProcedureConfig``, so NONINTERACTIVE calls keep the exact same
arguments. All texts live in :mod:`ui_text` (unit tested).
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import ui_text  # noqa: E402

OK = Gtk.ResponseType.OK
CANCEL = Gtk.ResponseType.CANCEL

# GIMP's theme draws "suggested-action" like any other button, so the one
# obvious button of each window gets its own colour.
_CSS = b"""
button.sb-primary, button.sb-primary label { background-image: none; background-color: #2d6fc4;
    color: #ffffff; font-weight: bold; }
button.sb-primary { border-color: #2a62ad; }
button.sb-primary:hover { background-color: #3a7fd6; }
button.sb-primary:disabled, button.sb-primary:disabled label { background-color: rgba(45, 111, 196, 0.35);
    color: rgba(255, 255, 255, 0.6); }
button.sb-danger, button.sb-danger label { background-image: none; background-color: #b13c3c;
    color: #ffffff; font-weight: bold; }
button.sb-danger { border-color: #9a3333; }
button.sb-danger:hover { background-color: #c44a4a; }
button.sb-danger:disabled, button.sb-danger:disabled label { background-color: rgba(177, 60, 60, 0.35);
    color: rgba(255, 255, 255, 0.6); }
label.sb-warning { color: #e8a33c; }
.sb-canvas { border: 1px dashed rgba(160, 160, 160, 0.8); background-color: rgba(255, 255, 255, 0.04); }
notebook tab { padding: 6px 14px; }
"""
_css_installed = False


def install_css() -> None:
    """Install the button colours for the default screen once per process."""
    global _css_installed
    if _css_installed:
        return
    screen = Gdk.Screen.get_default()
    if screen is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_installed = True


def style(widget: Gtk.Widget, kind: str | None) -> Gtk.Widget:
    """kind: "primary", "danger" or None (plain)."""
    install_css()
    ctx = widget.get_style_context()
    for cls in ("sb-primary", "sb-danger"):
        ctx.remove_class(cls)
    if kind:
        ctx.add_class(f"sb-{kind}")
    return widget


# ------------------------------------------------------------ helpers -----


def _dim(text: str, small: bool = True, wrap: bool = True, markup: bool = False) -> Gtk.Label:
    label = Gtk.Label(xalign=0)
    body = text if markup else GLib.markup_escape_text(text)
    label.set_markup(f"<small>{body}</small>" if small else body)
    label.get_style_context().add_class("dim-label")
    if wrap:
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(70)
    return label


def _right(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=1)
    label.set_valign(Gtk.Align.CENTER)
    return label


def _spin(lower: float, upper: float, value: float, step: float = 1, digits: int = 0) -> Gtk.SpinButton:
    adj = Gtk.Adjustment(value=value, lower=lower, upper=upper, step_increment=step, page_increment=step * 10)
    spin = Gtk.SpinButton(adjustment=adj, digits=digits)
    spin.set_numeric(True)
    spin.set_value(value)
    return spin


def _gimp_window_rect() -> tuple[int, int, int, int] | None:
    """Screen rectangle of the GIMP image window this procedure runs for
    (Windows only, through the native handle GIMP reports)."""
    try:
        gi.require_version("Gimp", "3.0")
        from gi.repository import Gimp

        from .progress_window import _window_rect_from_handle

        data = Gimp.progress_get_window_handle()
        return _window_rect_from_handle(data.get_data() if data is not None else None)
    except Exception:  # noqa: BLE001 - placement is best effort
        return None


def set_transient(window: Gtk.Window) -> None:
    """Keep plug-in windows above the GIMP image window and centre them on it
    (best effort; falls back to the centre of the screen). Call before the
    window is shown."""
    window.set_position(Gtk.WindowPosition.CENTER)
    try:
        gi.require_version("GimpUi", "3.0")
        from gi.repository import GimpUi

        GimpUi.window_set_transient(window)
    except Exception:  # noqa: BLE001 - outside GIMP (or older API): no parent
        pass
    rect = _gimp_window_rect()
    if rect is None:
        return
    scale = max(1, window.get_scale_factor())
    x, y, w, h = (v // scale for v in rect)
    _min, natural = window.get_preferred_size()
    width = max(natural.width, window.get_default_size()[0])
    height = max(natural.height, window.get_default_size()[1])
    window.set_position(Gtk.WindowPosition.NONE)
    window.move(max(0, x + (w - width) // 2), max(0, y + (h - height) // 3))


def timeout_while_alive(widget: Gtk.Widget, ms: int, fn: Callable[[], object]) -> None:
    """Run ``fn`` once after ``ms`` unless ``widget`` is destroyed first.

    Used by the test hooks: a timer that outlives its dialog would otherwise
    fire into a later window of the same plug-in run.
    """
    state = {"id": 0}

    def fire() -> bool:
        state["id"] = 0
        fn()
        return False

    def drop(*_: object) -> None:
        if state["id"]:
            GLib.source_remove(state["id"])
            state["id"] = 0

    state["id"] = GLib.timeout_add(ms, fire)
    widget.connect("destroy", drop)


def autoclose(dialog: Gtk.Dialog, seconds: float, response: Gtk.ResponseType = CANCEL) -> None:
    """Test hook: answer the dialog after ``seconds`` (0 = never)."""
    if seconds and seconds > 0:
        timeout_while_alive(dialog, int(seconds * 1000), lambda: dialog.response(response))


def send_key(widget: Gtk.Widget, keyval: int, state: int = 0) -> None:
    """Test hook: deliver a real key press to ``widget``'s toplevel through
    GTK's event processing (as if typed), so default handling (Escape closes
    a dialog, Enter in the prompt generates) is exercised."""
    toplevel = widget.get_toplevel()
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.key.window = toplevel.get_window()
    event.key.send_event = 1
    event.key.time = Gdk.CURRENT_TIME
    event.key.keyval = keyval
    event.key.state = Gdk.ModifierType(state)
    keymap = Gdk.Keymap.get_for_display(toplevel.get_display())
    ok, keys = keymap.get_entries_for_keyval(keyval)
    if ok and keys:
        event.key.hardware_keycode = keys[0].keycode
    seat = toplevel.get_display().get_default_seat()
    if seat is not None and seat.get_keyboard() is not None:
        event.set_device(seat.get_keyboard())
    Gtk.main_do_event(event)


def scripted_input(
    dialog: Gtk.Dialog, prompt: PromptBox | None, text: str | None, key: str | None, delay: float = 1.5
) -> None:
    """Test hook: after ``delay`` s type ``text`` into the prompt and press ``key``."""
    if not text and not key:
        return

    def act() -> None:
        if text is not None and prompt is not None:
            prompt.buffer.set_text(text)
            prompt.view.grab_focus()
        if key:
            send_key(prompt.view if prompt is not None else dialog, Gdk.keyval_from_name(key))

    timeout_while_alive(dialog, int(delay * 1000), act)


class PromptBox(Gtk.Box):
    """Large multi-line prompt with a placeholder and a Recent prompts menu.

    Enter generates (the dialog's default response); Shift+Enter inserts a
    new line.
    """

    def __init__(
        self,
        placeholder: str,
        text: str,
        history: list[str],
        on_activate: Callable[[], None],
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._on_activate = on_activate
        self._on_changed = on_changed
        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_accepts_tab(False)
        for side in ("left", "right", "top", "bottom"):
            getattr(self.view, f"set_{side}_margin")(8)
        self.buffer = self.view.get_buffer()
        self.buffer.set_text(text or "")
        self.view.connect("key-press-event", self._key)
        self.buffer.connect("changed", self._changed)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_min_content_height(112)
        scroller.set_hexpand(True)
        scroller.add(self.view)
        overlay = Gtk.Overlay()
        overlay.add(scroller)
        self.placeholder = Gtk.Label(label=placeholder, xalign=0, yalign=0)
        self.placeholder.get_style_context().add_class("dim-label")
        self.placeholder.set_halign(Gtk.Align.START)
        self.placeholder.set_valign(Gtk.Align.START)
        self.placeholder.set_margin_start(10)
        self.placeholder.set_margin_top(9)
        self.placeholder.set_no_show_all(True)  # visibility follows the buffer, not show_all()
        overlay.add_overlay(self.placeholder)
        overlay.set_overlay_pass_through(self.placeholder, True)
        self.pack_start(overlay, True, True, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.recent = Gtk.MenuButton(label="Recent prompts")
        menu = Gtk.Menu()
        for prompt in history:
            item = Gtk.MenuItem(label=ui_text.history_label(prompt))
            item.set_tooltip_text(prompt)
            item.connect("activate", lambda _w, p=prompt: self.set_text(p))
            menu.append(item)
        menu.show_all()
        self.recent.set_popup(menu)
        self.recent.set_sensitive(bool(history))
        if not history:
            self.recent.set_tooltip_text(
                f"Prompts you generate with are remembered here (last {ui_text.HISTORY_LIMIT})."
            )
        row.pack_start(self.recent, False, False, 0)
        row.pack_end(_dim("Enter generates, Shift+Enter starts a new line", wrap=False), False, False, 0)
        self.pack_start(row, False, False, 0)
        self._changed()

    def _key(self, _view: Gtk.TextView, event: Gdk.EventKey) -> bool:
        enter = event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter)
        if enter and not event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            self._on_activate()
            return True
        return False

    def _changed(self, *_: object) -> None:
        self.placeholder.set_visible(self.buffer.get_char_count() == 0)
        if self._on_changed:
            self._on_changed()

    def get_text(self) -> str:
        """The prompt as typed (not stripped)."""
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, False)

    def set_text(self, text: str) -> None:
        """Replace the prompt, select it and focus the text view."""
        self.buffer.set_text(text)
        self.select_all()
        self.view.grab_focus()

    def select_all(self) -> None:
        """Select the whole prompt, so typing replaces it."""
        start, end = self.buffer.get_bounds()
        self.buffer.select_range(start, end)


# --------------------------------------------------- generation dialogs ---


class GenerationDialog(Gtk.Dialog):
    """One dialog class for Fill, Expand and Text to Image.

    ``values`` holds the procedure arguments (prompt, negative, variations,
    seed, model and the per-kind ones); :meth:`collect` returns the same
    keys with the user's choices.
    """

    TITLES = {"fill": "Generative Fill", "expand": "Generative Expand", "txt2img": "Text to Image"}

    def __init__(
        self,
        kind: str,
        values: dict,
        history: list[str],
        models: list[tuple[str, str]],
        image_size: tuple[int, int] | None = None,
        selection_size: tuple[int, int] | None = None,
        default_size: tuple[int, int] = (768, 512),
        active_prompt_free: bool = False,
        active_name: str = "",
        show_advanced: bool = False,
    ) -> None:
        super().__init__(title=self.TITLES[kind], modal=True)
        self.kind = kind
        self.values = dict(values)
        self.image_size = image_size
        self.selection_size = selection_size
        self.default_size = default_size
        self.active_prompt_free = active_prompt_free
        self.active_name = active_name
        self.set_default_size(640, -1)
        self.set_border_width(6)
        self.add_button("_Cancel", CANCEL)
        self.generate = self.add_button("_Generate", OK)
        style(self.generate, "primary")
        self.generate.set_size_request(120, -1)
        self.generate.set_can_default(True)
        self.set_default_response(OK)
        self.generate.grab_default()

        area = self.get_content_area()
        area.set_spacing(10)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.set_border_width(8)
        area.pack_start(body, True, True, 0)

        self.remove_radio: Gtk.RadioButton | None = None
        if kind == "fill":
            body.pack_start(self._mode_switch(bool(values.get("remove"))), False, False, 0)

        placeholder = {
            "fill": ui_text.FILL_PLACEHOLDER,
            "expand": ui_text.EXPAND_PLACEHOLDER,
            "txt2img": ui_text.TXT2IMG_PLACEHOLDER,
        }[kind]
        self.prompt = PromptBox(
            placeholder,
            values.get("prompt", ""),
            history,
            on_activate=lambda: self.response(OK),
            on_changed=self._update_status,
        )
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.prompt, "prompt")
        removal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        removal.set_valign(Gtk.Align.CENTER)
        big = Gtk.Label(xalign=0)
        big.set_markup(f"<big>{GLib.markup_escape_text(ui_text.REMOVE_EXPLANATION)}</big>")
        big.set_line_wrap(True)
        big.set_max_width_chars(60)
        removal.pack_start(big, False, False, 0)
        removal.pack_start(
            _dim(
                "Works best when the selection covers the whole object with a little margin. "
                "An installed LaMa or MAT removal model is used automatically when there is one."
            ),
            False,
            False,
            0,
        )
        self.stack.add_named(removal, "remove")
        body.pack_start(self.stack, True, True, 0)

        if kind == "expand":
            body.pack_start(self._margins(), False, False, 0)
        elif kind == "txt2img":
            body.pack_start(self._size_and_target(), False, False, 0)

        self.advanced = self._advanced(models)
        self.advanced.set_expanded(show_advanced)
        body.pack_start(self.advanced, False, False, 0)

        self.status = _dim("", small=False)
        body.pack_start(self.status, False, False, 0)
        self.warning = Gtk.Label(xalign=0)
        self.warning.set_line_wrap(True)
        self.warning.set_max_width_chars(70)
        self.warning.get_style_context().add_class("sb-warning")
        self.warning.set_no_show_all(True)
        body.pack_start(self.warning, False, False, 0)
        if kind == "fill":
            body.pack_start(_dim(ui_text.SHORTCUT_HINT), False, False, 0)

        area.show_all()  # the window itself is shown by run(), after placement
        if self.remove_radio is not None and self.remove_radio.get_active():
            self.stack.set_visible_child_name("remove")
        else:
            self.stack.set_visible_child_name("prompt")
        self._update_status()
        self.prompt.view.grab_focus()
        self.prompt.select_all()

    # sections ------------------------------------------------------------

    def _mode_switch(self, remove: bool) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.get_style_context().add_class("linked")
        box.set_halign(Gtk.Align.START)
        fill = Gtk.RadioButton.new_with_mnemonic(None, "_Fill with a prompt")
        rem = Gtk.RadioButton.new_with_mnemonic_from_widget(fill, "_Remove object")
        for button in (fill, rem):
            button.set_mode(False)  # draw as toggle buttons
            button.set_size_request(170, 34)
            box.pack_start(button, False, False, 0)
        rem.set_active(remove)
        fill.set_active(not remove)
        rem.connect("toggled", self._mode_changed)
        self.remove_radio = rem
        return box

    def _mode_changed(self, button: Gtk.RadioButton) -> None:
        self.stack.set_visible_child_name("remove" if button.get_active() else "prompt")
        if not button.get_active():
            self.prompt.view.grab_focus()
        self._update_status()

    def _margins(self) -> Gtk.Widget:
        frame = Gtk.Frame(label="Add to the canvas (pixels)")
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        grid.set_border_width(8)
        grid.set_halign(Gtk.Align.CENTER)
        self.margin_spins = {}
        positions = {"top": (2, 0), "left": (0, 1), "right": (4, 1), "bottom": (2, 2)}
        for side, (col, row) in positions.items():
            spin = _spin(0, 4096, int(self.values.get(side, 0)), 32)
            spin.set_width_chars(6)
            spin.connect("value-changed", lambda *_: self._update_status())
            self.margin_spins[side] = spin
            label = Gtk.Label(label=side.capitalize())
            if side in ("left", "right"):
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                box.pack_start(label, False, False, 0)
                box.pack_start(spin, False, False, 0)
                grid.attach(box, col, row, 1, 1)
            else:
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                box.pack_start(label, False, False, 0)
                box.pack_start(spin, False, False, 0)
                box.set_halign(Gtk.Align.CENTER)
                grid.attach(box, col, row, 1, 1)
        canvas = Gtk.Label(label="your image")
        canvas.get_style_context().add_class("sb-canvas")
        canvas.get_style_context().add_class("dim-label")
        canvas.set_size_request(170, 70)
        grid.attach(canvas, 1, 1, 3, 1)
        presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        presets.set_halign(Gtk.Align.CENTER)
        presets.pack_start(_dim("Quick:", wrap=False), False, False, 0)
        for label, sides in (
            ("Wider", {"left": 256, "right": 256, "top": 0, "bottom": 0}),
            ("Taller", {"left": 0, "right": 0, "top": 256, "bottom": 256}),
            ("All sides", {"left": 128, "right": 128, "top": 128, "bottom": 128}),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _b, s=sides: [self.margin_spins[k].set_value(v) for k, v in s.items()])
            presets.pack_start(button, False, False, 0)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_border_width(4)
        outer.pack_start(grid, False, False, 0)
        outer.pack_start(presets, False, False, 0)
        frame.add(outer)
        return frame

    def _size_and_target(self) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        width, height = int(self.values.get("width", 0)), int(self.values.get("height", 0))
        self.auto_size = Gtk.CheckButton(label="Automatic size (the selection, or the default from Settings)")
        self.auto_size.set_active(width <= 0 or height <= 0)
        grid.attach(_right("Size"), 0, 0, 1, 1)
        grid.attach(self.auto_size, 1, 0, 3, 1)
        self.width_spin = _spin(64, 4096, width if width > 0 else self.default_size[0], 64)
        self.height_spin = _spin(64, 4096, height if height > 0 else self.default_size[1], 64)
        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        size_box.pack_start(self.width_spin, False, False, 0)
        size_box.pack_start(Gtk.Label(label="x"), False, False, 0)
        size_box.pack_start(self.height_spin, False, False, 0)
        size_box.pack_start(Gtk.Label(label="px"), False, False, 0)
        grid.attach(size_box, 1, 1, 3, 1)
        for w in (self.auto_size, self.width_spin, self.height_spin):
            w.connect(
                "toggled" if isinstance(w, Gtk.CheckButton) else "value-changed", lambda *_: self._update_status()
            )
        grid.attach(_right("Result as"), 0, 2, 1, 1)
        self.target_layer = Gtk.RadioButton.new_with_label(None, "New layer in this image")
        self.target_image = Gtk.RadioButton.new_with_label_from_widget(self.target_layer, "New image")
        target = self.values.get("target", "layer")
        if self.image_size is None:
            target = "image"
            self.target_layer.set_sensitive(False)
        self.target_image.set_active(target == "image")
        self.target_layer.set_active(target != "image")
        self.target_layer.connect("toggled", lambda *_: self._update_status())
        grid.attach(self.target_layer, 1, 2, 1, 1)
        grid.attach(self.target_image, 2, 2, 1, 1)
        return grid

    def _advanced(self, models: list[tuple[str, str]]) -> Gtk.Widget:
        expander = Gtk.Expander(label="Advanced")
        expander.set_expanded(False)
        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        grid.set_border_width(8)
        row = 0

        def add(label: str, widget: Gtk.Widget, hint: str = "", expand: bool = True) -> None:
            nonlocal row
            grid.attach(_right(label), 0, row, 1, 1)
            widget.set_hexpand(expand)
            if not expand:
                widget.set_halign(Gtk.Align.START)
            grid.attach(widget, 1, row, 1, 1)
            row += 1
            if hint:
                grid.attach(_dim(hint), 1, row, 1, 1)
                row += 1

        self.model_combo = Gtk.ComboBoxText()
        for cell in self.model_combo.get_cells():
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        self.model_combo.set_size_request(360, -1)
        for nick, label in models:
            self.model_combo.append(nick, label)
        current = self.values.get("model") or "active"
        if not self.model_combo.set_active_id(current):
            self.model_combo.append(current, current)
            self.model_combo.set_active_id(current)
        self.model_combo.connect("changed", lambda *_: self._update_status())
        add("Model", self.model_combo, "The first entry is the active model from Settings > Models.")

        self.negative = Gtk.Entry()
        self.negative.set_text(self.values.get("negative", ""))
        self.negative.set_activates_default(True)
        add("Avoid", self.negative, "Things that should not appear, separated by commas.")

        self.variations = _spin(1, 8, int(self.values.get("variations", 1)))
        self.variations.set_activates_default(True)
        hint = (
            "Each result becomes a layer; with more than one you pick your favourite afterwards."
            if self.kind != "txt2img"
            else "Each result becomes a layer."
        )
        add("Variations", self.variations, hint, expand=False)

        if self.kind == "fill":
            self.strength = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05)
            self.strength.set_value(float(self.values.get("strength", 1.0)))
            self.strength.set_digits(2)
            self.strength.set_value_pos(Gtk.PositionType.RIGHT)
            add(
                "Change amount",
                self.strength,
                "1.0 replaces the selection completely; lower values keep more of what is there now.",
            )

        seed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        seed = int(self.values.get("seed", -1))
        self.random_seed = Gtk.CheckButton(label="Random")
        self.random_seed.set_active(seed < 0)
        self.seed = _spin(0, 2**31 - 1, max(0, seed))
        self.seed.set_activates_default(True)
        self.seed.set_sensitive(seed >= 0)
        self.random_seed.connect("toggled", lambda b: self.seed.set_sensitive(not b.get_active()))
        seed_box.pack_start(self.random_seed, False, False, 0)
        seed_box.pack_start(self.seed, False, False, 0)
        add("Seed", seed_box, "Use the same number again to repeat a result.", expand=False)
        expander.add(grid)
        return expander

    # state ---------------------------------------------------------------

    @property
    def removing(self) -> bool:
        """True when Remove object is chosen (Fill only)."""
        return bool(self.remove_radio and self.remove_radio.get_active())

    def _update_status(self) -> None:
        if not hasattr(self, "status"):
            return
        parts = []
        warning = ""
        if self.kind == "fill":
            parts.append(ui_text.selection_status(self.selection_size, self.image_size))
            model = self.model_combo.get_active_id() if hasattr(self, "model_combo") else "active"
            if not self.removing and model == "active" and self.active_prompt_free:
                warning = ui_text.prompt_free_warning(self.active_name)
        elif self.kind == "expand" and hasattr(self, "margin_spins"):
            s = {k: int(v.get_value()) for k, v in self.margin_spins.items()}
            parts.append(ui_text.expand_status(self.image_size, s["left"], s["top"], s["right"], s["bottom"]))
        elif self.kind == "txt2img" and hasattr(self, "auto_size"):
            auto = self.auto_size.get_active()
            self.width_spin.set_sensitive(not auto)
            self.height_spin.set_sensitive(not auto)
            w = 0 if auto else int(self.width_spin.get_value())
            h = 0 if auto else int(self.height_spin.get_value())
            target = "image" if self.target_image.get_active() else "layer"
            parts.append(ui_text.txt2img_status(w, h, self.selection_size, self.default_size, target))
        self.status.set_text(" ".join(p for p in parts if p))
        if hasattr(self, "warning"):
            self.warning.set_text(warning)
            self.warning.set_visible(bool(warning))

    def collect(self) -> dict:
        """The procedure arguments as chosen, typed exactly as the ProcedureConfig expects."""
        out = {
            "prompt": self.prompt.get_text().strip(),
            "negative": self.negative.get_text().strip(),
            "variations": int(self.variations.get_value()),
            "seed": -1 if self.random_seed.get_active() else int(self.seed.get_value()),
            "model": self.model_combo.get_active_id() or "active",
        }
        if self.kind == "fill":
            out["strength"] = round(float(self.strength.get_value()), 2)
            out["remove"] = self.removing
        elif self.kind == "expand":
            out.update({k: int(v.get_value()) for k, v in self.margin_spins.items()})
        elif self.kind == "txt2img":
            auto = self.auto_size.get_active()
            out["width"] = 0 if auto else int(self.width_spin.get_value())
            out["height"] = 0 if auto else int(self.height_spin.get_value())
            out["target"] = "image" if self.target_image.get_active() else "layer"
        return out


def run_generation_dialog(
    kind: str,
    values: dict,
    history: list[str],
    models: list[tuple[str, str]],
    autoclose_seconds: float = 0,
    test_text: str | None = None,
    test_key: str | None = None,
    test_open_recent: bool = False,
    test_click: str | None = None,
    **kwargs: object,
) -> dict | None:
    """Show the dialog; the collected values, or None when cancelled.

    ``test_click`` (test hook): "generate" clicks the Generate button 2 s after opening.
    """
    dialog = GenerationDialog(kind, values, history, models, **kwargs)
    set_transient(dialog)
    autoclose(dialog, autoclose_seconds)
    scripted_input(dialog, dialog.prompt, test_text, test_key)
    if test_click == "generate":
        timeout_while_alive(dialog, 2000, dialog.generate.clicked)
    if test_open_recent:
        timeout_while_alive(dialog, 1200, lambda: dialog.prompt.recent.set_active(True))
    try:
        while True:
            response = dialog.run()
            if response != OK:
                return None
            result = dialog.collect()
            if kind == "fill" and not result.get("remove") and not result["prompt"]:
                dialog.status.set_markup(
                    "<b>Type what should appear, or switch to Remove object to erase the selection.</b>"
                )
                dialog.prompt.view.grab_focus()
                continue
            return result
    finally:
        dialog.destroy()


# --------------------------------------------------------- settings -------

GENERAL_FIELDS = (
    ("comfy_dir", "AI backend folder", "Where ComfyUI (portable build) is installed."),
    (
        "autostart",
        "Start backend automatically",
        "Starts ComfyUI hidden in the background when you generate. Nothing else to open.",
    ),
    (
        "idle_timeout_minutes",
        "Idle timeout (minutes)",
        "Stops the backend after this many minutes without "
        "use, to free the graphics card memory. 0 keeps it running until GIMP closes.",
    ),
    (
        "progress_window",
        "Show the floating progress window",
        "Progress, a live preview and a Cancel button while generating.",
    ),
)
ADVANCED_FIELDS = (
    ("steps", "Steps", "More steps add detail but take longer. 20 to 30 is typical."),
    ("cfg", "Prompt strictness (CFG)", "How closely the result follows the prompt. 5 to 8 is typical."),
    (
        "sampler",
        "Sampler",
        "The method that turns noise into a picture. Keep the default unless a model page says otherwise.",
    ),
    ("scheduler", "Scheduler", 'How the noise is removed step by step. "karras" suits most models.'),
    (
        "grow_percent",
        "Repaint margin (% of selection)",
        "Lets the AI repaint a little around the selection so object edges disappear.",
    ),
    ("grow", "Repaint margin limit (px)", "Upper limit for that margin."),
    ("feather_percent", "Edge softness (% of selection)", "How softly the new layer blends into the image."),
    ("feather", "Edge softness limit (px)", "Upper limit for the soft edge."),
    (
        "prefill",
        "Hide old content before generating",
        "Helps the AI replace an object instead of copying it (needs the inpaint nodes).",
    ),
    ("max_side_sd15", "Working size for SD 1.5 (px)", "Larger is sharper but slower and needs more memory."),
    ("max_side_sdxl", "Working size for SDXL (px)", "Larger is sharper but slower and needs more memory."),
    ("txt2img_width", "Text to Image default width (px)", ""),
    ("txt2img_height", "Text to Image default height (px)", ""),
)
CONNECTION_FIELDS = (
    ("backend", "Backend", "ComfyUI is started and stopped for you. AUTOMATIC1111 must be started by you with --api."),
    ("url", "ComfyUI address", ""),
    ("a1111_url", "AUTOMATIC1111 address", ""),
    ("startup_timeout", "Startup time limit (s)", "How long to wait for the backend to start."),
    ("request_timeout", "Generation time limit (s)", "0 estimates a limit for each request."),
    ("extra_server_args", "Extra ComfyUI options", "For example --lowvram on cards with little memory."),
    ("quality", "Model for scripts asking 'fast' or 'quality'", "Only used by older scripts."),
    ("checkpoint", "SD 1.5 model file", "Used by the 'fast' choice of older scripts."),
    ("sdxl_checkpoint", "SDXL model file", "Used by the 'quality' choice of older scripts."),
    ("fooocus_patch", "Fooocus patch file", "Used by the 'quality' choice of older scripts."),
    ("debug", "Verbose log", "Writes more detail to stable-boy.log for bug reports."),
)


class SettingsDialog(Gtk.Dialog):
    """General (only what a user needs, the rest behind expanders) and Models.

    ``choices`` maps a key to [(nick, label)] for choice arguments;
    ``ranges`` maps numeric keys to (min, max). ``test_backend(values,
    report)`` runs in a worker thread and returns the result line; it may
    call ``report(text)`` with progress (thread safe here).
    """

    def __init__(
        self,
        values: dict,
        choices: dict,
        ranges: dict,
        models_panel_factory: Callable[[], Gtk.Widget] | None = None,
        test_backend: Callable[[dict, Callable[[str], None]], str] | None = None,
    ) -> None:
        super().__init__(title="Generative Fill Settings", modal=True)
        self.values = dict(values)
        self.choices = choices
        self.ranges = ranges
        self.widgets: dict[str, Gtk.Widget] = {}
        self.expanders: list[Gtk.Expander] = []
        self._test_backend = test_backend
        self._alive = True
        self.connect("destroy", self._on_destroy)
        self.set_default_size(900, 760)
        self.add_button("_Cancel", CANCEL)
        save = self.add_button("_Save", OK)
        style(save, "primary")
        save.set_size_request(110, -1)
        save.set_can_default(True)
        self.set_default_response(OK)

        self.notebook = Gtk.Notebook()
        self.get_content_area().pack_start(self.notebook, True, True, 0)
        self.notebook.append_page(self._general_page(), Gtk.Label(label="General"))
        self.panel = None
        if models_panel_factory is not None:
            try:
                self.panel = models_panel_factory()
                self.notebook.append_page(self.panel, Gtk.Label(label="Models"))
            except Exception as err:  # noqa: BLE001 - the General page must still work
                self.notebook.append_page(
                    _dim(ui_text.with_next_step(f"The Models tab could not be opened: {err}"), small=False),
                    Gtk.Label(label="Models"),
                )
        self.get_content_area().show_all()  # shown by run(), after placement

    # building ------------------------------------------------------------

    def _general_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(14)
        grid = self._grid(GENERAL_FIELDS)
        box.pack_start(grid, False, False, 0)

        test_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.test_button = Gtk.Button(label="Check backend")
        self.test_button.set_tooltip_text("Starts the backend if needed and checks that it answers.")
        self.test_button.connect("clicked", self._on_test)
        test_row.pack_start(self.test_button, False, False, 0)
        self.test_spinner = Gtk.Spinner()
        test_row.pack_start(self.test_spinner, False, False, 0)
        self.test_label = Gtk.Label(xalign=0)
        self.test_label.set_line_wrap(True)
        self.test_label.set_max_width_chars(80)
        self.test_label.set_selectable(True)
        self.test_label.set_text(
            "Press Check backend to see that the AI backend starts and answers. "
            "The first start can take about a minute."
        )
        test_row.pack_start(self.test_label, True, True, 0)
        box.pack_start(test_row, False, False, 0)

        for title, fields in (
            ("Advanced generation", ADVANCED_FIELDS),
            ("Connection and troubleshooting", CONNECTION_FIELDS),
        ):
            expander = Gtk.Expander(label=title)
            self.expanders.append(expander)
            inner = self._grid(fields)
            inner.set_margin_top(8)
            inner.set_margin_start(12)
            expander.add(inner)
            box.pack_start(expander, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(box)
        return scroller

    def _grid(self, fields: tuple[tuple[str, str, str], ...]) -> Gtk.Grid:
        grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        row = 0
        for key, label, hint in fields:
            if key not in self.values:
                continue
            widget = self._widget(key, label)
            if isinstance(widget, Gtk.CheckButton):
                grid.attach(widget, 1, row, 1, 1)
            else:
                grid.attach(_right(label), 0, row, 1, 1)
                grid.attach(widget, 1, row, 1, 1)
            row += 1
            if hint:
                hint_label = _dim(hint)
                hint_label.set_margin_bottom(6)
                grid.attach(hint_label, 1, row, 1, 1)
                row += 1
        return grid

    def _widget(self, key: str, label: str) -> Gtk.Widget:
        value = self.values[key]
        if isinstance(value, bool):
            widget = Gtk.CheckButton(label=label)
            widget.set_active(value)
            self.widgets[key] = widget
            return widget
        if isinstance(value, (int, float)):
            lower, upper = self.ranges.get(key, (0, 100000))
            digits = 1 if isinstance(value, float) else 0
            widget = _spin(lower, upper, value, 0.5 if digits else 1, digits)
            widget.set_halign(Gtk.Align.START)
            self.widgets[key] = widget
            return widget
        if key in self.choices:
            widget = Gtk.ComboBoxText()
            for nick, text in self.choices[key]:
                widget.append(nick, text)
            if not widget.set_active_id(str(value)):
                widget.append(str(value), str(value))
                widget.set_active_id(str(value))
            widget.set_halign(Gtk.Align.START)
            self.widgets[key] = widget
            return widget
        entry = Gtk.Entry()
        entry.set_text(str(value))
        entry.set_hexpand(True)
        entry.set_width_chars(48)
        self.widgets[key] = entry
        if key == "comfy_dir":
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.pack_start(entry, True, True, 0)
            browse = Gtk.Button(label="Browse...")
            browse.connect("clicked", self._browse, entry)
            box.pack_start(browse, False, False, 0)
            return box
        return entry

    def _browse(self, _button: Gtk.Button, entry: Gtk.Entry) -> None:
        chooser = Gtk.FileChooserDialog(
            title="Choose the ComfyUI folder", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_buttons("_Cancel", CANCEL, "_Select", OK)
        if entry.get_text():
            chooser.set_current_folder(entry.get_text())
        if chooser.run() == OK and chooser.get_filename():
            entry.set_text(chooser.get_filename())
        chooser.destroy()

    # values --------------------------------------------------------------

    def collect(self) -> dict:
        """The settings as shown, with the type of each original value (bool, int, float, str)."""
        out = {}
        for key, widget in self.widgets.items():
            old = self.values[key]
            if isinstance(widget, Gtk.CheckButton):
                out[key] = widget.get_active()
            elif isinstance(widget, Gtk.SpinButton):
                widget.update()
                out[key] = float(widget.get_value()) if isinstance(old, float) else int(widget.get_value())
            elif isinstance(widget, Gtk.ComboBoxText):
                out[key] = widget.get_active_id() or old
            else:
                out[key] = widget.get_text().strip()
        return out

    # test backend --------------------------------------------------------

    def _on_test(self, _button: Gtk.Button) -> None:
        if self._test_backend is None:
            return
        values = self.collect()
        self.test_button.set_sensitive(False)
        self.test_spinner.start()
        self.test_label.set_text("Testing... this may start the backend, which takes about a minute the first time.")

        def report(text: str) -> None:
            GLib.idle_add(lambda: (self._alive and self.test_label.set_text(text), False)[1])

        def worker() -> None:
            try:
                result = self._test_backend(values, report)
            except Exception as err:  # noqa: BLE001 - shown in the dialog
                result = ui_text.health_text(False, f"{type(err).__name__}: {err}", 0, False)
            GLib.idle_add(lambda: (self._test_done(result), False)[1])

        threading.Thread(target=worker, name="stable-boy-test-backend", daemon=True).start()

    def _test_done(self, text: str) -> None:
        if not self._alive:
            return
        self.test_spinner.stop()
        self.test_button.set_sensitive(True)
        self.test_label.set_text(text)

    def _on_destroy(self, *_: object) -> None:
        self._alive = False
        if self.panel is not None and hasattr(self.panel, "stop"):
            self.panel.stop()


def _play_settings_step(dialog: SettingsDialog, action: str, arg: object, out: str) -> None:
    """One Settings test step (see ``run_settings_dialog``)."""
    import json
    import time

    panel = dialog.panel
    if action == "check":
        dialog.test_button.clicked()
    elif action == "tab":
        dialog.notebook.set_current_page(int(arg))
    elif action == "activate" and panel is not None:
        widget = getattr(panel, "_widgets", {}).get(str(arg))
        if widget is not None:
            widget.primary.clicked()
    elif action == "dump" and out:
        rows = []
        index = 0
        while panel is not None and hasattr(panel, "list"):
            row = panel.list.get_row_at_index(index)
            if row is None:
                break
            index += 1
            data = getattr(row, "data", None) or {}
            rows.append(
                {
                    "id": data.get("id"),
                    "installed": data.get("installed"),
                    "active": data.get("active"),
                    "button": row.primary.get_label() if hasattr(row, "primary") else None,
                    "button_sensitive": row.primary.get_sensitive() if hasattr(row, "primary") else None,
                    "state": row.state.get_text() if hasattr(row, "state") else None,
                }
            )
        record = {"t": time.strftime("%H:%M:%S"), "tag": str(arg or ""), "test_label": dialog.test_label.get_text()}
        record["page"] = dialog.notebook.get_current_page()
        record["rows"] = rows
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


def run_settings_dialog(
    values: dict,
    choices: dict,
    ranges: dict,
    models_panel_factory: Callable[[], Gtk.Widget] | None = None,
    test_backend: Callable[[dict, Callable[[str], None]], str] | None = None,
    autoclose_seconds: float = 0,
    tab: str = "",
    show_advanced: bool = False,
    select_model: str = "",
    test_steps: list | None = None,
    test_out: str = "",
) -> dict | None:
    """Show the Settings dialog; the collected values, or None when cancelled.

    ``test_steps`` (test hook): ``[seconds, action, arg]`` entries played on
    timers: "check" presses Check backend, "tab" switches to page ``arg``,
    "activate" presses the primary button of model row ``arg`` and "dump"
    appends the backend label and the model rows (in list order) to the JSON
    lines file ``test_out``.
    """
    dialog = SettingsDialog(values, choices, ranges, models_panel_factory, test_backend)
    set_transient(dialog)
    for expander in dialog.expanders[:1] if show_advanced else []:
        expander.set_expanded(True)
    if tab == "models" and dialog.notebook.get_n_pages() > 1:
        dialog.notebook.set_current_page(1)
        if select_model and hasattr(dialog.panel, "select"):
            timeout_while_alive(dialog, 300, lambda: dialog.panel.select(select_model))
    for seconds, action, arg in test_steps or []:
        timeout_while_alive(
            dialog, int(float(seconds) * 1000), lambda a=action, v=arg: _play_settings_step(dialog, a, v, test_out)
        )
    autoclose(dialog, autoclose_seconds)
    try:
        response = dialog.run()
        return dialog.collect() if response == OK else None
    finally:
        dialog.destroy()

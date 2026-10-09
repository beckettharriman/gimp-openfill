# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Models tab: one row per catalog model, installed models first, and a
single primary button per row whose label follows the state
(Download -> Downloading 43% - Cancel -> Set active -> Active).

Pure GTK 3 (as shipped with GIMP). The panel polls the supervisor's task
status file once per second through a GLib timeout and never blocks the UI.
The Hugging Face token field appears only when it matters (a gated model is
selected, installed or downloading, or a token is already saved).
"""

from __future__ import annotations

import time
import webbrowser

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from . import catalog as cat  # noqa: E402
from . import ui_text  # noqa: E402
from .dialogs import style  # noqa: E402
from .backend import BackendError  # noqa: E402

TOKEN_PAGE = "https://huggingface.co/settings/tokens"


def _status_line(row: dict, current: dict, pending: list[str]) -> str:
    if current.get("model_id") == row["id"]:
        kind = current.get("type")
        if kind == "download":
            done, total = current.get("done") or 0, current.get("total") or 0
            speed = (current.get("speed") or 0.0) / 1_048_576
            return (f"Downloading {cat.human_size(done)} of {cat.human_size(total)}"
                    + (f", {speed:.1f} MB/s" if speed else ""))
        if kind == "install_nodes":
            return "Installing the extra ComfyUI nodes it needs..."
        if kind == "remove":
            return "Removing its files..."
    if row["id"] in pending:
        return "Waiting for the current download to finish."
    if row["active"]:
        return "Active: used by the Generative Fill dialogs."
    if row["installed"]:
        if row["missing_models"]:
            return f"Needs {', '.join(row['missing_models'])} as well."
        if row["missing_nodes"]:
            return "Downloaded. Needs extra ComfyUI nodes: press Install nodes."
        if row.get("seen_by_server") is False:
            return "Downloaded. Restart the backend (Filters > AI > Stop AI Backend) to use it."
        return "Downloaded."
    if row["partial"]:
        return "Partly downloaded. Press Resume download to continue."
    if row["status"] == "Needs token":
        return "Not downloaded. Needs a Hugging Face token (see below)."
    return "Not downloaded."


class ModelRow(Gtk.ListBoxRow):
    def __init__(self, panel: "ModelsPanel", row: dict, order: int) -> None:
        super().__init__()
        self.panel = panel
        self.model_id = row["id"]
        self.order = order
        self.data = row
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        outer.set_border_width(8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.name = Gtk.Label(xalign=0)
        self.name.set_ellipsize(Pango.EllipsizeMode.END)
        self.summary = Gtk.Label(xalign=0)
        self.summary.get_style_context().add_class("dim-label")
        self.summary.set_ellipsize(Pango.EllipsizeMode.END)
        self.state = Gtk.Label(xalign=0)
        self.state.set_ellipsize(Pango.EllipsizeMode.END)
        self.bar = Gtk.ProgressBar()
        self.bar.set_no_show_all(True)
        for w in (self.name, self.summary, self.state, self.bar):
            text.pack_start(w, False, False, 0)
        outer.pack_start(text, True, True, 0)

        self.primary = Gtk.Button()
        self.primary.set_size_request(210, -1)
        self.primary.set_valign(Gtk.Align.CENTER)
        self.primary.connect("clicked", lambda *_: panel.primary_clicked(self.model_id))
        outer.pack_start(self.primary, False, False, 0)

        more = Gtk.MenuButton()
        more.set_valign(Gtk.Align.CENTER)
        more.set_tooltip_text("More actions")
        more.add(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu = Gtk.Menu()
        self.remove_item = Gtk.MenuItem(label="Delete downloaded files...")
        self.remove_item.connect("activate", lambda *_: panel.remove_clicked(self.model_id))
        menu.append(self.remove_item)
        page = Gtk.MenuItem(label="Open the model page")
        page.connect("activate", lambda *_: self._open(self.data.get("page")))
        menu.append(page)
        lic = Gtk.MenuItem(label="Read the license")
        lic.connect("activate", lambda *_: self._open(self.data.get("license_url")))
        menu.append(lic)
        menu.show_all()
        more.set_popup(menu)
        outer.pack_start(more, False, False, 0)
        self.add(outer)
        self.show_all()
        self.update(row, {}, [], True)

    @staticmethod
    def _open(url: str | None) -> None:
        if url:
            webbrowser.open(url)

    def update(self, row: dict, current: dict, pending: list[str], has_token: bool) -> None:
        self.data = row
        tags = []
        if row["active"]:
            tags.append("<span foreground='#3a9a3a'><b>active</b></span>")
        name = GLib.markup_escape_text(row["name"])
        self.name.set_markup(f"<b>{name}</b>  " + "  ".join(tags))
        self.summary.set_markup(f"<small>{GLib.markup_escape_text(ui_text.model_summary(row))}</small>")
        self.state.set_text(_status_line(row, current, pending))
        label, action, sensitive = ui_text.primary_action(row, current, pending, has_token)
        self.primary.set_label(label)
        self.primary.set_sensitive(sensitive)
        style(self.primary, "primary" if action in ("download", "activate", "nodes", "token")
              else "danger" if action == "cancel" else None)
        self.action = action
        if current.get("model_id") == row["id"] and current.get("type") == "download":
            total = current.get("total") or 0
            self.bar.set_fraction(min(1.0, (current.get("done") or 0) / total) if total else 0.0)
            self.bar.show()
        else:
            self.bar.hide()
        self.remove_item.set_sensitive(bool(row["installed"] or row["partial"]) and not current)


class ModelsPanel(Gtk.Box):
    def __init__(self, app) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app = app
        self.set_border_width(12)
        self._server_files = None
        self._server_checked = 0.0
        self._last_rows_refresh = 0.0
        self._rows: list[dict] = []
        self._widgets: dict[str, ModelRow] = {}
        self._order_key: tuple = ()
        self._shown_error = None

        intro = Gtk.Label(xalign=0)
        intro.set_markup("Downloaded models are listed first. Download a model once, then press "
                         "<b>Set active</b> to use it in Generative Fill, Expand and Text to Image.")
        intro.set_line_wrap(True)
        self.pack_start(intro, False, False, 0)

        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.set_sort_func(self._sort)
        self.list.set_header_func(self._header)
        self.list.connect("row-selected", lambda *_: self._update_token_box())
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_min_content_height(300)
        scroller.add(self.list)
        self.list.set_focus_vadjustment(scroller.get_vadjustment())
        self.pack_start(scroller, True, True, 0)

        self.token_revealer = Gtk.Revealer()
        token_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        line.pack_start(Gtk.Label(label="Hugging Face token"), False, False, 0)
        self.token = Gtk.Entry()
        self.token.set_visibility(False)
        self.token.set_placeholder_text("hf_...")
        self.token.set_text(app.settings.hf_token or "")
        line.pack_start(self.token, True, True, 0)
        save = Gtk.Button(label="Save token")
        save.connect("clicked", self._on_save_token)
        line.pack_start(save, False, False, 0)
        token_box.pack_start(line, False, False, 0)
        explain = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hint = Gtk.Label(xalign=0)
        hint.set_markup("<small>Some models (FLUX) are gated: accept the license on the model page, then "
                        "paste a free read token. It is stored only in your GIMP profile.</small>")
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dim-label")
        explain.pack_start(hint, True, True, 0)
        explain.pack_start(Gtk.LinkButton.new_with_label(TOKEN_PAGE, "Get a token"), False, False, 0)
        token_box.pack_start(explain, False, False, 0)
        self.token_revealer.add(token_box)
        self.pack_start(self.token_revealer, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.message = Gtk.Label(xalign=0)
        self.message.set_line_wrap(True)
        self.message.set_selectable(True)
        footer.pack_start(self.message, True, True, 0)
        folder = Gtk.Button(label="Open models folder")
        folder.connect("clicked", self._on_open_folder)
        footer.pack_end(folder, False, False, 0)
        self.pack_start(footer, False, False, 0)

        self._refresh_rows(force=True)
        self._timer = GLib.timeout_add(1000, self._tick)
        self.connect("destroy", lambda *_: self.stop())

    # helpers -------------------------------------------------------------

    def stop(self) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self._close_downloads_window()

    def select(self, model_id: str) -> None:
        """Select (and scroll to) a model row."""
        widget = self._widgets.get(model_id)
        if widget is not None:
            self.list.select_row(widget)
            widget.grab_focus()

    def selected_id(self) -> str | None:
        row = self.list.get_selected_row()
        return row.model_id if row is not None else None

    def _row(self, model_id: str) -> dict | None:
        for r in self._rows:
            if r["id"] == model_id:
                return r
        return None

    def _say(self, text: str) -> None:
        self.message.set_text(text)

    def _has_token(self) -> bool:
        return bool((self.app.settings.hf_token or "").strip())

    @staticmethod
    def _sort(a: ModelRow, b: ModelRow) -> int:
        ka = (ui_text.model_sort_key(a.data), a.order)
        kb = (ui_text.model_sort_key(b.data), b.order)
        return (ka > kb) - (ka < kb)

    @staticmethod
    def _header(row: ModelRow, before: ModelRow | None) -> None:
        group = "Downloaded" if row.data["installed"] else "Available to download"
        prev = None if before is None else ("Downloaded" if before.data["installed"] else "Available to download")
        if group != prev:
            label = Gtk.Label(xalign=0)
            label.set_markup(f"<small><b>{group.upper()}</b></small>")
            label.set_margin_start(8)
            label.set_margin_top(8 if before is not None else 4)
            label.set_margin_bottom(2)
            label.get_style_context().add_class("dim-label")
            row.set_header(label)
        else:
            row.set_header(None)

    # refresh -------------------------------------------------------------

    def _pending(self) -> list[str]:
        try:
            return [t.get("model_id") for t in self.app.server.pending_tasks()]
        except Exception:  # noqa: BLE001 - status files are best effort
            return []

    def _refresh_rows(self, force: bool = False) -> None:
        now = time.monotonic()
        if now - self._server_checked > 15 or force:
            self._server_checked = now
            try:
                self._server_files = self.app.server_model_files()
            except Exception:  # noqa: BLE001
                self._server_files = None
        self._rows = self.app.model_rows(self._server_files)
        current = self.app.task_status().get("current") or {}
        pending = self._pending()
        has_token = self._has_token()
        for order, r in enumerate(self._rows):
            widget = self._widgets.get(r["id"])
            if widget is None:
                widget = ModelRow(self, r, order)
                self._widgets[r["id"]] = widget
                self.list.add(widget)
            widget.update(r, current, pending, has_token)
        key = tuple((r["id"], r["installed"], r["active"]) for r in self._rows)
        if key != self._order_key:
            self._order_key = key
            self.list.invalidate_sort()
            self.list.invalidate_headers()
        self._last_rows_refresh = now
        self._update_token_box()

    def _update_token_box(self) -> None:
        selected = self._row(self.selected_id() or "")
        current = self.app.task_status().get("current") or {}
        gated_in_use = any(r["gated"] and (r["installed"] or r["partial"] or r["id"] == current.get("model_id"))
                           for r in self._rows)
        show = bool((selected and selected["gated"]) or gated_in_use or self._has_token())
        self.token_revealer.set_reveal_child(show)

    def _tick(self) -> bool:
        if time.monotonic() - self._last_rows_refresh > 3:
            self._refresh_rows()
            return True
        current = self.app.task_status().get("current") or {}
        pending = self._pending()
        has_token = self._has_token()
        for r in self._rows:
            widget = self._widgets.get(r["id"])
            if widget is not None:
                widget.update(r, current, pending, has_token)
        if not current:
            history = self.app.task_status().get("history") or []
            if history and history[0].get("state") == "error" and history[0].get("finished") != self._shown_error:
                last = history[0]
                self._shown_error = last.get("finished")
                self._say(ui_text.with_next_step(f"The last task for {last.get('model_id')} failed: "
                                                 f"{last.get('message')}"))
        return True

    # actions -------------------------------------------------------------

    def primary_clicked(self, model_id: str) -> None:
        widget = self._widgets.get(model_id)
        action = getattr(widget, "action", None)
        self.list.select_row(widget)
        if action == "download":
            self._download(model_id)
        elif action == "cancel":
            self.app.server.request_cancel()
            self._say("Download cancelled. The partial file is kept, so Resume download continues where it "
                      "stopped.")
        elif action == "activate":
            self._set_active(model_id)
        elif action == "nodes":
            self._install_nodes(model_id)
        elif action == "token":
            self.token_revealer.set_reveal_child(True)
            self.token.grab_focus()
            row = self._row(model_id) or {}
            self._say(f"{row.get('name', model_id)} is gated. Accept its license on the model page (menu next "
                      "to the button), paste your token below, press Save token, then Download.")
        self._refresh_rows(force=True)

    def _download(self, model_id: str) -> None:
        try:
            if self.token.get_text().strip() != (self.app.settings.hf_token or ""):
                self.app.save_token(self.token.get_text())
            ids = self.app.queue_download(model_id)
            row = self._row(model_id) or {}
            self._say(f"Downloading {row.get('name', model_id)}"
                      + (f" ({len(ids)} parts)" if len(ids) > 1 else "")
                      + ". It continues in the background even if you close this window.")
            self._open_downloads_window()
        except BackendError as err:
            self._say(ui_text.with_next_step(str(err)))
        except OSError as err:
            self._say(ui_text.save_failed(str(self.app.paths.config), str(err)))

    def _set_active(self, model_id: str) -> None:
        try:
            entry = self.app.set_active(model_id)
            self._say(f"{entry.name} is now the active model.")
        except BackendError as err:
            self._say(ui_text.with_next_step(str(err)))
        except OSError as err:
            self._say(ui_text.save_failed(str(self.app.paths.config), str(err)))

    def _install_nodes(self, model_id: str) -> None:
        nodes = self.app.nodes_to_install(model_id)
        if not nodes:
            self._say("Nothing to install.")
            return
        lines = "\n".join(f"- {n.repo} @ {n.commit[:10]} ({n.license or 'see repository'})" for n in nodes)
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                   message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text="Install extra nodes into ComfyUI?")
        dialog.format_secondary_text(
            f"This downloads and installs (with ComfyUI's own Python):\n{lines}\n\n"
            "The backend restarts afterwards; a running generation would be interrupted.")
        answer = dialog.run()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK:
            return
        try:
            self.app.queue_node_install(model_id)
            self._say("Installing the nodes. The backend restarts when it is done.")
        except BackendError as err:
            self._say(ui_text.with_next_step(str(err)))

    def remove_clicked(self, model_id: str) -> None:
        r = self._row(model_id)
        if not r:
            return
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                   message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=f"Delete the files of '{r['name']}' ({r['size']})?")
        dialog.format_secondary_text("Files shared with other downloaded models are kept. You can download "
                                     "it again later.")
        answer = dialog.run()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK:
            return
        self.app.remove_model(model_id)
        self._say(f"Deleting the files of {r['name']}...")
        self._refresh_rows(force=True)

    def _on_open_folder(self, *_):
        try:
            self.app.open_models_folder()
        except OSError as err:
            self._say(f"Could not open the folder: {err}. Next step: open {self.app.models_root} in the "
                      "file manager yourself.")

    def _on_save_token(self, *_):
        try:
            self.app.save_token(self.token.get_text())
        except OSError as err:
            self._say(ui_text.save_failed(str(self.app.paths.config), str(err)))
            return
        self._say("Token saved in your GIMP profile." if self.token.get_text().strip() else "Token removed.")
        self._refresh_rows(force=True)

    # floating downloads window (same window class as generation progress) ----

    _dl_window = None
    _dl_timer = 0

    def _open_downloads_window(self) -> None:
        if not self.app.settings.progress_window or self._dl_window is not None:
            return
        try:
            from .progress_window import ProgressWindow
            self._dl_window = ProgressWindow("Model downloads", "", on_cancel=self.app.server.request_cancel,
                                             position=(self.app.settings.progress_window_x,
                                                       self.app.settings.progress_window_y),
                                             show_preview=False, quit_main_on_close=False)
            self._dl_timer = GLib.timeout_add(1000, self._tick_downloads)
        except Exception as err:  # noqa: BLE001 - the window is optional
            self._dl_window = None
            self._say(f"The download continues, but the progress window could not be opened: {err}. "
                      "Next step: watch the row's progress here.")

    def _tick_downloads(self) -> bool:
        win = self._dl_window
        if win is None:
            return False
        status = self.app.task_status()
        current = status.get("current") or {}
        pending = [t.get("model_id") or t.get("type", "task") for t in self.app.server.pending_tasks()]
        win.set_downloads(current, pending)
        if current.get("type") == "download":
            done, total = current.get("done") or 0, current.get("total") or 0
            win.set_step(done / total if total else 0.0, f"Downloading {cat.human_size(done)} of {cat.human_size(total)}")
            return True
        if current or pending:
            win.set_step(0.0, f"{current.get('type', 'task')}: {current.get('state', 'working')}")
            return True
        history = status.get("history") or []
        last = history[0] if history else {}
        ok = last.get("state") == "done"
        win.finish(ok, "Download complete" if ok else f"{last.get('state', 'stopped')}: {last.get('message', '')}", 1500)
        self._dl_window = None
        self._dl_timer = 0
        return False

    def _close_downloads_window(self) -> None:
        if self._dl_timer:
            GLib.source_remove(self._dl_timer)
            self._dl_timer = 0
        if self._dl_window is not None:
            try:
                self._dl_window.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._dl_window = None

# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Models tab: catalog table, download/activate/remove buttons, token field.

Pure GTK 3 (as shipped with GIMP). The panel polls the supervisor's task
status file once per second through a GLib timeout and never blocks the UI.
"""

from __future__ import annotations

import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import catalog as cat  # noqa: E402
from .backend import BackendError  # noqa: E402

COLUMNS = ("Model", "Tier", "Status", "Size", "License", "Source")
COL_ID = len(COLUMNS)
COL_ACTIVE = COL_ID + 1


class ModelsPanel(Gtk.Box):
    def __init__(self, app) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        self.set_border_width(6)
        self._server_files = None
        self._server_checked = 0.0
        self._last_rows_refresh = 0.0

        self.store = Gtk.ListStore(str, str, str, str, str, str, str, str)
        self.view = Gtk.TreeView(model=self.store)
        for index, title in enumerate(COLUMNS):
            renderer = Gtk.CellRendererText()
            if index == 0:
                renderer.set_property("ellipsize", 3)  # END
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            column.set_expand(index == 0)
            if index == 0:
                column.set_min_width(260)
            elif index == 4:
                renderer.set_property("ellipsize", 3)
                column.set_max_width(220)
            self.view.append_column(column)
        active_col = Gtk.TreeViewColumn("Active", Gtk.CellRendererText(), text=COL_ACTIVE)
        self.view.insert_column(active_col, 0)
        self.view.set_tooltip_column(0)
        self.view.get_selection().connect("changed", lambda *_: self._update_buttons())
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(220)
        scroller.add(self.view)
        self.pack_start(scroller, True, True, 0)

        self.detail = Gtk.Label(xalign=0)
        self.detail.set_line_wrap(True)
        self.detail.set_selectable(True)
        self.pack_start(self.detail, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.btn_download = self._button(buttons, "Download", self._on_download)
        self.btn_cancel = self._button(buttons, "Cancel", self._on_cancel)
        self.btn_active = self._button(buttons, "Set active", self._on_set_active)
        self.btn_nodes = self._button(buttons, "Install nodes", self._on_install_nodes)
        self.btn_remove = self._button(buttons, "Remove", self._on_remove)
        self._button(buttons, "Open models folder", self._on_open_folder)
        self.pack_start(buttons, False, False, 0)

        token_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        token_box.pack_start(Gtk.Label(label="Hugging Face token:"), False, False, 0)
        self.token = Gtk.Entry()
        self.token.set_visibility(False)
        self.token.set_placeholder_text("hf_... (needed for gated models such as FLUX)")
        self.token.set_text(app.settings.hf_token or "")
        token_box.pack_start(self.token, True, True, 0)
        self._button(token_box, "Save token", self._on_save_token)
        self.pack_start(token_box, False, False, 0)
        hint = Gtk.Label(xalign=0)
        hint.set_markup("<small>Tokens: huggingface.co/settings/tokens (read access). Accept each gated "
                        "model's license on its page first. The token is stored only in config.json.</small>")
        hint.set_line_wrap(True)
        self.pack_start(hint, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("")
        self.pack_start(self.progress, False, False, 0)
        self.message = Gtk.Label(xalign=0)
        self.message.set_line_wrap(True)
        self.pack_start(self.message, False, False, 0)

        self._refresh_rows(force=True)
        self._timer = GLib.timeout_add(1000, self._tick)
        self.connect("destroy", lambda *_: self.stop())

    # helpers -------------------------------------------------------------

    @staticmethod
    def _button(box, label, handler):
        button = Gtk.Button(label=label)
        button.connect("clicked", handler)
        box.pack_start(button, False, False, 0)
        return button

    def stop(self) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def selected_id(self) -> str | None:
        model, it = self.view.get_selection().get_selected()
        return model[it][COL_ID] if it else None

    def _row(self, model_id: str) -> dict | None:
        for r in self._rows:
            if r["id"] == model_id:
                return r
        return None

    def _say(self, text: str) -> None:
        self.message.set_text(text)

    # refresh -------------------------------------------------------------

    def _refresh_rows(self, force: bool = False) -> None:
        now = time.monotonic()
        if now - self._server_checked > 15 or force:
            self._server_checked = now
            try:
                self._server_files = self.app.server_model_files()
            except Exception:
                self._server_files = None
        status = self.app.task_status()
        current = status.get("current") or {}
        self._rows = self.app.model_rows(self._server_files)
        selected = self.selected_id()
        self.store.clear()
        for r in self._rows:
            label = r["status"]
            if current.get("model_id") == r["id"]:
                if current.get("type") == "download":
                    pct = 100.0 * current.get("done", 0) / max(1, current.get("total", 1))
                    label = f"Downloading {pct:.0f}%"
                elif current.get("type") == "install_nodes":
                    label = "Installing nodes"
                elif current.get("type") == "remove":
                    label = "Removing"
            elif r["id"] in [t.get("model_id") for t in self.app.server.pending_tasks()]:
                label = "Queued"
            elif label == "Installed" and r["seen_by_server"] is False:
                label = "Installed (restart backend)"
            self.store.append([r["name"], r["tier"], label, r["size"], r["license"], r["source"],
                               r["id"], "*" if r["active"] else ""])
        if selected:
            for row in self.store:
                if row[COL_ID] == selected:
                    self.view.get_selection().select_iter(row.iter)
        self._last_rows_refresh = now
        self._update_buttons()

    def _update_buttons(self) -> None:
        r = self._row(self.selected_id() or "")
        busy = bool((self.app.task_status().get("current") or {}))
        self.btn_download.set_sensitive(bool(r) and not r["installed"] and not busy)
        self.btn_cancel.set_sensitive(busy)
        self.btn_active.set_sensitive(bool(r) and r["installed"] and r["runnable"] and not r["missing_nodes"])
        self.btn_nodes.set_sensitive(bool(r) and bool(r["missing_nodes"]) and not busy)
        self.btn_remove.set_sensitive(bool(r) and (r["installed"] or bool(r["partial"])) and not busy)
        if r:
            caps = ", ".join(r["capabilities"])
            gated = " Gated (token required)." if r["gated"] else ""
            self.detail.set_markup(
                f"<b>{GLib.markup_escape_text(r['name'])}</b>  [{r['id']}]\n"
                f"Capabilities: {caps}. Min VRAM: {r['min_vram_gb']:g} GB. Source: {GLib.markup_escape_text(r['uploader'])}.{gated}\n"
                f"License: {GLib.markup_escape_text(r['license'])} - {GLib.markup_escape_text(r['license_url'])}\n"
                f"Page: {GLib.markup_escape_text(r['page'])}"
                + (f"\nNeeds custom nodes: {', '.join(r['missing_nodes'])}" if r["missing_nodes"] else "")
                + (f"\nNeeds companion: {', '.join(r['missing_models'])}" if r["missing_models"] else ""))
        else:
            self.detail.set_text("Select a model to see its details.")

    def _tick(self) -> bool:
        status = self.app.task_status()
        current = status.get("current") or {}
        if current:
            done, total = current.get("done", 0), current.get("total", 0)
            frac = done / total if total else 0.0
            speed = current.get("speed", 0.0) / 1_048_576
            name = current.get("file", "")
            if current.get("type") == "download":
                self.progress.set_fraction(min(1.0, frac))
                self.progress.set_text(f"{name}  {cat.human_size(done)} / {cat.human_size(total)}  {speed:.1f} MB/s")
            else:
                self.progress.pulse()
                self.progress.set_text(f"{current.get('state', '')} {name}")
        else:
            self.progress.set_fraction(0.0)
            history = status.get("history") or []
            if history:
                last = history[0]
                when = time.strftime("%H:%M:%S", time.localtime(last.get("finished", 0)))
                self.progress.set_text(f"last: {last.get('type')} {last.get('model_id')} {last.get('state')} ({when})")
                if last.get("state") == "error":
                    self._say(f"Error: {last.get('message')}")
        if time.monotonic() - self._last_rows_refresh > 3:
            self._refresh_rows()
        else:
            self._update_buttons()
        return True

    # actions -------------------------------------------------------------

    def _on_download(self, *_):
        model_id = self.selected_id()
        if not model_id:
            return
        if self.token.get_text().strip() != (self.app.settings.hf_token or ""):
            self.app.save_token(self.token.get_text())
        try:
            ids = self.app.queue_download(model_id)
            self._say(f"Queued {len(ids)} download task(s) for {model_id}. Progress continues in the "
                      "background even if you close this dialog.")
        except BackendError as err:
            self._say(str(err))
        self._refresh_rows(force=True)

    def _on_cancel(self, *_):
        self.app.server.request_cancel()
        self._say("Cancel requested; the partial file is kept for resume.")

    def _on_set_active(self, *_):
        model_id = self.selected_id()
        if not model_id:
            return
        try:
            entry = self.app.set_active(model_id)
            self._say(f"Active model: {entry.name} (template {entry.template}).")
        except BackendError as err:
            self._say(str(err))
        self._refresh_rows(force=True)

    def _on_install_nodes(self, *_):
        model_id = self.selected_id()
        if not model_id:
            return
        nodes = self.app.nodes_to_install(model_id)
        if not nodes:
            self._say("Nothing to install.")
            return
        lines = "\n".join(f"- {n.repo} @ {n.commit[:10]} ({n.license or 'see repository'})" for n in nodes)
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                   message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text="Install custom nodes into ComfyUI?")
        dialog.format_secondary_text(
            f"This runs git clone and pip install (with ComfyUI's own Python) for:\n{lines}\n\n"
            "The backend restarts afterwards; a running generation would be interrupted.")
        answer = dialog.run()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK:
            return
        try:
            self.app.queue_node_install(model_id)
            self._say("Node installation queued.")
        except BackendError as err:
            self._say(str(err))
        self._refresh_rows(force=True)

    def _on_remove(self, *_):
        model_id = self.selected_id()
        r = self._row(model_id or "")
        if not r:
            return
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(), modal=True,
                                   message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=f"Delete the files of '{r['name']}' ({r['size']})?")
        dialog.format_secondary_text("Files shared with other installed models are kept.")
        answer = dialog.run()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK:
            return
        self.app.remove_model(model_id)
        self._say("Removal queued.")
        self._refresh_rows(force=True)

    def _on_open_folder(self, *_):
        try:
            self.app.open_models_folder()
        except OSError as err:
            self._say(str(err))

    def _on_save_token(self, *_):
        self.app.save_token(self.token.get_text())
        self._say("Token saved to config.json." if self.token.get_text().strip() else "Token cleared.")
        self._refresh_rows(force=True)

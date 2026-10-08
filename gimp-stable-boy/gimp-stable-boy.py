#!/usr/bin/env python3
# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann (original Stable Boy for GIMP 2.10)
# Copyright (C) 2026 Stable Boy contributors (GIMP 3 port and redesign)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""GIMP 3 entry point: registers the Filters > AI procedures.

Menu:
  Filters > AI > Generative Fill...           python-fu-stable-boy-generative-fill
  Filters > AI > Generative Expand...         python-fu-stable-boy-generative-expand
  Filters > AI > Text to Image...             python-fu-stable-boy-text-to-image
  Filters > AI > Generative Fill Settings...  python-fu-stable-boy-settings
  Filters > AI > Stop AI Backend              python-fu-stable-boy-stop-backend
"""

from __future__ import annotations

import os
import sys
import traceback

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
from gi.repository import Gimp, GimpUi, GLib, GObject  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stable_boy import __version__  # noqa: E402
from stable_boy.backend import BackendError, describe_error  # noqa: E402
from stable_boy.config import Paths, Settings  # noqa: E402

PROC_FILL = "python-fu-stable-boy-generative-fill"
PROC_EXPAND = "python-fu-stable-boy-generative-expand"
PROC_TXT2IMG = "python-fu-stable-boy-text-to-image"
PROC_SETTINGS = "python-fu-stable-boy-settings"
PROC_STOP = "python-fu-stable-boy-stop-backend"
MENU = "<Image>/Filters/AI"
AUTHOR = "Stable Boy contributors (original: Torben Giesselmann)"
RW = GObject.ParamFlags.READWRITE

SAMPLERS = ["euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral", "lms",
            "dpmpp_2s_ancestral", "dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu",
            "ddim", "uni_pc"]
SCHEDULERS = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]


def _choice(options: list[tuple[str, str]]) -> Gimp.Choice:
    choice = Gimp.Choice.new()
    for index, (nick, label) in enumerate(options):
        choice.add(nick, index, label, "")
    return choice


def _model_choice() -> Gimp.Choice:
    """'active' (from the settings), the two legacy tiers, then every catalog model."""
    options = [("active", "Active model (see Settings > Models)"),
               ("fast", "Fast (SD 1.5 inpainting)"), ("quality", "Quality (SDXL + Fooocus)")]
    try:
        from stable_boy.catalog import load_catalog
        for entry in load_catalog(plugin_dir=os.path.dirname(os.path.abspath(__file__))):
            if entry.runnable:
                options.append((entry.id, f"{entry.name} [{entry.tier}]".replace("_", "__")))
    except Exception:
        pass
    return _choice(options)


def _load_models_cache() -> dict:
    import json
    try:
        paths = Paths.for_profile(Gimp.directory())
        return json.loads(paths.models_cache.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fail(procedure, error: BaseException, log=None):
    text = describe_error(error) if isinstance(error, BackendError) else f"{type(error).__name__}: {error}"
    if log is not None:
        log.error("procedure failed: %s\n%s", text, traceback.format_exc())
    Gimp.message(text)
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(text))


def _dialog(procedure, config, title: str) -> bool:
    GimpUi.init("gimp-stable-boy")
    dialog = GimpUi.ProcedureDialog.new(procedure, config, title)
    dialog.fill(None)
    ok = dialog.run()
    dialog.destroy()
    return bool(ok)


# ------------------------------------------------------------------ runs ----

def run_fill(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and not _dialog(procedure, config, "Generative Fill"):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    from stable_boy.app import App
    app = None
    try:
        app = App()
        app.generative_fill(image, config.get_property("prompt"), config.get_property("negative"),
                            config.get_property("variations"), config.get_property("strength"),
                            config.get_property("seed"), config.get_property("model"))
    except Exception as err:  # noqa: BLE001 - every failure must reach the user
        return _fail(procedure, err, app.log if app else None)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run_expand(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and not _dialog(procedure, config, "Generative Expand"):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    from stable_boy.app import App
    app = None
    try:
        app = App()
        app.generative_expand(image, config.get_property("prompt"), config.get_property("negative"),
                              config.get_property("left"), config.get_property("top"),
                              config.get_property("right"), config.get_property("bottom"),
                              config.get_property("variations"), config.get_property("seed"),
                              config.get_property("model"))
    except Exception as err:  # noqa: BLE001
        return _fail(procedure, err, app.log if app else None)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run_txt2img(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and not _dialog(procedure, config, "Text to Image"):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    from stable_boy.app import App
    app = None
    try:
        app = App()
        app.text_to_image(image, config.get_property("prompt"), config.get_property("negative"),
                          config.get_property("width"), config.get_property("height"),
                          config.get_property("variations"), config.get_property("seed"),
                          config.get_property("model"), config.get_property("target"))
    except Exception as err:  # noqa: BLE001
        return _fail(procedure, err, app.log if app else None)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


SETTINGS_KEYS = ["backend", "comfy_dir", "url", "a1111_url", "autostart", "idle_timeout_minutes",
                 "quality", "progress_window", "checkpoint", "sdxl_checkpoint", "fooocus_patch", "steps", "cfg",
                 "sampler", "scheduler", "grow", "feather", "prefill", "max_side_sd15",
                 "max_side_sdxl", "txt2img_width", "txt2img_height", "startup_timeout",
                 "request_timeout", "extra_server_args", "debug"]


def _settings_dialog(procedure, config) -> bool:
    """Settings as a notebook: General (generated from the procedure arguments)
    and Models (the catalog panel)."""
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from stable_boy.app import App
    from stable_boy.models_ui import ModelsPanel

    GimpUi.init("gimp-stable-boy")
    dialog = GimpUi.ProcedureDialog.new(procedure, config, "Generative Fill Settings")
    general = dialog.fill_box("general", [k.replace("_", "-") for k in SETTINGS_KEYS] + ["check-backend"])
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_min_content_height(480)
    scroller.add(general)
    notebook = Gtk.Notebook()
    notebook.append_page(scroller, Gtk.Label(label="General"))
    panel = None
    try:
        panel = ModelsPanel(App())
        notebook.append_page(panel, Gtk.Label(label="Models"))
    except Exception as err:  # noqa: BLE001 - the General page must still work
        notebook.append_page(Gtk.Label(label=f"Models tab unavailable: {err}"), Gtk.Label(label="Models"))
    dialog.get_content_area().pack_start(notebook, True, True, 0)
    dialog.set_default_size(920, 720)
    notebook.show_all()
    if os.environ.get("SB_SETTINGS_TAB") == "models":
        def _go_models(*_):
            notebook.set_current_page(1)
            print(f"[stable-boy] models tab requested; current page {notebook.get_current_page()} of "
                  f"{notebook.get_n_pages()}", file=sys.stderr)
            return False
        dialog.connect("map-event", _go_models)
        GLib.timeout_add(400, _go_models)
        GLib.timeout_add(1500, _go_models)
    autoclose = float(os.environ.get("SB_TEST_AUTOCLOSE", "0") or 0)
    if autoclose > 0:
        GLib.timeout_add(int(autoclose * 1000), lambda: dialog.response(Gtk.ResponseType.OK) or False)
    ok = dialog.run()
    if panel is not None:
        panel.stop()
    dialog.destroy()
    return bool(ok)


def run_settings(procedure, config, data):
    run_mode = config.get_property("run-mode")
    paths = Paths.for_profile(Gimp.directory()).ensure()
    settings = Settings.load(paths.config)
    for key in SETTINGS_KEYS:  # dialog always starts from the saved file, not last-used values
        try:
            config.set_property(key.replace("_", "-"), getattr(settings, key))
        except Exception:
            pass
    if run_mode == Gimp.RunMode.INTERACTIVE and not _settings_dialog(procedure, config):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    settings = Settings.load(paths.config)  # the Models tab may have changed active_model / token meanwhile
    for key in SETTINGS_KEYS:
        setattr(settings, key, config.get_property(key.replace("_", "-")))
    settings.save(paths.config)
    if config.get_property("check-backend"):
        from stable_boy.app import App
        app = App()
        health = app.check_backend()
        if health.ok:
            Gimp.message(f"Backend OK: {health.detail}\n"
                         f"Checkpoints: {', '.join(health.checkpoints) or 'none'}\n"
                         f"Inpaint nodes: {'yes' if health.inpaint_nodes else 'no'}")
        else:
            Gimp.message(f"Backend check failed: {health.detail}")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run_stop(procedure, config, data):
    from stable_boy.app import App
    try:
        Gimp.message(App().stop_backend())
    except Exception as err:  # noqa: BLE001
        return _fail(procedure, err)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# --------------------------------------------------------------- plug-in ----

class StableBoy(Gimp.PlugIn):
    def do_set_i18n(self, name):
        return False, None, None

    def do_query_procedures(self):
        return [PROC_FILL, PROC_EXPAND, PROC_TXT2IMG, PROC_SETTINGS, PROC_STOP]

    def do_create_procedure(self, name):
        if name == PROC_FILL:
            return self._fill()
        if name == PROC_EXPAND:
            return self._expand()
        if name == PROC_TXT2IMG:
            return self._txt2img()
        if name == PROC_SETTINGS:
            return self._settings()
        if name == PROC_STOP:
            return self._stop()
        return None

    @staticmethod
    def _common_prompt_args(procedure, variations_default=1):
        procedure.add_string_argument("prompt", "_Prompt", "What should appear in the selection",
                                      "", RW)
        procedure.add_string_argument("negative", "_Negative prompt", "What to avoid",
                                      "blurry, low quality, watermark, text", RW)
        procedure.add_int_argument("variations", "_Variations", "Number of results (layers)",
                                   1, 8, variations_default, RW)

    @staticmethod
    def _seed_quality_args(procedure):
        procedure.add_int_argument("seed", "_Seed", "-1 for random", -1, 2**31 - 1, -1, RW)
        procedure.add_choice_argument("model", "_Model", "Which model to use ('active' = the one chosen "
                                      "in Settings > Models)", _model_choice(), "active", RW)

    def _image_procedure(self, name, func, label, blurb, help_text):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, func, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE
                                       | Gimp.ProcedureSensitivityMask.DRAWABLES
                                       | Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        procedure.set_menu_label(label)
        procedure.add_menu_path(MENU)
        procedure.set_documentation(blurb, help_text, name)
        procedure.set_attribution(AUTHOR, AUTHOR, "2022-2026")
        return procedure

    def _fill(self):
        p = self._image_procedure(
            PROC_FILL, run_fill, "Generative _Fill...",
            "Fill the selection with AI-generated content",
            "Crops a context region around the selection, sends it to the AI backend "
            "(ComfyUI by default, started automatically), and adds the result as a new "
            "layer with a feathered layer mask. Stable Boy " + __version__)
        self._common_prompt_args(p)
        p.add_double_argument("strength", "_Strength", "1.0 replaces the selection entirely; "
                              "lower values keep more of the original", 0.1, 1.0, 1.0, RW)
        self._seed_quality_args(p)
        return p

    def _expand(self):
        p = self._image_procedure(
            PROC_EXPAND, run_expand, "Generative _Expand...",
            "Grow the canvas and fill the new area with AI-generated content",
            "Resizes the canvas by the given margins and outpaints the new border, "
            "returning it as a new masked layer. Stable Boy " + __version__)
        self._common_prompt_args(p)
        for side in ("left", "top", "right", "bottom"):
            p.add_int_argument(side, f"_{side.capitalize()} (px)", f"Pixels to add on the {side}",
                               0, 4096, 256 if side in ("left", "right") else 0, RW)
        self._seed_quality_args(p)
        return p

    def _txt2img(self):
        p = self._image_procedure(
            PROC_TXT2IMG, run_txt2img, "_Text to Image...",
            "Generate an image from a text prompt",
            "Generates images from text into a new layer (sized to the selection when "
            "there is one) or a new image. Stable Boy " + __version__)
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE
                               | Gimp.ProcedureSensitivityMask.DRAWABLES
                               | Gimp.ProcedureSensitivityMask.NO_DRAWABLES
                               | Gimp.ProcedureSensitivityMask.NO_IMAGE)
        self._common_prompt_args(p)
        p.add_int_argument("width", "_Width", "0 = selection or configured default", 0, 4096, 0, RW)
        p.add_int_argument("height", "_Height", "0 = selection or configured default", 0, 4096, 0, RW)
        p.add_choice_argument("target", "_Result as", "Where the result goes",
                              _choice([("layer", "New layer"), ("image", "New image")]), "layer", RW)
        self._seed_quality_args(p)
        return p

    def _settings(self):
        p = Gimp.Procedure.new(self, PROC_SETTINGS, Gimp.PDBProcType.PLUGIN, run_settings, None)
        p.set_menu_label("Generative Fill _Settings...")
        p.add_menu_path(MENU)
        p.set_documentation("Configure the AI backend and generation defaults",
                            "Backend location, model choice, sampling defaults, mask feathering "
                            "and the idle timeout. Saved to the GIMP profile. Stable Boy " + __version__,
                            PROC_SETTINGS)
        p.set_attribution(AUTHOR, AUTHOR, "2022-2026")
        p.add_enum_argument("run-mode", "Run mode", "The run mode", Gimp.RunMode,
                            Gimp.RunMode.INTERACTIVE, RW)
        s = Settings()
        cache = _load_models_cache()
        p.add_choice_argument("backend", "_Backend", "Generation server", _choice(
            [("comfyui", "ComfyUI (managed, recommended)"), ("a1111", "AUTOMATIC1111 WebUI (external)")]),
            s.backend, RW)
        p.add_string_argument("comfy-dir", "Co_mfyUI folder", "Folder of the ComfyUI portable build",
                              s.comfy_dir, RW)
        p.add_string_argument("url", "Com_fyUI URL", "Base URL of ComfyUI", s.url, RW)
        p.add_string_argument("a1111-url", "_A1111 URL", "Base URL of the WebUI API", s.a1111_url, RW)
        p.add_boolean_argument("autostart", "S_tart backend automatically", "", s.autostart, RW)
        p.add_int_argument("idle-timeout-minutes", "_Idle timeout (min)",
                           "Stop the backend after this many idle minutes; 0 = until GIMP exits",
                           0, 24 * 60, s.idle_timeout_minutes, RW)
        p.add_choice_argument("quality", "L_egacy tier for 'fast'/'quality' calls", "",
                              _choice([("fast", "Fast (SD 1.5 inpainting)"), ("quality", "Quality (SDXL + Fooocus)")]),
                              s.quality, RW)
        p.add_boolean_argument("progress-window", "Float_ing progress window", "Show a floating window with "
                               "progress, live preview and downloads", s.progress_window, RW)
        self._model_arg(p, "checkpoint", "SD 1.5 _checkpoint", cache.get("checkpoints"), s.checkpoint)
        self._model_arg(p, "sdxl-checkpoint", "SD_XL checkpoint", cache.get("checkpoints"), s.sdxl_checkpoint)
        self._model_arg(p, "fooocus-patch", "Fooocus _patch", cache.get("fooocus_patches"), s.fooocus_patch)
        p.add_int_argument("steps", "Ste_ps", "", 1, 150, s.steps, RW)
        p.add_double_argument("cfg", "CF_G scale", "", 0.0, 30.0, s.cfg, RW)
        p.add_choice_argument("sampler", "Sampler", "", _choice([(x, x) for x in SAMPLERS]), s.sampler, RW)
        p.add_choice_argument("scheduler", "Sche_duler", "", _choice([(x, x) for x in SCHEDULERS]),
                              s.scheduler, RW)
        p.add_int_argument("grow", "Mas_k grow (px)", "Dilate the mask before generating", 0, 256, s.grow, RW)
        p.add_int_argument("feather", "Mask feather (p_x)", "Soft edge of the layer mask", 0, 256, s.feather, RW)
        p.add_boolean_argument("prefill", "Pre-fill masked area", "Hide old content under the mask "
                               "before sampling (needs comfyui-inpaint-nodes)", s.prefill, RW)
        p.add_int_argument("max-side-sd15", "Max _working size SD 1.5", "", 512, 2048, s.max_side_sd15, RW)
        p.add_int_argument("max-side-sdxl", "Max worki_ng size SDXL", "", 768, 2048, s.max_side_sdxl, RW)
        p.add_int_argument("txt2img-width", "Text to Image width", "", 64, 4096, s.txt2img_width, RW)
        p.add_int_argument("txt2img-height", "Text to Image height", "", 64, 4096, s.txt2img_height, RW)
        p.add_int_argument("startup-timeout", "Start_up timeout (s)", "", 30, 1800, s.startup_timeout, RW)
        p.add_int_argument("request-timeout", "Re_quest timeout (s)", "0 = estimate per request",
                           0, 7200, s.request_timeout, RW)
        p.add_string_argument("extra-server-args", "Extra ComfyUI ar_guments",
                              "For example --lowvram", s.extra_server_args, RW)
        p.add_boolean_argument("debug", "_Verbose log", "", s.debug, RW)
        p.add_boolean_argument("check-backend", "Chec_k backend now",
                               "Start the backend if needed and list its models", True, RW)
        return p

    @staticmethod
    def _model_arg(procedure, name, nick, options, default):
        options = [str(o) for o in (options or [])]
        if default and default not in options:
            options.insert(0, default)
        if options:
            # a single underscore would become a mnemonic in the radio label
            procedure.add_choice_argument(name, nick, "", _choice([(o, o.replace("_", "__")) for o in options]),
                                          default, RW)
        else:
            procedure.add_string_argument(name, nick, "", default, RW)

    def _stop(self):
        p = Gimp.Procedure.new(self, PROC_STOP, Gimp.PDBProcType.PLUGIN, run_stop, None)
        p.set_menu_label("Stop AI _Backend")
        p.add_menu_path(MENU)
        p.set_documentation("Shut down the managed ComfyUI backend to free GPU memory",
                            "Asks the Stable Boy supervisor to terminate the ComfyUI process it "
                            "started. The backend restarts automatically on the next request.",
                            PROC_STOP)
        p.set_attribution(AUTHOR, AUTHOR, "2022-2026")
        p.add_enum_argument("run-mode", "Run mode", "The run mode", Gimp.RunMode,
                            Gimp.RunMode.INTERACTIVE, RW)
        return p


Gimp.main(StableBoy.__gtype__, sys.argv)

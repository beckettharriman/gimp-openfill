# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Orchestration: GIMP image in, backend request out, layers back in.

This module imports ``gimp_io`` (and therefore ``gi``); everything below it
is plain Python.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import catalog as cat
from . import geometry, gimp_io, workflow
from .backend import (
    SETTINGS_MENU,
    Backend,
    BackendError,
    BackendUnavailable,
    HealthStatus,
    InpaintRequest,
    ModelMissing,
    ModelSpec,
    Sampling,
    Txt2ImgRequest,
)
from .backends.a1111 import A1111Backend
from .backends.comfy import ComfyBackend
from .comfy_api import ComfyApiError, ComfyClient
from .config import Paths, Settings, comfy_layout
from .geometry import Rect
from .log import get_logger
from .runner import Runner
from .server import ServerManager
from .workflow import model_display_name

LEGACY_CHOICES = {"fast": "sd15-inpainting", "quality": "sdxl-base"}
MODEL_LIST_NODES = (
    ("CheckpointLoaderSimple", "ckpt_name"),
    ("UNETLoader", "unet_name"),
    ("UnetLoaderGGUF", "unet_name"),
    ("INPAINT_LoadInpaintModel", "model_name"),
)


class NothingSelected(BackendError):
    """The command needs a selection and there is none."""


class UnsupportedImage(BackendError):
    """The image cannot take generated pixels as it is (indexed colors)."""


INDEXED_MESSAGE = (
    "This image uses indexed colors, which cannot hold generated pixels without destroying "
    "them. Convert it with Image > Mode > RGB (or Grayscale) and run the command again."
)
NO_SELECTION_MESSAGE = (
    "Nothing is selected. Select the area to fill first (for example with the Rectangle or "
    "Free Select tool), then run Generative Fill again. To regenerate the whole image, use "
    "Select > All."
)


def _layer_name(kind: str, prompt: str) -> str:
    text = " ".join(prompt.split())[:48].strip()
    return f"{kind}: {text}" if text else kind


class App:
    def __init__(self, interactive: bool = True) -> None:
        # interactive=False (scripts, batch): no progress window, so a failure never waits for a click
        self.interactive = interactive
        self.paths = Paths.for_profile(gimp_io.profile_dir()).ensure()
        self.settings = Settings.load(self.paths.config)
        self.log = get_logger(self.paths.log, debug=self.settings.debug)
        if self.settings.load_problem:
            self.log.warning("settings: %s", self.settings.load_problem)
            try:
                gimp_io.message(self.settings.load_problem)
            except Exception:  # noqa: BLE001 - the warning is in the log either way
                pass
        self.server = ServerManager(self.settings, self.paths, self.log)
        self.plugin_dir = Path(__file__).resolve().parent.parent
        try:
            self.catalog = cat.load_merged(plugin_dir=self.plugin_dir, base=self.paths.base)
        except cat.CatalogError as err:
            self.log.warning("catalog unavailable: %s", err)
            self.catalog = []

    # paths ---------------------------------------------------------------

    @property
    def models_root(self) -> Path:
        return cat.default_models_root(self.settings.comfy_dir)

    @property
    def custom_nodes_dir(self) -> Path:
        return cat.default_custom_nodes_dir(self.settings.comfy_dir)

    # backend -------------------------------------------------------------

    def backend(self, progress=None, cancel=None) -> Backend:
        url = self.server.ensure_running(progress, cancel)
        timeout = float(self.settings.request_timeout or 0)
        if self.settings.backend == "a1111":
            return A1111Backend(url, timeout, self.log)
        return ComfyBackend(url, request_timeout=timeout, logger=self.log)

    def refresh_models_cache(self, health: HealthStatus) -> None:
        if not health.ok:
            return
        data = {
            "updated": time.time(),
            "checkpoints": health.checkpoints,
            "fooocus_heads": health.fooocus_heads,
            "fooocus_patches": health.fooocus_patches,
            "inpaint_nodes": health.inpaint_nodes,
            "version": health.version,
        }
        try:
            self.paths.models_cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def server_model_files(self) -> list[str] | None:
        """Model files the running server lists (None when it is not up)."""
        if self.settings.backend != "comfyui":
            return None
        client = ComfyClient(self.server.url(), timeout=5)
        if not client.is_alive(timeout=2.0):
            return None
        names: list[str] = []
        for node, inp in MODEL_LIST_NODES:
            try:
                names += client.combo_options(node, inp)
            except ComfyApiError:
                pass
        return names

    # models --------------------------------------------------------------

    def resolve_model(self, choice: str | None) -> tuple[cat.ModelEntry | None, ModelSpec]:
        """Map a dialog choice ('active', a legacy tier or a catalog id) to a model."""
        self.require_backend_install()
        choice = (choice or "active").strip()
        model_id = self.settings.active_model if choice == "active" else LEGACY_CHOICES.get(choice, choice)
        try:
            entry = cat.by_id(self.catalog, model_id)
        except cat.CatalogError:
            if choice in LEGACY_CHOICES or not self.catalog:
                return None, self.settings.model_for("quality" if choice == "quality" else "fast")
            raise ModelMissing(f"unknown model '{model_id}'; pick one in {SETTINGS_MENU} > Models") from None
        if not entry.runnable:
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' is a companion file, not a model you can generate with"
            )
        status = cat.install_status(entry, self.models_root, self.custom_nodes_dir, self.catalog)
        if not status.installed:
            if not self.has_model_for("fill"):
                raise ModelMissing(cat.NO_MODEL_MESSAGE)
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' is not downloaded yet. Open Filters > AI > Generative Fill "
                "Settings > Models and press Download."
            )
        if status.missing_models:
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' also needs {', '.join(status.missing_models)}; download it from the Models tab."
            )
        if status.missing_nodes:
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' needs the custom node pack(s) {', '.join(status.missing_nodes)}; "
                "press Install nodes in the Models tab."
            )
        return entry, cat.model_spec_for(entry, self.catalog)

    def profile_for(self, model: ModelSpec) -> geometry.ModelProfile:
        base = geometry.PROFILES.get(model.arch, geometry.SD15)
        if model.arch == "sd15":
            max_side = self.settings.max_side_sd15
        elif model.arch == "inpaint_model":
            max_side = base.max_side
        else:
            max_side = self.settings.max_side_sdxl
        return replace(base, max_side=max(base.min_side, int(max_side)))

    def sampling(self, model: ModelSpec, variations: int, seed: int, denoise: float | None = None) -> Sampling:
        steps, cfg = int(self.settings.steps), float(self.settings.cfg)
        sampler, scheduler = self.settings.sampler, self.settings.scheduler
        if model.arch == "flux":
            cfg, sampler, scheduler, steps = 30.0, "euler", "normal", max(20, min(steps, 30))
        elif model.arch == "qwen_image":
            cfg, sampler, scheduler, steps = 2.5, "euler", "simple", max(20, min(steps, 30))
        batch = 1 if model.prompt_free else max(1, min(8, int(variations)))
        return Sampling(
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=float(self.settings.denoise if denoise is None else denoise),
            seed=int(seed),
            batch=batch,
        )

    def require_backend_install(self) -> None:
        """With the managed ComfyUI backend, a missing ComfyUI folder is the real
        problem; report it before any model check (which would otherwise say a
        model is missing). A server that answers anyway (started by hand) is fine."""
        if self.settings.backend != "comfyui" or comfy_layout(self.settings.comfy_dir) is not None:
            return
        if ComfyClient(self.server.url(), timeout=3).is_alive(timeout=2.0):
            return
        raise BackendUnavailable(
            f"ComfyUI was not found in '{self.settings.comfy_dir}'. Set the ComfyUI folder in {SETTINGS_MENU}, "
            "or install ComfyUI there (see the README, Install)."
        )

    def model_rows(self, server_files: list[str] | None = None) -> list[dict]:
        self.require_backend_install()
        rows = []
        for e in self.catalog:
            st = cat.install_status(e, self.models_root, self.custom_nodes_dir, self.catalog, server_files)
            label = st.label
            if label == "Available" and e.gated and not self.settings.hf_token:
                label = "Needs token"
            rows.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "tier": e.tier,
                    "status": label,
                    "installed": st.installed,
                    "size": cat.human_size(e.total_size),
                    "bytes": e.total_size,
                    "license": e.license_name,
                    "license_url": e.license_url,
                    "page": e.page,
                    "source": "first-party" if e.source_type == "first-party" else "community quant",
                    "uploader": e.uploader,
                    "gated": e.gated,
                    "runnable": e.runnable,
                    "active": e.id == self.settings.active_model,
                    "min_vram_gb": e.min_vram_gb,
                    "missing_nodes": st.missing_nodes,
                    "missing_models": st.missing_models,
                    "partial": st.partial,
                    "capabilities": list(e.capabilities),
                    "seen_by_server": st.seen_by_server,
                }
            )
        return rows

    def set_active(self, model_id: str) -> cat.ModelEntry:
        entry = cat.by_id(self.catalog, model_id)
        if not entry.runnable:
            raise ModelMissing(f"'{model_display_name(entry.name)}' cannot be the active model (companion file)")
        self.settings.active_model = model_id
        self._save_settings()
        self.log.info("active model set to %s", model_id)
        return entry

    def save_token(self, token: str) -> None:
        self.settings.hf_token = token.strip()
        self._save_settings()

    def _save_settings(self) -> None:
        """Save, turning a refused or failed write into a message the user can act on."""
        try:
            self.settings.save(self.paths.config)
        except OSError as err:
            self.log.error("settings not saved: %s", err)
            raise BackendError(f"The settings could not be saved: {err}") from err

    def has_model_for(self, operation: str) -> bool:
        """True when a downloaded model can run ``operation`` (fill, expand, txt2img, remove, edit)."""
        return bool(cat.runnable_installed(self.catalog, self.models_root, self.custom_nodes_dir, operation))

    def queue_download(self, model_id: str, include_dependencies: bool = True) -> list[str]:
        entry = cat.by_id(self.catalog, model_id)
        if cat.gated_files_missing(entry, self.models_root) and not self.settings.hf_token:
            pages = ", ".join(cat.login_pages(entry, self.models_root)) or entry.page
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' needs a free Hugging Face login: accept the license at {pages} "
                "and paste your access key in the Models tab (the Download button shows the steps)."
            )
        self.models_root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.models_root).free
        need = sum(f.size or 0 for f in entry.files if not cat.file_installed(self.models_root, f))
        if need and free < need + 512 * 1024 * 1024:
            raise ModelMissing(
                f"not enough disk space for '{model_display_name(entry.name)}': needs {cat.human_size(need)}, {cat.human_size(free)} free"
            )
        ids = []
        if include_dependencies:
            for dep in entry.requires_models:
                dep_entry = cat.by_id(self.catalog, dep)
                if not cat.install_status(dep_entry, self.models_root, None).installed:
                    ids += self.queue_download(dep, include_dependencies=False)
        task = {
            "type": "download",
            "model_id": entry.id,
            "models_root": str(self.models_root),
            "use_token": entry.gated,
            "files": [
                {
                    "url": f.url,
                    "dest": f.dest,
                    "size": f.size,
                    "sha256": f.sha256,
                    "gated": f.gated,
                    "optional": f.optional,
                    "role": f.role,
                }
                for f in entry.files
            ],
        }
        ids.append(self.server.queue_task(task))
        return ids

    def queue_node_install(self, model_id: str) -> str | None:
        entry = cat.by_id(self.catalog, model_id)
        layout = comfy_layout(self.settings.comfy_dir)
        if layout is None:
            raise ModelMissing(f"ComfyUI was not found at '{self.settings.comfy_dir}'")
        nodes = [
            n
            for n in entry.requires_nodes
            if not cat.file_installed(self.custom_nodes_dir, cat.FileSpec("", "", n.folder))
            and not (self.custom_nodes_dir / n.folder).is_dir()
        ]
        if not nodes:
            return None
        task = {
            "type": "install_nodes",
            "model_id": entry.id,
            "custom_nodes_dir": str(self.custom_nodes_dir),
            "python": str(layout["python"]),
            "restart_backend": True,
            "nodes": [{"repo": n.repo, "folder": n.folder, "commit": n.commit} for n in nodes],
        }
        return self.server.queue_task(task)

    def nodes_to_install(self, model_id: str) -> list[cat.NodeSpec]:
        entry = cat.by_id(self.catalog, model_id)
        return [n for n in entry.requires_nodes if not (self.custom_nodes_dir / n.folder).is_dir()]

    def remove_model(self, model_id: str) -> str:
        entry = cat.by_id(self.catalog, model_id)
        shared = {
            f.dest
            for e in self.catalog
            if e.id != model_id
            for f in e.files
            if cat.install_status(e, self.models_root, None).installed
        }
        files = [f.dest for f in entry.files if f.dest not in shared]
        task = {"type": "remove", "model_id": entry.id, "models_root": str(self.models_root), "files": files}
        return self.server.queue_task(task)

    def open_models_folder(self) -> None:
        path = self.models_root
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def task_status(self) -> dict:
        return self.server.task_status()

    # features ------------------------------------------------------------

    REMOVAL_PROMPT = (
        "seamless continuation of the surrounding background, same material, texture, "
        "lighting and color as the area around it, nothing added"
    )
    REMOVAL_NEGATIVE = "object, button, logo, text, watermark, person, blurry, smudge, artifacts, seam"

    def removal_model_available(self) -> cat.ModelEntry | None:
        """An installed prompt-free removal model (LaMa/MAT), best first."""
        for mid in ("mat-places512", "lama-big"):
            try:
                entry = cat.by_id(self.catalog, mid)
            except cat.CatalogError:
                continue
            st = cat.install_status(entry, self.models_root, self.custom_nodes_dir, self.catalog)
            if st.installed and not st.missing_nodes:
                return entry
        return None

    def generative_fill(
        self,
        image,
        prompt: str,
        negative: str,
        variations: int,
        strength: float,
        seed: int,
        model_choice: str,
        remove: bool = False,
    ) -> list:
        # Checked before anything else (no backend start, no model lookup): without a
        # selection there is nothing to fill, and filling the whole image is never
        # what was meant.
        self._check_image(image)
        selection = gimp_io.selection_rect(image)
        if selection is None:
            self.log.info("fill: refused, nothing selected")
            raise NothingSelected(NO_SELECTION_MESSAGE)
        if remove:
            removal = self.removal_model_available()
            if removal is not None:
                self.log.info("fill: Remove object -> using %s", removal.id)
                model_choice = removal.id
            else:
                self.log.info(
                    "fill: Remove object requested but no LaMa/MAT installed; using %s with a background prompt",
                    model_choice,
                )
        entry, model = self.resolve_model(model_choice)
        profile = self.profile_for(model)
        full = gimp_io.image_rect(image)
        target = selection
        removal_intent = remove or not prompt.strip() or model.prompt_free
        ctx = geometry.context_rect(
            target, full, profile, padding_ratio=geometry.fill_padding(removal_intent, model.prompt_free)
        )
        ws = geometry.working_size(
            ctx.width, ctx.height, geometry.fill_profile(profile, ctx, model.arch, removal_intent)
        )
        mp = geometry.mask_params(
            target,
            ws.scale,
            self.settings.grow_percent,
            self.settings.feather_percent,
            self.settings.grow,
            self.settings.feather,
        )
        layer_grow = geometry.layer_mask_grow(mp, removal_intent)
        color_match = geometry.color_match_strength(target, ctx, full, removal_intent)
        prefill_style, prefill_mode = geometry.prefill_for(removal_intent, strength, model.arch)
        if model.prompt_free:
            prompt, negative = "", ""
        elif removal_intent:
            # Empty prompt on a generation model: ask for background, not "anything".
            prompt = self.REMOVAL_PROMPT
            negative = (negative + ", " if negative.strip() else "") + self.REMOVAL_NEGATIVE
            strength = 1.0
        self.log.info(
            "fill: selection=%s context=%s working=%dx%d scale=%.2f mask(grow=%d/%dpx feather=%d/%dpx "
            "layer grow=%dpx) prefill=%s/%s color_match=%.1f model=%s template=%s",
            target,
            ctx,
            ws.width,
            ws.height,
            ws.scale,
            mp.grow_image,
            mp.grow_work,
            mp.feather_image,
            mp.blur_work,
            layer_grow,
            prefill_style,
            prefill_mode,
            color_match,
            entry.id if entry else model.checkpoint,
            model.effective_template,
        )
        image_png = gimp_io.export_region_png(image, ctx)
        mask_png = gimp_io.export_selection_mask_png(image, ctx)
        request = InpaintRequest(
            image_png=image_png,
            mask_png=mask_png,
            width=ctx.width,
            height=ctx.height,
            work_width=ws.width,
            work_height=ws.height,
            prompt=prompt,
            negative=negative,
            model=model,
            sampling=self.sampling(model, variations, seed, strength),
            mode="fill",
            grow=mp.grow_work,
            feather=mp.blur_work,
            prefill=self.settings.prefill,
            prefill_style=prefill_style,
            prefill_mode=prefill_mode,
            color_match=color_match,
        )
        title = "Object Removal" if model.prompt_free else "Generative Fill"
        runner = Runner(
            self, title, model_display_name(entry.name) if entry else model.checkpoint, interactive=self.interactive
        )
        try:
            result = runner.run(
                lambda progress, preview, cancel: self.backend(progress, cancel).inpaint(
                    request, progress, preview, cancel
                )
            )
            self.server.touch()
            self._debug_dump("fill", request, result, ctx)
            layers = gimp_io.insert_results(
                image,
                result.images,
                ctx,
                _layer_name(title, prompt),
                float(mp.feather_image),
                self.paths.temp,
                grow=layer_grow,
            )
        except BaseException as err:
            runner.fail(err)
            raise
        runner.done(f"Added layer: {layers[0].get_name()}" if layers else "Done")
        self.log.info("fill: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def generative_expand(
        self,
        image,
        prompt: str,
        negative: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
        variations: int,
        seed: int,
        model_choice: str,
    ) -> list:
        """Grow the canvas by the given margins and generate the new area.

        Every growing side is rendered in the same pass, with the whole canvas
        as context. Large expansions run in rounds (``geometry.expand_rounds``),
        each again all sides at once; each round reads the visible result of
        the previous one and only the last makes the requested variations.
        """
        self._check_image(image)
        entry, model = self.resolve_model(model_choice)
        rounds = geometry.expand_rounds(image.get_width(), image.get_height(), left, top, right, bottom)
        if len(rounds) == 1:
            return self._expand_round(image, prompt, negative, rounds[0], variations, seed, entry, model)
        self.log.info("expand: margins=%s in %d rounds: %s", (left, top, right, bottom), len(rounds), rounds)
        layers: list = []
        image.undo_group_start()
        try:
            for index, margins in enumerate(rounds):
                count = variations if index == len(rounds) - 1 else 1
                layers = self._expand_round(image, prompt, negative, margins, count, seed, entry, model)
        finally:
            image.undo_group_end()
        return layers

    def _expand_round(
        self,
        image,
        prompt: str,
        negative: str,
        margins: tuple[int, int, int, int],
        variations: int,
        seed: int,
        entry: cat.ModelEntry | None,
        model: ModelSpec,
    ) -> list:
        """One expand pass: all margins at once."""
        left, top, right, bottom = margins
        profile = self.profile_for(model)
        plan = geometry.plan_expand(image.get_width(), image.get_height(), left, top, right, bottom, profile)
        ws = geometry.working_size(plan.context.width, plan.context.height, profile)
        mp = geometry.mask_params(
            plan.fill_rect,
            ws.scale,
            self.settings.grow_percent,
            self.settings.feather_percent,
            self.settings.grow,
            self.settings.feather,
        )
        if model.prompt_free:
            prompt, negative = "", ""
        else:
            prompt, negative = workflow.expand_prompts(prompt, negative)
        sampling = self.sampling(model, variations, seed, 1.0)
        sampling = replace(sampling, cfg=workflow.expand_cfg(model.arch, sampling.cfg))
        self.log.info(
            "expand: margins=%s canvas=%dx%d context=%s working=%dx%d model=%s prompt=%s cfg=%.1f",
            (left, top, right, bottom),
            plan.new_width,
            plan.new_height,
            plan.context,
            ws.width,
            ws.height,
            entry.id if entry else model.checkpoint,
            "user" if prompt else "continue the scene",
            sampling.cfg,
        )
        # Read the context from the unresized image (new-canvas coordinates shifted
        # back by the offset; pixels outside the image come back transparent) so a
        # backend failure leaves the image untouched. The canvas grows only on success.
        source_rect = plan.context.translate(-plan.offset_x, -plan.offset_y)
        image_png = gimp_io.export_region_png(image, source_rect, transparent_outside=True)
        mask_pixels = geometry.mask_for_expand(plan)
        mask_png = gimp_io.mask_png_from_bytes(plan.context, mask_pixels)
        request = InpaintRequest(
            image_png=image_png,
            mask_png=mask_png,
            width=plan.context.width,
            height=plan.context.height,
            work_width=ws.width,
            work_height=ws.height,
            prompt=prompt,
            negative=negative,
            model=model,
            sampling=sampling,
            mode="expand",
            grow=mp.grow_work,
            feather=mp.blur_work,
            prefill=True,
        )
        runner = Runner(
            self,
            "Generative Expand",
            model_display_name(entry.name) if entry else model.checkpoint,
            interactive=self.interactive,
        )
        try:
            result = runner.run(
                lambda progress, preview, cancel: self.backend(progress, cancel).outpaint(
                    request, progress, preview, cancel
                )
            )
            self.server.touch()
            image.undo_group_start()
            try:
                gimp_io.resize_canvas(image, plan.new_width, plan.new_height, plan.offset_x, plan.offset_y)
                layers = gimp_io.insert_results(
                    image,
                    result.images,
                    plan.context,
                    _layer_name("Generative Expand", prompt),
                    float(mp.feather_image),
                    self.paths.temp,
                    mask_pixels=mask_pixels,
                )
            finally:
                image.undo_group_end()
        except BaseException as err:
            runner.fail(err)
            raise
        runner.done(f"Canvas is now {plan.new_width} x {plan.new_height}")
        self.log.info("expand: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def text_to_image(
        self,
        image,
        prompt: str,
        negative: str,
        width: int,
        height: int,
        variations: int,
        seed: int,
        model_choice: str,
        target: str,
    ) -> None:
        if image is not None and target == "layer":
            self._check_image(image)
        entry, model = self.resolve_model(model_choice)
        if entry is not None and "txt2img" not in entry.capabilities:
            raise ModelMissing(
                f"'{model_display_name(entry.name)}' does not support Text to Image; pick an SD 1.5 or SDXL model"
            )
        profile = self.profile_for(model)
        origin = Rect(0, 0, 0, 0)
        if image is not None and target == "layer":
            selection = gimp_io.selection_rect(image)
            if selection is not None and (width <= 0 or height <= 0):
                origin = selection
                width, height = selection.width, selection.height
        if width <= 0 or height <= 0:
            width, height = self.settings.txt2img_width, self.settings.txt2img_height
        ws = geometry.working_size(width, height, profile)
        request = Txt2ImgRequest(
            ws.width, ws.height, prompt, negative, model, self.sampling(model, variations, seed, 1.0)
        )
        self.log.info("txt2img: %dx%d model=%s target=%s", ws.width, ws.height, model.checkpoint, target)
        runner = Runner(
            self,
            "Text to Image",
            model_display_name(entry.name) if entry else model.checkpoint,
            interactive=self.interactive,
        )
        try:
            result = runner.run(
                lambda progress, preview, cancel: self.backend(progress, cancel).txt2img(
                    request, progress, preview, cancel
                )
            )
            self.server.touch()
            name = _layer_name("Text to Image", prompt)
            if image is None or target == "image":
                gimp_io.new_image_from_pngs(result.images, name, self.paths.temp)
            else:
                # generated at the model's working size; the layer gets the requested size
                gimp_io.insert_results(
                    image,
                    result.images,
                    Rect(origin.x, origin.y, width, height),
                    name,
                    0.0,
                    self.paths.temp,
                    use_selection_mask=False,
                    scale_to_origin=True,
                )
        except BaseException as err:
            runner.fail(err)
            raise
        runner.done("Done")
        self.log.info("txt2img: done, seed=%s", result.seed)

    def _check_image(self, image) -> None:
        if gimp_io.is_indexed(image):
            self.log.info("refused: indexed image")
            raise UnsupportedImage(INDEXED_MESSAGE)

    def _debug_dump(self, kind: str, request: InpaintRequest, result, rect: Rect) -> None:
        """With debug on (settings or SB_DEBUG_DUMP=1) keep the exact bytes exchanged
        with the backend next to a JSON description, for bug reports."""
        if not (self.settings.debug or os.environ.get("SB_DEBUG_DUMP") == "1"):
            return
        try:
            folder = self.paths.temp / f"debug-{kind}-{time.strftime('%Y%m%d-%H%M%S')}"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "sent-image.png").write_bytes(request.image_png)
            (folder / "sent-mask.png").write_bytes(request.mask_png)
            for i, data in enumerate(result.images):
                (folder / f"result-{i}.png").write_bytes(data)
            info = {
                "rect": [rect.x, rect.y, rect.width, rect.height],
                "work": [request.work_width, request.work_height],
                "mode": request.mode,
                "grow": request.grow,
                "feather": request.feather,
                "prefill": request.prefill,
                "prompt": request.prompt,
                "negative": request.negative,
                "model": request.model.__dict__,
                "sampling": request.sampling.__dict__,
                "seed": result.seed,
                "layer_feather": self.settings.feather,
                "graph_classes": sorted({n["class_type"] for n in (result.info.get("graph") or {}).values()}),
            }
            (folder / "request.json").write_text(json.dumps(info, indent=2, default=str), encoding="utf-8")
            self.log.info("debug dump: %s", folder)
        except Exception as err:  # noqa: BLE001
            self.log.warning("debug dump failed: %s", err)

    def check_backend(self) -> HealthStatus:
        try:
            backend = self.backend(gimp_io.GimpProgress("Checking the AI backend"))
        except BackendError as err:
            return HealthStatus(False, str(err))
        health = backend.health()
        self.refresh_models_cache(health)
        return health

    def stop_backend(self) -> str:
        state = self.server.read_state()
        if not state:
            return "No managed backend is running."
        if self.server.request_stop():
            return f"Asked the AI backend (pid {state.get('server_pid')}) to shut down."
        return "Could not write the stop request."

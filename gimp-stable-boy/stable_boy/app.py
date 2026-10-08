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
from . import geometry, gimp_io
from .backend import (Backend, BackendError, HealthStatus, InpaintRequest, ModelMissing, ModelSpec,
                      Sampling, Txt2ImgRequest)
from .backends.a1111 import A1111Backend
from .backends.comfy import ComfyBackend
from .comfy_api import ComfyApiError, ComfyClient
from .config import Paths, Settings, comfy_layout
from .geometry import Rect
from .log import get_logger
from .server import ServerManager

LEGACY_CHOICES = {"fast": "sd15-inpainting", "quality": "sdxl-base"}
MODEL_LIST_NODES = (("CheckpointLoaderSimple", "ckpt_name"), ("UNETLoader", "unet_name"),
                    ("UnetLoaderGGUF", "unet_name"), ("INPAINT_LoadInpaintModel", "model_name"))


def _layer_name(kind: str, prompt: str) -> str:
    text = " ".join(prompt.split())[:48].strip()
    return f"{kind}: {text}" if text else kind


class App:
    def __init__(self) -> None:
        self.paths = Paths.for_profile(gimp_io.profile_dir()).ensure()
        self.settings = Settings.load(self.paths.config)
        self.log = get_logger(self.paths.log, debug=self.settings.debug)
        self.server = ServerManager(self.settings, self.paths, self.log)
        self.plugin_dir = Path(__file__).resolve().parent.parent
        try:
            self.catalog = cat.load_catalog(plugin_dir=self.plugin_dir)
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

    def backend(self, progress=None) -> Backend:
        url = self.server.ensure_running(progress)
        timeout = float(self.settings.request_timeout or 0)
        if self.settings.backend == "a1111":
            return A1111Backend(url, timeout, self.log)
        return ComfyBackend(url, request_timeout=timeout, logger=self.log)

    def refresh_models_cache(self, health: HealthStatus) -> None:
        if not health.ok:
            return
        data = {"updated": time.time(), "checkpoints": health.checkpoints,
                "fooocus_heads": health.fooocus_heads, "fooocus_patches": health.fooocus_patches,
                "inpaint_nodes": health.inpaint_nodes, "version": health.version}
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
        choice = (choice or "active").strip()
        model_id = self.settings.active_model if choice == "active" else LEGACY_CHOICES.get(choice, choice)
        try:
            entry = cat.by_id(self.catalog, model_id)
        except cat.CatalogError:
            if choice in LEGACY_CHOICES or not self.catalog:
                return None, self.settings.model_for("quality" if choice == "quality" else "fast")
            raise ModelMissing(f"unknown model '{model_id}'; pick one in Filters > AI > Generative Fill Settings > Models")
        if not entry.runnable:
            raise ModelMissing(f"'{entry.name}' is a companion file, not a model you can generate with")
        status = cat.install_status(entry, self.models_root, self.custom_nodes_dir, self.catalog)
        if not status.installed:
            raise ModelMissing(f"'{entry.name}' is not downloaded yet. Open Filters > AI > Generative Fill "
                               "Settings > Models and press Download.")
        if status.missing_models:
            raise ModelMissing(f"'{entry.name}' also needs {', '.join(status.missing_models)}; download it from the Models tab.")
        if status.missing_nodes:
            raise ModelMissing(f"'{entry.name}' needs the custom node pack(s) {', '.join(status.missing_nodes)}; "
                               "press Install nodes in the Models tab.")
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
        return Sampling(steps=steps, cfg=cfg, sampler=sampler, scheduler=scheduler,
                        denoise=float(self.settings.denoise if denoise is None else denoise),
                        seed=int(seed), batch=batch)

    def model_rows(self, server_files: list[str] | None = None) -> list[dict]:
        rows = []
        for e in self.catalog:
            st = cat.install_status(e, self.models_root, self.custom_nodes_dir, self.catalog, server_files)
            label = st.label
            if label == "Available" and e.gated and not self.settings.hf_token:
                label = "Needs token"
            rows.append({"id": e.id, "name": e.name, "tier": e.tier, "status": label, "installed": st.installed,
                         "size": cat.human_size(e.total_size), "bytes": e.total_size,
                         "license": e.license_name, "license_url": e.license_url, "page": e.page,
                         "source": "first-party" if e.source_type == "first-party" else "community quant",
                         "uploader": e.uploader, "gated": e.gated, "runnable": e.runnable,
                         "active": e.id == self.settings.active_model, "min_vram_gb": e.min_vram_gb,
                         "missing_nodes": st.missing_nodes, "missing_models": st.missing_models,
                         "partial": st.partial, "capabilities": list(e.capabilities),
                         "seen_by_server": st.seen_by_server})
        return rows

    def set_active(self, model_id: str) -> cat.ModelEntry:
        entry = cat.by_id(self.catalog, model_id)
        if not entry.runnable:
            raise ModelMissing(f"'{entry.name}' cannot be the active model (companion file)")
        self.settings.active_model = model_id
        self.settings.save(self.paths.config)
        self.log.info("active model set to %s", model_id)
        return entry

    def save_token(self, token: str) -> None:
        self.settings.hf_token = token.strip()
        self.settings.save(self.paths.config)

    def queue_download(self, model_id: str, include_dependencies: bool = True) -> list[str]:
        entry = cat.by_id(self.catalog, model_id)
        if entry.gated and not self.settings.hf_token:
            raise ModelMissing(f"'{entry.name}' is gated on Hugging Face. Accept the license at {entry.page} "
                               "and enter your access token (huggingface.co/settings/tokens) in the Models tab.")
        self.models_root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.models_root).free
        need = sum(f.size or 0 for f in entry.files if not cat.file_installed(self.models_root, f))
        if need and free < need + 512 * 1024 * 1024:
            raise ModelMissing(f"not enough disk space for '{entry.name}': needs {cat.human_size(need)}, "
                               f"{cat.human_size(free)} free")
        ids = []
        if include_dependencies:
            for dep in entry.requires_models:
                dep_entry = cat.by_id(self.catalog, dep)
                if not cat.install_status(dep_entry, self.models_root, None).installed:
                    ids += self.queue_download(dep, include_dependencies=False)
        task = {"type": "download", "model_id": entry.id, "models_root": str(self.models_root),
                "use_token": entry.gated,
                "files": [{"url": f.url, "dest": f.dest, "size": f.size, "sha256": f.sha256,
                           "gated": f.gated, "optional": f.optional, "role": f.role} for f in entry.files]}
        ids.append(self.server.queue_task(task))
        return ids

    def queue_node_install(self, model_id: str) -> str | None:
        entry = cat.by_id(self.catalog, model_id)
        layout = comfy_layout(self.settings.comfy_dir)
        if layout is None:
            raise ModelMissing(f"ComfyUI was not found at '{self.settings.comfy_dir}'")
        nodes = [n for n in entry.requires_nodes if not cat.file_installed(self.custom_nodes_dir, cat.FileSpec("", "", n.folder))
                 and not (self.custom_nodes_dir / n.folder).is_dir()]
        if not nodes:
            return None
        task = {"type": "install_nodes", "model_id": entry.id, "custom_nodes_dir": str(self.custom_nodes_dir),
                "python": str(layout["python"]), "restart_backend": True,
                "nodes": [{"repo": n.repo, "folder": n.folder, "commit": n.commit} for n in nodes]}
        return self.server.queue_task(task)

    def nodes_to_install(self, model_id: str) -> list[cat.NodeSpec]:
        entry = cat.by_id(self.catalog, model_id)
        return [n for n in entry.requires_nodes if not (self.custom_nodes_dir / n.folder).is_dir()]

    def remove_model(self, model_id: str) -> str:
        entry = cat.by_id(self.catalog, model_id)
        shared = {f.dest for e in self.catalog if e.id != model_id for f in e.files
                  if cat.install_status(e, self.models_root, None).installed}
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

    def generative_fill(self, image, prompt: str, negative: str, variations: int,
                        strength: float, seed: int, model_choice: str) -> list:
        entry, model = self.resolve_model(model_choice)
        profile = self.profile_for(model)
        full = gimp_io.image_rect(image)
        selection = gimp_io.selection_rect(image)
        target = selection or full
        ctx = geometry.context_rect(target, full, profile)
        ws = geometry.working_size(ctx.width, ctx.height, profile)
        if model.prompt_free:
            prompt, negative = "", ""
        self.log.info("fill: selection=%s context=%s working=%dx%d model=%s template=%s", target, ctx,
                      ws.width, ws.height, entry.id if entry else model.checkpoint, model.effective_template)
        image_png = gimp_io.export_region_png(image, ctx)
        if selection is not None:
            mask_png = gimp_io.export_selection_mask_png(image, ctx)
        else:
            mask_png = gimp_io.mask_png_from_bytes(ctx, b"\xff" * ctx.area)
        request = InpaintRequest(
            image_png=image_png, mask_png=mask_png, width=ctx.width, height=ctx.height,
            work_width=ws.width, work_height=ws.height, prompt=prompt, negative=negative,
            model=model, sampling=self.sampling(model, variations, seed, strength), mode="fill",
            grow=max(0, round(self.settings.grow * ws.scale)),
            feather=max(0, round(self.settings.feather * ws.scale)),
            prefill=self.settings.prefill)
        title = "Object Removal" if model.prompt_free else "Generative Fill"
        progress = gimp_io.GimpProgress(title)
        try:
            backend = self.backend(progress)
            result = backend.inpaint(request, progress)
        finally:
            progress.done()
        self.server.touch()
        layers = gimp_io.insert_results(image, result.images, ctx, _layer_name(title, prompt),
                                        float(self.settings.feather), self.paths.temp)
        self.log.info("fill: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def generative_expand(self, image, prompt: str, negative: str, left: int, top: int,
                          right: int, bottom: int, variations: int, seed: int, model_choice: str) -> list:
        entry, model = self.resolve_model(model_choice)
        profile = self.profile_for(model)
        plan = geometry.plan_expand(image.get_width(), image.get_height(), left, top, right, bottom,
                                    profile)
        ws = geometry.working_size(plan.context.width, plan.context.height, profile)
        if model.prompt_free:
            prompt, negative = "", ""
        self.log.info("expand: margins=%s canvas=%dx%d context=%s working=%dx%d model=%s",
                      (left, top, right, bottom), plan.new_width, plan.new_height, plan.context,
                      ws.width, ws.height, entry.id if entry else model.checkpoint)
        # Read the context from the unresized image (new-canvas coordinates shifted
        # back by the offset; pixels outside the image come back transparent) so a
        # backend failure leaves the image untouched. The canvas grows only on success.
        source_rect = plan.context.translate(-plan.offset_x, -plan.offset_y)
        image_png = gimp_io.export_region_png(image, source_rect, transparent_outside=True)
        mask_pixels = geometry.mask_for_expand(plan)
        mask_png = gimp_io.mask_png_from_bytes(plan.context, mask_pixels)
        request = InpaintRequest(
            image_png=image_png, mask_png=mask_png, width=plan.context.width,
            height=plan.context.height, work_width=ws.width, work_height=ws.height,
            prompt=prompt, negative=negative, model=model,
            sampling=self.sampling(model, variations, seed, 1.0), mode="expand",
            grow=max(0, round(self.settings.grow * ws.scale)),
            feather=max(0, round(self.settings.feather * ws.scale)), prefill=True)
        progress = gimp_io.GimpProgress("Generative Expand")
        try:
            backend = self.backend(progress)
            result = backend.outpaint(request, progress)
        finally:
            progress.done()
        self.server.touch()
        image.undo_group_start()
        try:
            gimp_io.resize_canvas(image, plan.new_width, plan.new_height, plan.offset_x, plan.offset_y)
            layers = gimp_io.insert_results(image, result.images, plan.context,
                                            _layer_name("Generative Expand", prompt),
                                            float(self.settings.feather), self.paths.temp,
                                            mask_pixels=mask_pixels)
        finally:
            image.undo_group_end()
        self.log.info("expand: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def text_to_image(self, image, prompt: str, negative: str, width: int, height: int,
                      variations: int, seed: int, model_choice: str, target: str) -> None:
        entry, model = self.resolve_model(model_choice)
        if entry is not None and "txt2img" not in entry.capabilities:
            raise ModelMissing(f"'{entry.name}' does not support Text to Image; pick an SD 1.5 or SDXL model")
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
        request = Txt2ImgRequest(ws.width, ws.height, prompt, negative, model,
                                 self.sampling(model, variations, seed, 1.0))
        self.log.info("txt2img: %dx%d model=%s target=%s", ws.width, ws.height, model.checkpoint, target)
        progress = gimp_io.GimpProgress("Text to Image")
        try:
            backend = self.backend(progress)
            result = backend.txt2img(request, progress)
        finally:
            progress.done()
        self.server.touch()
        name = _layer_name("Text to Image", prompt)
        if image is None or target == "image":
            gimp_io.new_image_from_pngs(result.images, name, self.paths.temp)
        else:
            gimp_io.insert_results(image, result.images, Rect(origin.x, origin.y, ws.width, ws.height),
                                   name, 0.0, self.paths.temp, use_selection_mask=False)
        self.log.info("txt2img: done, seed=%s", result.seed)

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

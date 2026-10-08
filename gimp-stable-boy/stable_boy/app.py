# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Orchestration: GIMP image in, backend request out, layers back in.

This module imports ``gimp_io`` (and therefore ``gi``); everything below it
is plain Python.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace

from . import geometry, gimp_io
from .backend import (Backend, BackendError, HealthStatus, InpaintRequest, ModelSpec, Sampling,
                      Txt2ImgRequest)
from .backends.a1111 import A1111Backend
from .backends.comfy import ComfyBackend
from .config import Paths, Settings
from .geometry import Rect
from .log import get_logger
from .server import ServerManager


def _layer_name(kind: str, prompt: str) -> str:
    text = " ".join(prompt.split())[:48].strip()
    return f"{kind}: {text}" if text else kind


class App:
    def __init__(self) -> None:
        self.paths = Paths.for_profile(gimp_io.profile_dir()).ensure()
        self.settings = Settings.load(self.paths.config)
        self.log = get_logger(self.paths.log, debug=self.settings.debug)
        self.server = ServerManager(self.settings, self.paths, self.log)

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

    def profile_for(self, model: ModelSpec) -> geometry.ModelProfile:
        base = geometry.SDXL if model.arch == "sdxl" else geometry.SD15
        max_side = self.settings.max_side_sdxl if model.arch == "sdxl" else self.settings.max_side_sd15
        return replace(base, max_side=max(base.min_side, int(max_side)))

    def sampling(self, variations: int, seed: int, denoise: float | None = None) -> Sampling:
        return Sampling(steps=int(self.settings.steps), cfg=float(self.settings.cfg),
                        sampler=self.settings.sampler, scheduler=self.settings.scheduler,
                        denoise=float(self.settings.denoise if denoise is None else denoise),
                        seed=int(seed), batch=max(1, min(8, int(variations))))

    # features ------------------------------------------------------------

    def generative_fill(self, image, prompt: str, negative: str, variations: int,
                        strength: float, seed: int, quality: str) -> list:
        model = self.settings.model_for(quality)
        profile = self.profile_for(model)
        full = gimp_io.image_rect(image)
        selection = gimp_io.selection_rect(image)
        target = selection or full
        ctx = geometry.context_rect(target, full, profile)
        ws = geometry.working_size(ctx.width, ctx.height, profile)
        self.log.info("fill: selection=%s context=%s working=%dx%d model=%s", target, ctx,
                      ws.width, ws.height, model.checkpoint)
        image_png = gimp_io.export_region_png(image, ctx)
        if selection is not None:
            mask_png = gimp_io.export_selection_mask_png(image, ctx)
        else:
            mask_png = gimp_io.mask_png_from_bytes(ctx, b"\xff" * ctx.area)
        request = InpaintRequest(
            image_png=image_png, mask_png=mask_png, width=ctx.width, height=ctx.height,
            work_width=ws.width, work_height=ws.height, prompt=prompt, negative=negative,
            model=model, sampling=self.sampling(variations, seed, strength), mode="fill",
            grow=max(0, round(self.settings.grow * ws.scale)),
            feather=max(0, round(self.settings.feather * ws.scale)),
            prefill=self.settings.prefill)
        progress = gimp_io.GimpProgress("Generative Fill")
        try:
            backend = self.backend(progress)
            result = backend.inpaint(request, progress)
        finally:
            progress.done()
        self.server.touch()
        layers = gimp_io.insert_results(image, result.images, ctx, _layer_name("Generative Fill", prompt),
                                        float(self.settings.feather), self.paths.temp)
        self.log.info("fill: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def generative_expand(self, image, prompt: str, negative: str, left: int, top: int,
                          right: int, bottom: int, variations: int, seed: int, quality: str) -> list:
        model = self.settings.model_for(quality)
        profile = self.profile_for(model)
        plan = geometry.plan_expand(image.get_width(), image.get_height(), left, top, right, bottom,
                                    profile)
        ws = geometry.working_size(plan.context.width, plan.context.height, profile)
        self.log.info("expand: margins=%s canvas=%dx%d context=%s working=%dx%d",
                      (left, top, right, bottom), plan.new_width, plan.new_height, plan.context,
                      ws.width, ws.height)
        image.undo_group_start()
        try:
            gimp_io.resize_canvas(image, plan.new_width, plan.new_height, plan.offset_x, plan.offset_y)
            image_png = gimp_io.export_region_png(image, plan.context)
        finally:
            image.undo_group_end()
        mask_pixels = geometry.mask_for_expand(plan)
        mask_png = gimp_io.mask_png_from_bytes(plan.context, mask_pixels)
        request = InpaintRequest(
            image_png=image_png, mask_png=mask_png, width=plan.context.width,
            height=plan.context.height, work_width=ws.width, work_height=ws.height,
            prompt=prompt, negative=negative, model=model,
            sampling=self.sampling(variations, seed, 1.0), mode="expand",
            grow=max(0, round(self.settings.grow * ws.scale)),
            feather=max(0, round(self.settings.feather * ws.scale)), prefill=True)
        progress = gimp_io.GimpProgress("Generative Expand")
        try:
            backend = self.backend(progress)
            result = backend.outpaint(request, progress)
        finally:
            progress.done()
        self.server.touch()
        layers = gimp_io.insert_results(image, result.images, plan.context,
                                        _layer_name("Generative Expand", prompt),
                                        float(self.settings.feather), self.paths.temp,
                                        mask_pixels=mask_pixels)
        self.log.info("expand: done, seed=%s, %d layer(s)", result.seed, len(layers))
        return layers

    def text_to_image(self, image, prompt: str, negative: str, width: int, height: int,
                      variations: int, seed: int, quality: str, target: str) -> None:
        model = self.settings.model_for(quality)
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
                                 self.sampling(variations, seed, 1.0))
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

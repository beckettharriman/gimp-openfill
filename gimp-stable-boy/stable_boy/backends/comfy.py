# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""ComfyUI backend: builds graphs, uploads inputs, streams progress."""

from __future__ import annotations

import time
import uuid

from .. import workflow
from ..backend import (Backend, BackendUnavailable, GenerationResult, GenerationTimeout,
                       HealthStatus, InpaintRequest, ModelMissing, OutOfMemory, Progress,
                       ProgressCallback, Txt2ImgRequest, WorkflowRejected)
from ..comfy_api import ComfyApiError, ComfyClient, ComfyExecutionError
from ..geometry import estimate_timeout, seed_or_random


class ComfyBackend(Backend):
    name = "comfyui"

    def __init__(self, url: str = "http://127.0.0.1:8188", client: ComfyClient | None = None,
                 request_timeout: float = 0.0, logger=None) -> None:
        self.url = url
        self.client = client or ComfyClient(url)
        self.request_timeout = request_timeout  # 0 = estimate per request
        self.log = logger
        self._caps: workflow.Capabilities | None = None
        self._progress = Progress()
        self._active_prompt: str | None = None

    # ------------------------------------------------------------------

    def capabilities(self, refresh: bool = False) -> workflow.Capabilities:
        if self._caps is None or refresh:
            info = self.client.object_info("INPAINT_ExpandMask")
            self._caps = workflow.Capabilities(inpaint_nodes=bool(info))
        return self._caps

    def health(self) -> HealthStatus:
        try:
            stats = self.client.system_stats()
        except ComfyApiError as err:
            return HealthStatus(False, str(err))
        devices = stats.get("devices") or [{}]
        version = str(stats.get("system", {}).get("comfyui_version", ""))
        try:
            checkpoints = self.client.combo_options("CheckpointLoaderSimple", "ckpt_name")
            caps = self.capabilities(refresh=True)
            heads = self.client.combo_options("INPAINT_LoadFooocusInpaint", "head") if caps.inpaint_nodes else []
            patches = self.client.combo_options("INPAINT_LoadFooocusInpaint", "patch") if caps.inpaint_nodes else []
        except ComfyApiError as err:
            return HealthStatus(False, f"server answered but node info failed: {err}", version)
        return HealthStatus(True, f"ComfyUI {version}", version, checkpoints, caps.inpaint_nodes,
                            heads, patches, int(devices[0].get("vram_total", 0)),
                            int(devices[0].get("vram_free", 0)))

    def progress(self) -> Progress:
        return self._progress

    def cancel(self) -> None:
        try:
            self.client.interrupt()
        except ComfyApiError:
            pass

    # ------------------------------------------------------------------

    def inpaint(self, request: InpaintRequest, progress: ProgressCallback | None = None) -> GenerationResult:
        caps = self.capabilities()
        if request.model.uses_fooocus and not caps.inpaint_nodes:
            raise ModelMissing("the Fooocus inpaint patch needs comfyui-inpaint-nodes on the server")
        seed = seed_or_random(request.sampling.seed)
        job = uuid.uuid4().hex[:12]
        self._report(progress, 0.0, "Uploading selection...")
        try:
            image_ref = self.client.upload_image(f"sb-{job}-image.png", request.image_png)
            mask_ref = self.client.upload_image(f"sb-{job}-mask.png", request.mask_png)
        except ComfyApiError as err:
            raise BackendUnavailable(f"upload failed: {err}") from err
        try:
            graph = workflow.build_fill(request, image_ref, mask_ref, seed, caps,
                                        filename_prefix=f"stable-boy/{request.mode}-{job}")
        except ValueError as err:
            raise WorkflowRejected(str(err)) from err
        pixels = request.work_width * request.work_height
        try:
            images = self._run(graph, request.sampling.steps, request.sampling.batch, pixels, progress)
        except WorkflowRejected as err:
            # The telea / navier-stokes pre-fill modes need OpenCV on the server.
            # Fall back to the dependency-free neutral fill instead of failing.
            if "cv2" not in str(err) or request.prefill_mode == "neutral":
                raise
            if self.log:
                self.log.warning("server has no OpenCV; retrying with neutral pre-fill")
            request.prefill_mode = "neutral"
            graph = workflow.build_inpaint(request, image_ref, mask_ref, seed, caps,
                                           filename_prefix=f"stable-boy/{request.mode}-{job}")
            images = self._run(graph, request.sampling.steps, request.sampling.batch, pixels, progress)
        return GenerationResult(images, seed, {"job": job, "graph": graph, "backend": self.name})

    def txt2img(self, request: Txt2ImgRequest, progress: ProgressCallback | None = None) -> GenerationResult:
        seed = seed_or_random(request.sampling.seed)
        job = uuid.uuid4().hex[:12]
        try:
            graph = workflow.build_txt2img(request, seed, filename_prefix=f"stable-boy/txt2img-{job}")
        except ValueError as err:
            raise WorkflowRejected(str(err)) from err
        images = self._run(graph, request.sampling.steps, request.sampling.batch,
                           request.width * request.height, progress)
        return GenerationResult(images, seed, {"job": job, "graph": graph, "backend": self.name})

    # ------------------------------------------------------------------

    def _run(self, graph: dict, steps: int, batch: int, pixels: int,
             progress: ProgressCallback | None) -> list[bytes]:
        timeout = self.request_timeout or estimate_timeout(steps, batch, pixels)
        deadline = time.monotonic() + timeout
        self._report(progress, 0.02, "Submitting workflow...")
        try:
            prompt_id = self.client.queue_prompt(graph)
        except ComfyApiError as err:
            raise self._translate_queue_error(err, graph) from err
        self._active_prompt = prompt_id
        self._progress = Progress(0.0, "queued", True)
        if self.log:
            self.log.info("queued prompt %s (timeout %.0fs, %d steps x %d)", prompt_id, timeout, steps, batch)
        try:
            entry = self.client.wait_for(prompt_id, workflow.total_steps(graph), deadline,
                                         self._wrap(progress))
        except ComfyExecutionError as err:
            if err.is_out_of_memory:
                raise OutOfMemory(str(err)) from err
            raise WorkflowRejected(f"{err.node_type or 'node'}: {err}") from err
        except ComfyApiError as err:
            if "timed out" in str(err):
                self.cancel()
                raise GenerationTimeout(f"no result after {timeout:.0f} s") from err
            raise BackendUnavailable(str(err)) from err
        finally:
            self._active_prompt = None
            self._progress = Progress(1.0, "done", False)
        self._report(progress, 0.99, "Downloading result...")
        try:
            images = self.client.output_images(entry, workflow.OUTPUT_NODE)
        except ComfyApiError as err:
            raise BackendUnavailable(f"could not download the result: {err}") from err
        if not images:
            raise WorkflowRejected("the workflow finished without producing an image")
        return images

    def _wrap(self, progress: ProgressCallback | None) -> ProgressCallback:
        def cb(fraction: float, text: str) -> None:
            self._progress = Progress(fraction, text, fraction < 1.0)
            if progress:
                progress(fraction, text)
        return cb

    @staticmethod
    def _report(progress: ProgressCallback | None, fraction: float, text: str) -> None:
        if progress:
            progress(fraction, text)

    @staticmethod
    def _translate_queue_error(err: ComfyApiError, graph: dict) -> Exception:
        if err.node_errors:
            text = workflow.describe_node_errors(err.node_errors, graph)
            lowered = text.lower()
            if "not in list" in lowered or "invalid" in lowered and ("ckpt" in lowered or "patch" in lowered or "head" in lowered):
                return ModelMissing(text)
            return WorkflowRejected(text)
        if err.status == 0:
            return BackendUnavailable(str(err))
        return WorkflowRejected(str(err))

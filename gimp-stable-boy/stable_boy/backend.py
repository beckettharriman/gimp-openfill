# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend interface shared by the ComfyUI and AUTOMATIC1111 implementations.

The GIMP side only ever talks to a :class:`Backend`; it never knows which
server is behind it. Requests carry already-encoded PNG bytes so the backend
modules stay free of GIMP imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

ProgressCallback = Callable[[float, str], None]
PreviewCallback = Callable[[bytes], None]      # raw ComfyUI binary frame (see progress.parse_preview_frame)
CancelCallback = Callable[[], bool]            # polled; True aborts the running job


class BackendError(RuntimeError):
    """Base class for everything the backend can report to the user."""


class BackendUnavailable(BackendError):
    """The server is not running, cannot be reached or failed to start."""


class ModelMissing(BackendError):
    """A checkpoint or patch file the workflow needs is not on the server."""


class OutOfMemory(BackendError):
    """The GPU ran out of memory while generating."""


class GenerationTimeout(BackendError):
    """The request exceeded the configured timeout."""


class GenerationCancelled(BackendError):
    """The user or the plug-in cancelled the request."""


class WorkflowRejected(BackendError):
    """The server refused the submitted workflow (invalid inputs)."""


@dataclass
class Sampling:
    steps: int = 25
    cfg: float = 7.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    denoise: float = 1.0
    seed: int = -1          # negative = random
    batch: int = 1          # number of variations


@dataclass
class ModelSpec:
    checkpoint: str = ""
    arch: str = "sd15"                        # sd15 | sdxl | flux | qwen_image | inpaint_model
    fooocus_head: Optional[str] = None        # SDXL only
    fooocus_patch: Optional[str] = None       # SDXL only
    template: str = ""                        # catalog template id; "" = derive from arch
    unet: str = ""                            # diffusion model file (FLUX / Qwen, safetensors or gguf)
    clip1: str = ""                           # text encoder 1 (T5 / Qwen2.5-VL)
    clip2: str = ""                           # text encoder 2 (CLIP-L)
    vae: str = ""                             # separate VAE file
    inpaint_model: str = ""                   # LaMa / MAT file for prompt-free removal

    @property
    def uses_fooocus(self) -> bool:
        return self.arch == "sdxl" and bool(self.fooocus_head and self.fooocus_patch)

    @property
    def effective_template(self) -> str:
        if self.template:
            return self.template
        return {"sdxl": "sdxl_fooocus", "flux": "flux_fill", "qwen_image": "qwen_edit",
                "inpaint_model": "inpaint_model"}.get(self.arch, "sd15_inpaint")

    @property
    def prompt_free(self) -> bool:
        return self.effective_template == "inpaint_model"


@dataclass
class InpaintRequest:
    image_png: bytes             # context crop, RGB or RGBA PNG
    mask_png: bytes              # 8-bit gray PNG, 255 = generate here
    width: int                   # crop size in image pixels
    height: int
    work_width: int              # resolution the model samples at
    work_height: int
    prompt: str
    negative: str
    model: ModelSpec
    sampling: Sampling = field(default_factory=Sampling)
    mode: str = "fill"           # "fill" or "expand"
    grow: int = 16               # mask dilation in working pixels
    feather: int = 24            # mask blur in working pixels
    prefill: bool = True         # pre-fill masked area before sampling
    prefill_mode: str = "navier-stokes"  # expand pre-fill: navier-stokes | telea | neutral
    color_match: float = 1.0     # strength of the post color correction (0 = off)

    @property
    def needs_scaling(self) -> bool:
        return (self.work_width, self.work_height) != (self.width, self.height)


@dataclass
class Txt2ImgRequest:
    width: int
    height: int
    prompt: str
    negative: str
    model: ModelSpec
    sampling: Sampling = field(default_factory=Sampling)


@dataclass
class GenerationResult:
    images: list[bytes]          # PNG bytes, one per variation
    seed: int
    info: dict = field(default_factory=dict)


@dataclass
class HealthStatus:
    ok: bool
    detail: str = ""
    version: str = ""
    checkpoints: list[str] = field(default_factory=list)
    inpaint_nodes: bool = False
    fooocus_heads: list[str] = field(default_factory=list)
    fooocus_patches: list[str] = field(default_factory=list)
    vram_total: int = 0
    vram_free: int = 0


@dataclass
class Progress:
    fraction: float = 0.0
    text: str = ""
    running: bool = False


class Backend(ABC):
    """Abstract generation backend."""

    name: str = "abstract"

    @abstractmethod
    def health(self) -> HealthStatus:
        """Return server status and the models it can offer."""

    @abstractmethod
    def inpaint(self, request: InpaintRequest, progress: ProgressCallback | None = None,
                preview: PreviewCallback | None = None, cancel: CancelCallback | None = None) -> GenerationResult:
        """Fill the masked part of ``request.image_png``."""

    def outpaint(self, request: InpaintRequest, progress: ProgressCallback | None = None,
                 preview: PreviewCallback | None = None, cancel: CancelCallback | None = None) -> GenerationResult:
        """Expand: same as inpaint with ``mode='expand'`` semantics."""
        request.mode = "expand"
        return self.inpaint(request, progress, preview, cancel)

    @abstractmethod
    def txt2img(self, request: Txt2ImgRequest, progress: ProgressCallback | None = None,
                preview: PreviewCallback | None = None, cancel: CancelCallback | None = None) -> GenerationResult:
        """Generate from text only."""

    @abstractmethod
    def progress(self) -> Progress:
        """Current progress of the running job, if any."""

    @abstractmethod
    def cancel(self) -> None:
        """Interrupt the running job."""


def describe_error(error: BaseException) -> str:
    """Short, user-facing description for a backend failure."""
    if isinstance(error, BackendUnavailable):
        return f"The AI backend is not available: {error}"
    if isinstance(error, ModelMissing):
        return f"A model file is missing on the backend: {error}"
    if isinstance(error, OutOfMemory):
        return ("The GPU ran out of memory. Try a smaller selection, fewer "
                "variations, or the SD 1.5 model instead of SDXL.")
    if isinstance(error, GenerationTimeout):
        return f"The request timed out: {error}"
    if isinstance(error, GenerationCancelled):
        return "Generation was cancelled."
    if isinstance(error, WorkflowRejected):
        return f"The backend rejected the workflow: {error}"
    return f"{type(error).__name__}: {error}"

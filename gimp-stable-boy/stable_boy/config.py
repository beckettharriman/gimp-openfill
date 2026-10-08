# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings persisted as JSON in the GIMP profile (``<profile>/stable-boy``).

No GIMP imports: the caller passes the profile directory.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_DIRNAME = "stable-boy"
CONFIG_FILENAME = "config.json"
STATE_FILENAME = "server-state.json"
LOG_FILENAME = "stable-boy.log"
SERVER_LOG_FILENAME = "comfyui.log"
MODELS_CACHE_FILENAME = "models-cache.json"


def default_comfy_dir() -> str:
    if sys.platform == "win32":
        return r"C:\AI\ComfyUI\ComfyUI_windows_portable"
    return str(Path.home() / "ComfyUI")


@dataclass
class Settings:
    backend: str = "comfyui"                       # "comfyui" or "a1111"
    comfy_dir: str = field(default_factory=default_comfy_dir)
    url: str = "http://127.0.0.1:8188"             # ComfyUI (or A1111) base URL
    a1111_url: str = "http://127.0.0.1:7860"
    autostart: bool = True                         # start ComfyUI when needed
    idle_timeout_minutes: int = 20                 # 0 = keep running until GIMP exits
    startup_timeout: int = 240                     # seconds to wait for the server
    request_timeout: int = 0                       # 0 = estimate per request
    extra_server_args: str = ""                    # appended to the ComfyUI command
    checkpoint: str = "sd-v1-5-inpainting.ckpt"    # default (SD 1.5) model
    sdxl_checkpoint: str = "sd_xl_base_1.0.safetensors"
    fooocus_head: str = "fooocus_inpaint_head.pth"
    fooocus_patch: str = "inpaint_v26.fooocus.patch"
    quality: str = "fast"                          # "fast" (SD 1.5) or "quality" (SDXL)
    steps: int = 25
    cfg: float = 7.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    denoise: float = 1.0
    grow: int = 48                                 # mask dilation cap (px); actual = grow_percent of selection
    feather: int = 24                              # layer mask feather cap (px); actual = feather_percent
    grow_percent: float = 15.0                     # dilation as percent of the selection's larger side (covers object rims)
    feather_percent: float = 6.0                   # layer mask feather as percent of the larger side
    prefill: bool = True
    max_side_sd15: int = 768
    max_side_sdxl: int = 1024
    txt2img_width: int = 768
    txt2img_height: int = 512
    debug: bool = False
    active_model: str = "sd15-inpainting"          # catalog id used when a dialog says "active"
    hf_token: str = ""                             # Hugging Face access token for gated files (local only)
    progress_window: bool = True                   # floating progress/preview window
    progress_window_x: int = -1                    # last position; -1 = top-right of the image window
    progress_window_y: int = -1

    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "Settings":
        settings = cls()
        try:  # utf-8-sig: tolerate the BOM that PowerShell's Set-Content adds
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return settings
        if not isinstance(data, dict):
            return settings
        known = {f.name: f.type for f in fields(cls)}
        for key, value in data.items():
            if key in known:
                try:
                    setattr(settings, key, _coerce(getattr(settings, key), value))
                except (TypeError, ValueError):
                    pass
        return settings

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def to_dict(self) -> dict:
        return asdict(self)

    # derived -----------------------------------------------------------

    @property
    def active_url(self) -> str:
        return self.a1111_url if self.backend == "a1111" else self.url

    def model_for(self, quality: str | None = None):
        """Return a ``ModelSpec`` for the requested quality tier."""
        from .backend import ModelSpec
        tier = quality or self.quality
        if tier == "quality" and self.sdxl_checkpoint:
            return ModelSpec(self.sdxl_checkpoint, "sdxl", self.fooocus_head or None,
                             self.fooocus_patch or None)
        return ModelSpec(self.checkpoint, "sd15")


def _coerce(current, value):
    if isinstance(current, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return str(value)


@dataclass
class Paths:
    """All files the plug-in owns inside the GIMP profile."""

    base: Path

    @classmethod
    def for_profile(cls, profile_dir: str | Path) -> "Paths":
        return cls(Path(profile_dir) / CONFIG_DIRNAME)

    @property
    def config(self) -> Path:
        return self.base / CONFIG_FILENAME

    @property
    def state(self) -> Path:
        return self.base / STATE_FILENAME

    @property
    def log(self) -> Path:
        return self.base / LOG_FILENAME

    @property
    def server_log(self) -> Path:
        return self.base / SERVER_LOG_FILENAME

    @property
    def models_cache(self) -> Path:
        return self.base / MODELS_CACHE_FILENAME

    @property
    def temp(self) -> Path:
        return self.base / "tmp"

    def ensure(self) -> "Paths":
        self.base.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)
        return self


def comfy_layout(comfy_dir: str | Path) -> dict[str, Path] | None:
    """Locate python + main.py for a ComfyUI install; None if not found.

    Supports the official Windows portable (``python_embeded/python.exe`` +
    ``ComfyUI/main.py``), a plain git checkout with a ``venv``/``.venv``,
    and a checkout where the interpreter is given explicitly via PATH.
    """
    root = Path(comfy_dir)
    candidates = []
    if (root / "python_embeded" / "python.exe").exists() and (root / "ComfyUI" / "main.py").exists():
        candidates.append((root / "python_embeded" / "python.exe", root / "ComfyUI" / "main.py", root))
    main = root / "main.py"
    if main.exists():
        for venv in ("venv", ".venv"):
            for py in ("Scripts/python.exe", "bin/python3", "bin/python"):
                exe = root / venv / py
                if exe.exists():
                    candidates.append((exe, main, root))
        candidates.append((Path(sys.executable), main, root))
    if not candidates:
        return None
    python, main, cwd = candidates[0]
    return {"python": python, "main": main, "cwd": cwd}

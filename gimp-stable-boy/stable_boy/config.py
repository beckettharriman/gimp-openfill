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
import time
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .backend import ModelSpec

CONFIG_DIRNAME = "stable-boy"
CONFIG_FILENAME = "config.json"
STATE_FILENAME = "server-state.json"
LOG_FILENAME = "stable-boy.log"
SERVER_LOG_FILENAME = "comfyui.log"
MODELS_CACHE_FILENAME = "models-cache.json"


def default_comfy_dir() -> str:
    """The ComfyUI folder assumed when the config does not name one."""
    if sys.platform == "win32":
        return r"C:\AI\ComfyUI\ComfyUI_windows_portable"
    return str(Path.home() / "ComfyUI")


@dataclass
class Settings:
    """User settings stored in ``config.json``.

    ``hf_token`` is a secret: it is left out of ``repr()`` so it cannot end up
    in a log line or a traceback, and :meth:`save` makes the file readable by
    its owner only on POSIX systems.
    """

    backend: str = "comfyui"  # "comfyui" or "a1111"
    comfy_dir: str = field(default_factory=default_comfy_dir)
    url: str = "http://127.0.0.1:8188"  # ComfyUI (or A1111) base URL
    a1111_url: str = "http://127.0.0.1:7860"
    autostart: bool = True  # start ComfyUI when needed
    idle_timeout_minutes: int = 20  # 0 = keep running until GIMP exits
    startup_timeout: int = 240  # seconds to wait for the server
    request_timeout: int = 0  # 0 = estimate per request
    extra_server_args: str = ""  # appended to the ComfyUI command
    checkpoint: str = "sd-v1-5-inpainting.ckpt"  # default (SD 1.5) model
    sdxl_checkpoint: str = "sd_xl_base_1.0.safetensors"
    fooocus_head: str = "fooocus_inpaint_head.pth"
    fooocus_patch: str = "inpaint_v26.fooocus.patch"
    quality: str = "fast"  # "fast" (SD 1.5) or "quality" (SDXL)
    steps: int = 25
    cfg: float = 7.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    denoise: float = 1.0
    grow: int = 48  # mask dilation cap (px); actual = grow_percent of selection
    feather: int = 24  # layer mask feather cap (px); actual = feather_percent
    grow_percent: float = 15.0  # dilation as percent of the selection's larger side (covers object rims)
    feather_percent: float = 6.0  # layer mask feather as percent of the larger side
    prefill: bool = True
    max_side_sd15: int = 768
    max_side_sdxl: int = 1024
    txt2img_width: int = 768
    txt2img_height: int = 512
    debug: bool = False
    active_model: str = "sd15-inpainting"  # catalog id used when a dialog says "active"
    hf_token: str = field(default="", repr=False)  # Hugging Face access token for gated files (local only)
    progress_window: bool = True  # floating progress/preview window
    progress_window_x: int = -1  # last position; -1 = top-right of the image window
    progress_window_y: int = -1
    prompt_history: str = ""  # JSON list of recent prompts, newest first (dialogs)
    # Not persisted: why the last :meth:`load` fell back to defaults (None when it did not).
    load_problem: str | None = field(default=None, repr=False, compare=False, metadata={"persist": False})
    # Not persisted: a damaged settings file that could not be moved aside; :meth:`save` refuses to overwrite it.
    _protected_path: str | None = field(default=None, repr=False, compare=False, metadata={"persist": False})

    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path, backup: bool = True) -> Settings:
        """Read ``path``; a missing file, unknown keys and mistyped values fall back to defaults.

        A file that exists but is not a JSON object (damaged, half written, edited
        by hand) is moved aside to ``config.json.corrupt-<YYYYmmdd-HHMMSS>`` so a
        later :meth:`save` cannot destroy the user's settings and token, and
        :attr:`load_problem` says so in plain words. ``backup=False`` (for
        processes other than the plug-in) only reads and never moves anything.
        """
        settings = cls()
        path = Path(path)
        try:  # utf-8-sig: tolerate the BOM that PowerShell's Set-Content adds
            text = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return settings
        except OSError as err:
            settings.load_problem = (
                f"Your settings file '{path}' could not be opened ({err.strerror or err}); defaults are in use "
                "for now and will not be saved over it. Check the file's permissions, then restart GIMP."
            )
            settings._protected_path = str(path)
            return settings
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            if backup:
                settings._move_aside(path)
            else:
                settings._protected_path = str(path)
            return settings
        known = {f.name for f in fields(cls) if f.metadata.get("persist", True)}
        for key, value in data.items():
            if key in known:
                try:
                    setattr(settings, key, _coerce(getattr(settings, key), value))
                except (TypeError, ValueError):
                    pass
        return settings

    def _move_aside(self, path: Path) -> None:
        """Rename an unreadable settings file to a fresh ``.corrupt-<timestamp>`` name and record why."""
        target = corrupt_backup_path(path)
        try:
            os.rename(path, target)  # never replaces: the name was checked free, and rename fails on Windows if taken
        except OSError as err:
            self._protected_path = str(path)
            self.load_problem = (
                f"Your settings file '{path}' could not be read, and moving it aside failed "
                f"({err.strerror or err}); defaults are in use and the file was left untouched. "
                "Fix or delete the file, then open Filters > AI > Generative Fill Settings again."
            )
            return
        self.load_problem = (
            f"Your settings file could not be read and was moved aside to '{target}'; defaults are in use. "
            "Open Filters > AI > Generative Fill Settings to set the ComfyUI folder and your options again."
        )

    def save(self, path: Path) -> None:
        """Write atomically (temporary file, then rename); owner-only permissions on POSIX."""
        path = Path(path)
        if self._protected_path and os.path.abspath(path) == os.path.abspath(self._protected_path):
            raise OSError(f"not saving: '{path}' could not be read and was not backed up, so it is kept as it is")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.metadata.get("persist", True)}
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp, 0o600)  # the file holds the Hugging Face token
        os.replace(tmp, path)

    # derived -----------------------------------------------------------

    @property
    def active_url(self) -> str:
        """Base URL of the selected backend."""
        return self.a1111_url if self.backend == "a1111" else self.url

    def model_for(self, quality: str | None = None) -> ModelSpec:
        """Return a ``ModelSpec`` for the requested quality tier."""
        from .backend import ModelSpec

        tier = quality or self.quality
        if tier == "quality" and self.sdxl_checkpoint:
            return ModelSpec(self.sdxl_checkpoint, "sdxl", self.fooocus_head or None, self.fooocus_patch or None)
        return ModelSpec(self.checkpoint, "sd15")


def corrupt_backup_path(path: Path, now: float | None = None) -> Path:
    """A name next to ``path`` that does not exist yet: ``<name>.corrupt-<YYYYmmdd-HHMMSS>[-N]``."""
    path = Path(path)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    candidate = path.with_name(f"{path.name}.corrupt-{stamp}")
    n = 1
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.name}.corrupt-{stamp}-{n}")
    return candidate


def _coerce(current: Any, value: Any) -> Any:
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
    def for_profile(cls, profile_dir: str | Path) -> Paths:
        """Paths under ``<profile_dir>/stable-boy``."""
        return cls(Path(profile_dir) / CONFIG_DIRNAME)

    @property
    def config(self) -> Path:
        """Settings file (holds the Hugging Face token)."""
        return self.base / CONFIG_FILENAME

    @property
    def state(self) -> Path:
        """Supervisor state: pids, URL, status."""
        return self.base / STATE_FILENAME

    @property
    def log(self) -> Path:
        """Plug-in and supervisor log."""
        return self.base / LOG_FILENAME

    @property
    def server_log(self) -> Path:
        """ComfyUI stdout and stderr."""
        return self.base / SERVER_LOG_FILENAME

    @property
    def models_cache(self) -> Path:
        """Model files the server listed last time (no secrets)."""
        return self.base / MODELS_CACHE_FILENAME

    @property
    def temp(self) -> Path:
        """Scratch folder (debug dumps)."""
        return self.base / "tmp"

    def ensure(self) -> Paths:
        """Create the folders; returns ``self``."""
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
    candidates: list[tuple[Path, Path, Path]] = []
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

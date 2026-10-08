# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Model catalog: loading, validation, install status, template selection.

The catalog (``models/catalog.json``) describes every model the plug-in can
download and run. This module has no GIMP dependency.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .backend import ModelSpec

TIERS = ("fast", "quality", "edit", "removal")
CAPABILITIES = ("fill", "expand", "txt2img", "remove", "edit", "patch")
SOURCE_TYPES = ("first-party", "community-quantization")
TEMPLATES = ("sd15_inpaint", "sdxl_fooocus", "flux_fill", "qwen_edit", "inpaint_model")
ARCHS = {"sd15": "sd15", "sdxl": "sdxl", "flux": "flux", "qwen_image": "qwen_image",
         "inpaint_model": "inpaint_model"}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class FileSpec:
    role: str
    url: str
    dest: str                 # relative to <ComfyUI>/models
    size: Optional[int] = None
    sha256: Optional[str] = None
    gated: bool = False
    optional: bool = False    # skip if another entry already provided it
    license: str = ""

    @property
    def filename(self) -> str:
        return self.dest.replace("\\", "/").rsplit("/", 1)[-1]

    @property
    def subfolder(self) -> str:
        parts = self.dest.replace("\\", "/").rsplit("/", 1)
        return parts[0] if len(parts) == 2 else ""


@dataclass(frozen=True)
class NodeSpec:
    repo: str
    folder: str
    commit: str
    license: str = ""


@dataclass(frozen=True)
class ModelEntry:
    id: str
    name: str
    tier: str
    capabilities: tuple[str, ...]
    arch: str
    template: Optional[str]
    page: str
    license_name: str
    license_url: str
    gated: bool
    source_type: str
    uploader: str
    min_vram_gb: float
    requires_nodes: tuple[NodeSpec, ...]
    requires_models: tuple[str, ...]
    files: tuple[FileSpec, ...]

    @property
    def total_size(self) -> int:
        return sum(f.size or 0 for f in self.files)

    @property
    def runnable(self) -> bool:
        return self.template is not None

    def file_by_role(self, role: str) -> Optional[FileSpec]:
        for f in self.files:
            if f.role == role:
                return f
        return None


@dataclass
class InstallStatus:
    installed: bool
    missing: list[str] = field(default_factory=list)     # dest paths not on disk
    partial: list[str] = field(default_factory=list)     # .part files present
    missing_nodes: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)  # required companion entries
    seen_by_server: Optional[bool] = None

    @property
    def label(self) -> str:
        if self.installed and not self.missing_nodes and not self.missing_models:
            return "Installed"
        if self.installed and (self.missing_nodes or self.missing_models):
            return "Needs node" if self.missing_nodes else "Needs model"
        if self.partial:
            return "Partial"
        return "Available"


# ------------------------------------------------------------------ load ----

def _req(d: dict, key: str, where: str):
    if key not in d:
        raise CatalogError(f"{where}: missing '{key}'")
    return d[key]


def parse_catalog(data: dict) -> list[ModelEntry]:
    if not isinstance(data, dict) or "models" not in data:
        raise CatalogError("catalog must be an object with a 'models' list")
    entries: list[ModelEntry] = []
    seen: set[str] = set()
    for raw in data["models"]:
        where = f"model '{raw.get('id', '?')}'"
        mid = _req(raw, "id", where)
        if not isinstance(mid, str) or not mid or any(c in mid for c in " /\\"):
            raise CatalogError(f"{where}: invalid id")
        if mid in seen:
            raise CatalogError(f"{where}: duplicate id")
        seen.add(mid)
        tier = _req(raw, "tier", where)
        if tier not in TIERS:
            raise CatalogError(f"{where}: unknown tier '{tier}'")
        caps = tuple(_req(raw, "capabilities", where))
        for c in caps:
            if c not in CAPABILITIES:
                raise CatalogError(f"{where}: unknown capability '{c}'")
        template = raw.get("template")
        if template is not None and template not in TEMPLATES:
            raise CatalogError(f"{where}: unknown template '{template}'")
        arch = _req(raw, "arch", where)
        if arch not in ARCHS:
            raise CatalogError(f"{where}: unknown arch '{arch}'")
        src = _req(raw, "source_type", where)
        if src not in SOURCE_TYPES:
            raise CatalogError(f"{where}: unknown source_type '{src}'")
        lic = _req(raw, "license", where)
        if not isinstance(lic, dict) or not lic.get("name") or not lic.get("url"):
            raise CatalogError(f"{where}: license needs name and url")
        files = []
        for fr in _req(raw, "files", where):
            url, dest = _req(fr, "url", where), _req(fr, "dest", where)
            if not url.startswith("https://"):
                raise CatalogError(f"{where}: file url must be https: {url}")
            if dest.startswith(("/", "\\")) or ".." in dest.split("/"):
                raise CatalogError(f"{where}: unsafe dest '{dest}'")
            sha = fr.get("sha256")
            if sha is not None and (len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)):
                raise CatalogError(f"{where}: bad sha256 for {dest}")
            files.append(FileSpec(fr.get("role", "file"), url, dest, fr.get("size"), sha,
                                  bool(fr.get("gated", False)), bool(fr.get("optional", False)),
                                  fr.get("license", "")))
        if not files:
            raise CatalogError(f"{where}: no files")
        nodes = tuple(NodeSpec(_req(n, "repo", where), _req(n, "folder", where), _req(n, "commit", where),
                               n.get("license", "")) for n in raw.get("requires_nodes", []))
        for n in nodes:
            if len(n.commit) < 7:
                raise CatalogError(f"{where}: node {n.folder} needs a pinned commit")
        entries.append(ModelEntry(
            id=mid, name=_req(raw, "name", where), tier=tier, capabilities=caps, arch=arch,
            template=template, page=raw.get("page", ""), license_name=lic["name"], license_url=lic["url"],
            gated=bool(raw.get("gated", False)) or any(f.gated for f in files), source_type=src,
            uploader=raw.get("uploader", ""), min_vram_gb=float(raw.get("min_vram_gb", 0)),
            requires_nodes=nodes, requires_models=tuple(raw.get("requires_models", [])), files=tuple(files)))
    ids = {e.id for e in entries}
    for e in entries:
        for dep in e.requires_models:
            if dep not in ids:
                raise CatalogError(f"model '{e.id}' requires unknown model '{dep}'")
    return entries


def catalog_search_paths(plugin_dir: str | Path) -> list[Path]:
    plugin_dir = Path(plugin_dir)
    return [plugin_dir / "models" / "catalog.json",
            plugin_dir.parent / "models" / "catalog.json"]


def load_catalog(path: str | Path | None = None, plugin_dir: str | Path | None = None) -> list[ModelEntry]:
    candidates = [Path(path)] if path else catalog_search_paths(plugin_dir or Path(__file__).resolve().parent.parent)
    for candidate in candidates:
        if candidate.is_file():
            with open(candidate, "r", encoding="utf-8-sig") as fh:
                return parse_catalog(json.load(fh))
    raise CatalogError("catalog.json not found in " + ", ".join(str(c) for c in candidates))


def by_id(entries: Iterable[ModelEntry], model_id: str) -> ModelEntry:
    for e in entries:
        if e.id == model_id:
            return e
    raise CatalogError(f"unknown model id '{model_id}'")


# ---------------------------------------------------------------- status ----

def file_installed(models_root: Path, spec: FileSpec) -> bool:
    path = Path(models_root) / spec.dest
    if not path.is_file():
        return False
    if spec.size:
        try:
            return path.stat().st_size == spec.size
        except OSError:
            return False
    return True


def install_status(entry: ModelEntry, models_root: Path, custom_nodes_dir: Path | None,
                   catalog: Iterable[ModelEntry] = (), server_files: Iterable[str] | None = None) -> InstallStatus:
    missing, partial = [], []
    for f in entry.files:
        if file_installed(models_root, f):
            continue
        missing.append(f.dest)
        if (Path(models_root) / (f.dest + ".part")).exists():
            partial.append(f.dest)
    missing_nodes = []
    if custom_nodes_dir is not None:
        for n in entry.requires_nodes:
            if not (Path(custom_nodes_dir) / n.folder).is_dir():
                missing_nodes.append(n.folder)
    missing_models = []
    catalog = list(catalog)
    for dep in entry.requires_models:
        try:
            dep_entry = by_id(catalog, dep)
        except CatalogError:
            missing_models.append(dep)
            continue
        if any(not file_installed(models_root, f) for f in dep_entry.files):
            missing_models.append(dep)
    seen = None
    if server_files is not None:
        names = set(server_files)
        seen = all(f.filename in names for f in entry.files if f.role in ("checkpoint", "unet"))
    return InstallStatus(not missing, missing, partial, missing_nodes, missing_models, seen)


# -------------------------------------------------------------- model spec ----

def model_spec_for(entry: ModelEntry, catalog: Iterable[ModelEntry] = ()) -> ModelSpec:
    """Translate a catalog entry into the backend's ModelSpec."""
    if not entry.runnable:
        raise CatalogError(f"model '{entry.id}' is not a runnable model")
    names = {f.role: f.filename for f in entry.files}
    paths = {f.role: f.dest for f in entry.files}
    spec = ModelSpec(checkpoint=names.get("checkpoint", ""), arch=entry.arch, template=entry.template or "")
    spec.unet = names.get("unet", "")
    spec.clip1 = names.get("clip1", "")
    spec.clip2 = names.get("clip2", "")
    spec.vae = names.get("vae", "")
    spec.inpaint_model = names.get("inpaint_model", "")
    if entry.template == "sdxl_fooocus":
        for dep in entry.requires_models:
            dep_entry = by_id(list(catalog), dep)
            spec.fooocus_head = (dep_entry.file_by_role("fooocus_head") or FileSpec("", "", "")).filename or None
            spec.fooocus_patch = (dep_entry.file_by_role("fooocus_patch") or FileSpec("", "", "")).filename or None
    for role in ("clip1", "unet"):
        if paths.get(role, "").startswith("text_encoders/"):
            pass  # ComfyUI lists text_encoders/ and clip/ under the same loader
    return spec


def human_size(num: int | float | None) -> str:
    if not num:
        return "?"
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def default_models_root(comfy_dir: str | Path) -> Path:
    root = Path(comfy_dir)
    if (root / "ComfyUI" / "models").is_dir():
        return root / "ComfyUI" / "models"
    return root / "models"


def default_custom_nodes_dir(comfy_dir: str | Path) -> Path:
    root = Path(comfy_dir)
    if (root / "ComfyUI" / "custom_nodes").is_dir():
        return root / "ComfyUI" / "custom_nodes"
    return root / "custom_nodes"


def free_disk_bytes(path: Path) -> int:
    try:
        st = os.statvfs(path)  # type: ignore[attr-defined]
        return st.f_bavail * st.f_frsize
    except AttributeError:
        import shutil
        return shutil.disk_usage(path).free

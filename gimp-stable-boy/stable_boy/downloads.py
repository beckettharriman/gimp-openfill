# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resumable, verified model downloads and custom-node installation.

Pure Python (urllib + subprocess). Used by the supervisor's task worker and by
unit tests; nothing here touches GIMP.
"""

from __future__ import annotations

import errno
import hashlib
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHUNK = 1024 * 1024
USER_AGENT = "gimp-stable-boy/2.0 (+https://github.com/thndrbrrr/gimp-stable-boy)"

ProgressFn = Callable[[int, Optional[int], float], None]   # done, total, bytes/sec
CancelFn = Callable[[], bool]


class DownloadError(RuntimeError):
    """``code`` is one of: auth, notfound, disk, hash, network, cancelled, size."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class DownloadResult:
    path: Path
    bytes_written: int
    sha256: Optional[str]
    resumed_from: int
    skipped: bool = False


def part_path(dest: Path) -> Path:
    return dest.with_name(dest.name + ".part")


def _sha256_of(path: Path, cancel: CancelFn | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(CHUNK * 4)
            if not block:
                break
            h.update(block)
            if cancel and cancel():
                raise DownloadError("cancelled", "cancelled during verification")
    return h.hexdigest()


def _open(url: str, headers: dict, opener=urlopen, timeout: float = 60.0):
    req = Request(url, headers=headers, method="GET")
    return opener(req, timeout=timeout)


def download_file(url: str, dest: Path, expected_size: int | None = None,
                  expected_sha256: str | None = None, token: str | None = None,
                  progress: ProgressFn | None = None, cancel: CancelFn | None = None,
                  opener=urlopen, min_free_bytes: int = 256 * 1024 * 1024) -> DownloadResult:
    """Download ``url`` to ``dest`` with resume (HTTP Range), verification and
    atomic rename. Raises :class:`DownloadError` with a user-facing ``code``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        size_ok = expected_size is None or dest.stat().st_size == expected_size
        if size_ok and (expected_sha256 is None or _sha256_of(dest, cancel) == expected_sha256):
            return DownloadResult(dest, 0, expected_sha256, 0, skipped=True)
        dest.unlink()  # wrong size or hash: start over

    part = part_path(dest)
    offset = part.stat().st_size if part.is_file() else 0
    if expected_size and offset > expected_size:
        part.unlink()
        offset = 0

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if offset:
        headers["Range"] = f"bytes={offset}-"

    try:
        resp = _open(url, headers, opener)
    except HTTPError as err:
        if err.code in (401, 403):
            raise DownloadError("auth", f"HTTP {err.code}: this file is gated. Accept the license on the model page "
                                        "and enter a Hugging Face access token in the settings.") from err
        if err.code == 404:
            raise DownloadError("notfound", f"HTTP 404: the file is no longer at {url}") from err
        if err.code == 416 and offset:
            # The partial file is already complete (or the server disagrees); verify below.
            resp = None
        else:
            raise DownloadError("network", f"HTTP {err.code} while fetching {url}") from err
    except (URLError, OSError, TimeoutError) as err:
        raise DownloadError("network", f"could not connect: {err}") from err

    written = 0
    resumed_from = offset
    if resp is not None:
        with resp:
            status = getattr(resp, "status", None) or resp.getcode()
            length = resp.headers.get("Content-Length")
            total: Optional[int] = None
            if status == 206 and offset:
                mode = "ab"
                total = offset + int(length) if length else expected_size
            else:
                mode = "wb"
                resumed_from = 0
                offset = 0
                total = int(length) if length else expected_size
            if expected_size and total and total != expected_size:
                raise DownloadError("size", f"server reports {total} bytes, catalog expects {expected_size}")
            if total:
                try:
                    import shutil
                    free = shutil.disk_usage(dest.parent).free
                    if free < (total - offset) + min_free_bytes:
                        raise DownloadError("disk", f"not enough disk space: need {total - offset} bytes, "
                                                    f"{free} free on {dest.parent.anchor or dest.parent}")
                except OSError:
                    pass
            started = time.monotonic()
            last_report = 0.0
            try:
                with open(part, mode) as fh:
                    while True:
                        if cancel and cancel():
                            raise DownloadError("cancelled", "download cancelled")
                        block = resp.read(CHUNK)
                        if not block:
                            break
                        fh.write(block)
                        written += len(block)
                        now = time.monotonic()
                        if progress and (now - last_report >= 0.5 or (total and offset + written >= total)):
                            last_report = now
                            speed = written / max(1e-6, now - started)
                            progress(offset + written, total, speed)
            except OSError as err:
                if err.errno in (errno.ENOSPC, 28) or "No space" in str(err):
                    raise DownloadError("disk", "the disk is full") from err
                raise DownloadError("network", f"read/write error: {err}") from err

    final_size = part.stat().st_size if part.is_file() else 0
    if expected_size and final_size != expected_size:
        raise DownloadError("size", f"downloaded {final_size} bytes, expected {expected_size}; "
                                    "the partial file is kept for resume")
    digest = None
    if expected_sha256:
        digest = _sha256_of(part, cancel)
        if digest != expected_sha256:
            part.unlink()
            raise DownloadError("hash", f"checksum mismatch for {dest.name}: got {digest[:12]}..., "
                                        f"expected {expected_sha256[:12]}...; the file was deleted")
    elif part.is_file():
        digest = _sha256_of(part, cancel)
    os.replace(part, dest)
    return DownloadResult(dest, written, digest, resumed_from)


# ---------------------------------------------------------- custom nodes ----

def git_executable() -> str:
    for name in ("git", "git.exe"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            p = Path(d) / name
            if p.is_file():
                return str(p)
    for p in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe"):
        if Path(p).is_file():
            return p
    return "git"


def install_custom_node(repo: str, folder: str, commit: str, custom_nodes_dir: Path, python: Path,
                        log: Callable[[str], None] | None = None, runner=subprocess.run) -> Path:
    """Clone ``repo`` into ``custom_nodes_dir/folder`` at ``commit`` and install
    its requirements with ``python``. Idempotent: an existing clone is reset to
    the pinned commit."""
    log = log or (lambda s: None)
    git = git_executable()
    target = Path(custom_nodes_dir) / folder
    kw = {"capture_output": True, "text": True}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    if not (target / ".git").is_dir():
        log(f"cloning {repo} -> {target}")
        r = runner([git, "clone", "--quiet", repo, str(target)], **kw)
        if r.returncode != 0:
            raise RuntimeError(f"git clone failed: {r.stderr.strip() or r.stdout.strip()}")
    log(f"checking out {commit}")
    r = runner([git, "-C", str(target), "fetch", "--quiet", "origin"], **kw)
    r = runner([git, "-C", str(target), "checkout", "--quiet", commit], **kw)
    if r.returncode != 0:
        raise RuntimeError(f"git checkout {commit} failed: {r.stderr.strip() or r.stdout.strip()}")
    req = target / "requirements.txt"
    if req.is_file():
        log(f"installing requirements with {python}")
        r = runner([str(python), "-s", "-m", "pip", "install", "--no-warn-script-location", "-r", str(req)], **kw)
        if r.returncode != 0:
            raise RuntimeError(f"pip install failed: {(r.stderr or r.stdout).strip()[-800:]}")
    return target


def node_installed(custom_nodes_dir: Path, folder: str) -> bool:
    return (Path(custom_nodes_dir) / folder).is_dir()

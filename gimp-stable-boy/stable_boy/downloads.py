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
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CHUNK = 1024 * 1024
USER_AGENT = "gimp-stable-boy/2.0 (+https://github.com/thndrbrrr/gimp-stable-boy)"

# The Hugging Face token is only ever sent to these hosts (and their subdomains),
# only over https, and never forwarded on a redirect (the CDN URLs are pre-signed).
HF_TOKEN_HOSTS: tuple[str, ...] = ("huggingface.co", "hf.co")

# Custom node repositories must be plain GitHub https URLs pinned to a full commit.
_REPO_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?/?$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")
_CONTENT_RANGE_RE = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$")

ProgressFn = Callable[[int, "int | None", float], None]  # done, total, bytes/sec
CancelFn = Callable[[], bool]


class DownloadError(RuntimeError):
    """``code`` is one of: auth, notfound, disk, hash, network, cancelled, size."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class DownloadResult:
    """Outcome of :func:`download_file`."""

    path: Path
    bytes_written: int
    sha256: str | None
    resumed_from: int
    skipped: bool = False


# ------------------------------------------------------------- validation ----


def is_safe_name(name: str) -> bool:
    """True for a plain file or folder name: no separators, no ``..``, no drive."""
    return isinstance(name, str) and bool(_NAME_RE.match(name)) and name not in (".", "..")


def safe_relative_path(rel: str) -> str:
    """Validate a catalog ``dest`` (``subfolder/file``) and return it with ``/`` separators.

    Rejects absolute paths, drive letters, ``..`` and empty segments, and
    requires every segment to be a plain name. Raises ``ValueError``.
    """
    if not isinstance(rel, str) or not rel:
        raise ValueError("empty path")
    norm = rel.replace("\\", "/")
    if norm.startswith("/") or ":" in norm:
        raise ValueError(f"absolute path not allowed: {rel!r}")
    segments = norm.split("/")
    if any(not is_safe_name(seg) for seg in segments):
        raise ValueError(f"unsafe path: {rel!r}")
    return "/".join(PurePosixPath(norm).parts)


def safe_join(root: Path, rel: str) -> Path:
    """``root / rel`` after :func:`safe_relative_path`, verified to stay inside ``root``."""
    root = Path(root)
    path = root.joinpath(*safe_relative_path(rel).split("/"))
    resolved_root, resolved = root.resolve(), path.resolve()
    if resolved_root not in resolved.parents:
        raise ValueError(f"path escapes {root}: {rel!r}")
    return path


def validate_node_spec(repo: str, folder: str, commit: str) -> None:
    """Raise ``ValueError`` unless the custom node source is a GitHub https URL,
    the folder a plain name and the commit a full 40-character SHA-1."""
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        raise ValueError(f"custom node repo must be https://github.com/<owner>/<name>: {repo!r}")
    if not is_safe_name(folder):
        raise ValueError(f"custom node folder must be a plain name: {folder!r}")
    if not isinstance(commit, str) or not _COMMIT_RE.match(commit):
        raise ValueError(f"custom node commit must be a full 40-character hex SHA: {commit!r}")


def token_allowed(url: str, hosts: Iterable[str] = HF_TOKEN_HOSTS) -> bool:
    """True when a bearer token may be sent to ``url`` (https and an allowed host)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return any(host == h or host.endswith("." + h) for h in hosts)


# -------------------------------------------------------------- download ----


def _human(n: int) -> str:
    """``1536`` -> ``"1.5 KB"`` (decimal units, like the Models tab)."""
    value = float(n)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "bytes" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} GB"


def network_message(url: str, err: BaseException) -> str:
    """Plain words for a connection failure, with the next step."""
    reason = getattr(err, "reason", err)
    text = str(reason)
    if isinstance(reason, socket.gaierror) or "getaddrinfo" in text:
        why = "the address could not be looked up (no internet connection?)"
    elif isinstance(reason, ConnectionRefusedError) or "10061" in text or "refused" in text.lower():
        why = "the connection was refused (a proxy or firewall may be blocking it)"
    elif isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in text.lower():
        why = "the connection timed out"
    else:
        why = text or type(err).__name__
    host = urlparse(url).hostname or url
    return (
        f"Could not reach {host}: {why}. Check the internet connection and any proxy or firewall, "
        "then press Download again (a partly downloaded file is kept and resumes)."
    )


def part_path(dest: Path) -> Path:
    """The temporary ``<name>.part`` file a download is written to before the rename."""
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


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _open(
    url: str,
    headers: dict[str, str],
    opener: Callable[..., Any] = urlopen,
    timeout: float = 60.0,
    authorization: str | None = None,
) -> Any:
    req = Request(url, headers=headers, method="GET")
    if authorization:
        # Unredirected: urllib must not forward the token to the redirect target.
        req.add_unredirected_header("Authorization", authorization)
    return opener(req, timeout=timeout)


def download_file(
    url: str,
    dest: Path,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    token: str | None = None,
    progress: ProgressFn | None = None,
    cancel: CancelFn | None = None,
    opener: Callable[..., Any] = urlopen,
    min_free_bytes: int = 256 * 1024 * 1024,
    token_hosts: Iterable[str] = HF_TOKEN_HOSTS,
    _fresh_retry: bool = False,
) -> DownloadResult:
    """Download ``url`` to ``dest`` with resume (HTTP Range), verification and
    atomic rename. Raises :class:`DownloadError` with a user-facing ``code``.

    ``token`` is sent as ``Authorization: Bearer`` only when ``url`` is https on
    one of ``token_hosts``; it is never put in the URL and never forwarded on a
    redirect. Data goes to ``<dest>.part`` first; the size and the SHA-256 (when
    known) are checked before the ``.part`` file is renamed onto ``dest``.
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
    authorization = f"Bearer {token}" if token and token_allowed(url, token_hosts) else None
    if offset:
        headers["Range"] = f"bytes={offset}-"

    try:
        resp = _open(url, headers, opener, authorization=authorization)
    except HTTPError as err:
        err.close()  # release the connection; only the status code is used
        if err.code in (401, 403):
            raise DownloadError(
                "auth",
                f"HTTP {err.code}: this file is gated. Accept the license on the model page "
                "and enter a Hugging Face access token in the settings.",
            ) from err
        if err.code == 404:
            raise DownloadError("notfound", f"HTTP 404: the file is no longer at {url}") from err
        if err.code == 416 and offset:
            # The partial file is already complete (or the server disagrees); verify below.
            resp = None
        else:
            raise DownloadError("network", f"HTTP {err.code} while fetching {url}") from err
    except (URLError, OSError) as err:
        raise DownloadError("network", network_message(url, err)) from err

    written = 0
    resumed_from = offset
    if resp is not None:
        with resp:
            status = getattr(resp, "status", None) or resp.getcode()
            length = resp.headers.get("Content-Length")
            total: int | None = None
            if status == 206 and offset:
                match = _CONTENT_RANGE_RE.match(resp.headers.get("Content-Range") or "")
                if match and int(match.group(1)) != offset:
                    _unlink_quietly(part)
                    raise DownloadError(
                        "network",
                        f"server resumed at byte {match.group(1)}, expected {offset}; "
                        "the partial file was deleted, retry to start over",
                    )
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
                    free: int | None = shutil.disk_usage(dest.parent).free
                except OSError:
                    free = None
                if free is not None and free < (total - offset) + min_free_bytes:
                    raise DownloadError(
                        "disk",
                        f"not enough disk space on {dest.parent.anchor or dest.parent}: the download needs "
                        f"{_human(total - offset + min_free_bytes)} (with a safety margin), {_human(free)} is free. "
                        "Free up space on that drive, then press Download again.",
                    )
            limit = expected_size or total
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
                        if limit and offset + written + len(block) > limit:
                            raise DownloadError("size", f"server sent more than the expected {limit} bytes")
                        fh.write(block)
                        written += len(block)
                        now = time.monotonic()
                        if progress and (now - last_report >= 0.5 or (total and offset + written >= total)):
                            last_report = now
                            speed = written / max(1e-6, now - started)
                            progress(offset + written, total, speed)
            except DownloadError as err:
                if err.code == "size":
                    _unlink_quietly(part)  # oversized data is never resumable
                raise
            except OSError as err:
                if err.errno in (errno.ENOSPC, 28) or "No space" in str(err):
                    raise DownloadError(
                        "disk",
                        f"the disk filled up during the download ({dest.parent.anchor or dest.parent}). Free up "
                        "space on that drive, then press Download again; the part already downloaded is kept.",
                    ) from err
                raise DownloadError("network", f"read/write error: {err}") from err

    final_size = part.stat().st_size if part.is_file() else 0
    if expected_size and final_size != expected_size:
        raise DownloadError(
            "size", f"downloaded {final_size} bytes, expected {expected_size}; the partial file is kept for resume"
        )
    digest = None
    if expected_sha256:
        digest = _sha256_of(part, cancel)
        if digest != expected_sha256:
            part.unlink()
            if resumed_from and not _fresh_retry:
                # the bytes kept from an earlier attempt were bad (a corrupt .part): fetch once from zero
                return download_file(
                    url,
                    dest,
                    expected_size,
                    expected_sha256,
                    token,
                    progress,
                    cancel,
                    opener,
                    min_free_bytes,
                    token_hosts,
                    _fresh_retry=True,
                )
            raise DownloadError(
                "hash",
                f"checksum mismatch for {dest.name}: got {digest[:12]}..., "
                f"expected {expected_sha256[:12]}...; the file was deleted",
            )
    elif part.is_file():
        digest = _sha256_of(part, cancel)
    os.replace(part, dest)
    return DownloadResult(dest, written, digest, resumed_from)


# ---------------------------------------------------------- custom nodes ----


def git_executable() -> str:
    """Path of ``git`` (PATH first, then the default Git for Windows locations)."""
    for name in ("git", "git.exe"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            p = Path(d) / name
            if p.is_file():
                return str(p)
    for p in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe"):
        if Path(p).is_file():
            return p
    return "git"


def install_custom_node(
    repo: str,
    folder: str,
    commit: str,
    custom_nodes_dir: Path,
    python: Path,
    log: Callable[[str], None] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> Path:
    """Clone ``repo`` into ``custom_nodes_dir/folder`` at ``commit`` and install
    its requirements with ``python``. Idempotent: an existing clone is reset to
    the pinned commit.

    Every command is an argument list (never a shell). ``repo``, ``folder`` and
    ``commit`` are checked with :func:`validate_node_spec` first, and the
    checked-out ``HEAD`` must equal ``commit`` before pip runs.
    """
    validate_node_spec(repo, folder, commit)
    log = log or (lambda _msg: None)
    git = git_executable()
    target = Path(custom_nodes_dir) / folder
    kw: dict[str, Any] = {"capture_output": True, "text": True}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    if not (target / ".git").is_dir():
        log(f"cloning {repo} -> {target}")
        r = runner([git, "clone", "--quiet", "--", repo, str(target)], **kw)
        if r.returncode != 0:
            raise RuntimeError(f"git clone failed: {r.stderr.strip() or r.stdout.strip()}")
    log(f"checking out {commit}")
    runner([git, "-C", str(target), "fetch", "--quiet", "origin"], **kw)  # best effort; offline is fine
    r = runner([git, "-C", str(target), "checkout", "--quiet", commit], **kw)
    if r.returncode != 0:
        raise RuntimeError(f"git checkout {commit} failed: {r.stderr.strip() or r.stdout.strip()}")
    r = runner([git, "-C", str(target), "rev-parse", "HEAD"], **kw)
    head = (r.stdout or "").strip()
    if r.returncode != 0 or head != commit:
        raise RuntimeError(f"{folder} is at {head or 'an unknown commit'}, expected the pinned {commit}")
    req = target / "requirements.txt"
    if req.is_file():
        log(f"installing requirements with {python}")
        r = runner([str(python), "-s", "-m", "pip", "install", "--no-warn-script-location", "-r", str(req)], **kw)
        if r.returncode != 0:
            raise RuntimeError(f"pip install failed: {(r.stderr or r.stdout).strip()[-800:]}")
    return target

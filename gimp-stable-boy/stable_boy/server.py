# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""ServerManager: find a healthy backend or start one, hidden.

The plug-in process is short-lived, so the long-running work is delegated to
``supervisor.py`` (a detached process). This module only knows how to read
the supervisor's state file, health-check the URL and launch the supervisor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from .backend import BackendUnavailable
from .comfy_api import ComfyClient
from .config import Paths, Settings, comfy_layout

ProgressCallback = Callable[[float, str], None]
IS_WINDOWS = sys.platform == "win32"


def _hidden_python() -> str:
    """Interpreter for the supervisor: the console-less twin of ours if any."""
    exe = Path(sys.executable)
    if IS_WINDOWS:
        for name in ("pythonw.exe", "pythonw3.exe"):
            candidate = exe.with_name(name)
            if candidate.exists():
                return str(candidate)
    return str(exe)


class ServerManager:
    def __init__(self, settings: Settings, paths: Paths, logger=None) -> None:
        self.settings = settings
        self.paths = paths
        self.log = logger

    # state ---------------------------------------------------------------

    def read_state(self) -> dict:
        try:
            return json.loads(self.paths.state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self, state: dict) -> None:
        tmp = self.paths.state.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, self.paths.state)

    def touch(self) -> None:
        """Record activity so the idle timeout restarts."""
        state = self.read_state()
        if state:
            state["last_used"] = time.time()
            try:
                self._write_state(state)
            except OSError:
                pass

    def request_stop(self) -> bool:
        """Ask the supervisor to shut the backend down. Returns True if asked."""
        state = self.read_state()
        if not state:
            return False
        state["stop"] = True
        try:
            self._write_state(state)
        except OSError:
            return False
        if self.log:
            self.log.info("stop requested for backend pid %s", state.get("server_pid"))
        return True

    # health --------------------------------------------------------------

    def url(self) -> str:
        state = self.read_state()
        return state.get("url") or self.settings.active_url

    def is_healthy(self, url: str | None = None) -> bool:
        if self.settings.backend == "a1111":
            from .backends.a1111 import A1111Backend
            return A1111Backend(url or self.settings.a1111_url).health().ok
        return ComfyClient(url or self.url()).is_alive()

    # start ---------------------------------------------------------------

    def ensure_running(self, progress: ProgressCallback | None = None) -> str:
        """Return a healthy base URL, starting the backend if allowed."""
        url = self.url()
        if self.is_healthy(url):
            self.touch()
            return url
        if self.settings.backend == "a1111":
            raise BackendUnavailable(
                f"AUTOMATIC1111 WebUI is not answering at {self.settings.a1111_url}. "
                "Start it with --api, or switch the backend to ComfyUI in the settings.")
        if not self.settings.autostart:
            raise BackendUnavailable(
                f"ComfyUI is not answering at {url} and auto-start is disabled in the settings.")
        return self.start(progress)

    def start(self, progress: ProgressCallback | None = None) -> str:
        layout = comfy_layout(self.settings.comfy_dir)
        if layout is None:
            raise BackendUnavailable(
                f"ComfyUI was not found at '{self.settings.comfy_dir}'. Install the portable "
                "build there or set the ComfyUI folder in Filters > AI > Generative Fill Settings.")
        self.paths.ensure()
        url = self.settings.url
        host, port = _split_host_port(url)
        gimp_pid = os.getppid()
        cmd = [
            _hidden_python(), str(Path(__file__).with_name("supervisor.py")),
            "--python", str(layout["python"]), "--main", str(layout["main"]),
            "--cwd", str(layout["cwd"]), "--host", host, "--port", str(port),
            "--state", str(self.paths.state), "--server-log", str(self.paths.server_log),
            "--log", str(self.paths.log), "--watch-pid", str(gimp_pid),
            "--idle-minutes", str(self.settings.idle_timeout_minutes),
        ]
        if self.settings.extra_server_args.strip():
            cmd += ["--extra-args", self.settings.extra_server_args.strip()]
        if self.log:
            self.log.info("launching supervisor (gimp pid %s): %s", gimp_pid, " ".join(cmd))
        self._spawn_detached(cmd)
        return self._wait_ready(url, progress)

    def _spawn_detached(self, cmd: list[str]) -> None:
        kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        kwargs["env"] = env
        if IS_WINDOWS:
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                     | subprocess.CREATE_NEW_PROCESS_GROUP)
            try:
                subprocess.Popen(cmd, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kwargs)
                return
            except OSError as err:
                if self.log:
                    self.log.info("breakaway spawn refused (%s); retrying without it", err)
                subprocess.Popen(cmd, creationflags=flags, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)

    def _wait_ready(self, url: str, progress: ProgressCallback | None) -> str:
        client = ComfyClient(url)
        timeout = max(30, int(self.settings.startup_timeout))
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            elapsed = time.monotonic() - started
            if progress:
                progress(min(0.95, elapsed / timeout), f"Starting the AI backend... {int(elapsed)} s")
            if client.is_alive(timeout=2.0):
                self.touch()
                if self.log:
                    self.log.info("backend ready at %s after %.0f s", url, elapsed)
                return url
            state = self.read_state()
            if state.get("status") == "failed" or (elapsed > 15 and not state):
                break
            time.sleep(1.5)
        raise BackendUnavailable(
            f"ComfyUI did not come up at {url} within {timeout} s. "
            f"Last log lines:\n{self.server_log_tail()}")

    def server_log_tail(self, lines: int = 8) -> str:
        try:
            text = self.paths.server_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "(no backend log yet)"
        return "\n".join(text.strip().splitlines()[-lines:])


def _split_host_port(url: str) -> tuple[str, int]:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.hostname or "127.0.0.1", parsed.port or 8188

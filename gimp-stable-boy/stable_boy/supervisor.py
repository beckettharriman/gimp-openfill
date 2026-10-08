#!/usr/bin/env python3
# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend supervisor: a tiny detached process that owns the ComfyUI server
and runs long tasks (model downloads, custom node installs) for the plug-in.

GIMP plug-in processes are short-lived, so something else has to keep the
server warm between calls, shut it down when GIMP exits, enforce the idle
timeout and carry on downloading after the dialog closed. This script is that
something. It is started by ``server.py`` with ``pythonw`` (no console).

Modes:
  --mode backend (default): start ComfyUI hidden (CREATE_NO_WINDOW, output to
      a log file, Job Object with KILL_ON_JOB_CLOSE), write server-state.json,
      exit when the watched GIMP pid disappears / idle timeout / stop request;
      also process tasks.
  --mode tasks: no backend; process queued tasks and exit when the queue has
      been empty for a while. Used when a download is requested while the
      backend is not running.

Tasks are JSON files in ``<base>/tasks/``; progress goes to
``<base>/tasks-status.json`` which the plug-in polls. A ``cancel`` file in the
tasks folder cancels the running task.

Depends only on the standard library plus ``downloads.py`` next to it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stable_boy import downloads  # noqa: E402

IS_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------- windows ----

def _job_object_for_child(pid: int):
    """Create a Job Object that kills ``pid`` when the handle closes."""
    if not IS_WINDOWS:
        return None
    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                    ("SchedulingClass", ctypes.c_uint32)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    PROCESS_TERMINATE, PROCESS_SET_QUOTA = 0x0001, 0x0100
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info),
                                       ctypes.sizeof(info)):
        return None
    handle = k32.OpenProcess(PROCESS_TERMINATE | PROCESS_SET_QUOTA, False, pid)
    if handle and k32.AssignProcessToJobObject(job, handle):
        k32.CloseHandle(handle)
        return job  # keep the job handle alive for the life of the supervisor
    return None


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        SYNCHRONIZE = 0x00100000
        handle = k32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return k32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT -> still running
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ------------------------------------------------------------------ state ----

def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def server_busy(url: str) -> bool | None:
    """True/False from ``/queue``; None if the server did not answer."""
    try:
        with urlopen(url.rstrip("/") + "/queue", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return bool(data.get("queue_running")) or bool(data.get("queue_pending"))
    except Exception:
        return None


class Logger:
    def __init__(self, path: Path, tag: str) -> None:
        self.path = path
        self.tag = tag
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str, level: str = "INFO") -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {level:5s} [{os.getpid()} {self.tag}] {msg}\n")
        except OSError:
            pass


# ---------------------------------------------------------------- backend ----

class Backend:
    """The ComfyUI child process."""

    def __init__(self, cmd: list[str], cwd: str, log_path: str, log: Logger) -> None:
        self.cmd = cmd
        self.cwd = cwd
        self.log_path = log_path
        self.log = log
        self.child: subprocess.Popen | None = None
        self.job = None
        self.log_file = None

    def start(self) -> None:
        popen_kwargs: dict = {}
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)  # GIMP's interpreter paths must not leak into ComfyUI
        env.pop("PYTHONHOME", None)
        env["PYTHONIOENCODING"] = "utf-8"
        self.log_file = open(self.log_path, "ab", buffering=0)
        self.log(f"starting backend: {' '.join(self.cmd)}")
        self.child = subprocess.Popen(self.cmd, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=self.log_file,
                                      stderr=subprocess.STDOUT, env=env, **popen_kwargs)
        self.job = _job_object_for_child(self.child.pid)
        self.log(f"backend pid {self.child.pid}, job object {'ok' if self.job else 'unavailable'}")

    @property
    def pid(self) -> int:
        return self.child.pid if self.child else 0

    def alive(self) -> bool:
        return self.child is not None and self.child.poll() is None

    def stop(self) -> None:
        child, self.child = self.child, None
        if child is None:
            return
        if child.poll() is None:
            try:
                child.terminate()
                child.wait(timeout=15)
                self.log("backend terminated")
            except Exception:
                try:
                    child.kill()
                    child.wait(timeout=5)
                    self.log("backend killed")
                except Exception as err:
                    self.log(f"could not stop backend: {err}", "ERROR")
        if self.log_file:
            try:
                self.log_file.close()
            except OSError:
                pass
            self.log_file = None
        self.job = None


# ------------------------------------------------------------------ tasks ----

class TaskWorker:
    """Processes ``<base>/tasks/*.json`` one at a time in a thread."""

    def __init__(self, base: Path, config_path: Path, log: Logger, on_restart_backend=None) -> None:
        self.base = base
        self.tasks_dir = base / "tasks"
        self.status_path = base / "tasks-status.json"
        self.config_path = config_path
        self.log = log
        self.on_restart_backend = on_restart_backend
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.last_activity = time.time()
        self.status: dict = {"worker_pid": os.getpid(), "current": None, "queue": [], "history": []}
        self._thread = threading.Thread(target=self._run, name="tasks", daemon=True)

    # queue helpers -----------------------------------------------------

    def pending(self) -> list[Path]:
        return sorted(p for p in self.tasks_dir.glob("*.json") if not p.name.endswith(".running.json"))

    def cancel_requested(self) -> bool:
        return (self.tasks_dir / "cancel").exists()

    def _clear_cancel(self) -> None:
        try:
            (self.tasks_dir / "cancel").unlink()
        except OSError:
            pass

    def _write_status(self) -> None:
        with self._lock:
            self.status["updated"] = time.time()
            self.status["queue"] = [p.stem for p in self.pending()]
            try:
                write_json(self.status_path, self.status)
            except OSError:
                pass

    def _set_current(self, **fields) -> None:
        with self._lock:
            if self.status["current"] is None:
                self.status["current"] = {}
            self.status["current"].update(fields)
        self._write_status()

    def _finish(self, task: dict, state: str, message: str = "", **extra) -> None:
        with self._lock:
            entry = {"task_id": task.get("id"), "type": task.get("type"), "model_id": task.get("model_id"),
                     "state": state, "message": message, "finished": time.time(), **extra}
            self.status["history"] = ([entry] + self.status["history"])[:30]
            self.status["current"] = None
        self.last_activity = time.time()
        self._write_status()
        self.log(f"task {task.get('id')} {state}: {message}")

    # lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._write_status()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def idle_for(self) -> float:
        return time.time() - self.last_activity

    def busy(self) -> bool:
        with self._lock:
            return self.status["current"] is not None or bool(self.pending())

    def _run(self) -> None:
        while not self._stop.is_set():
            tasks = self.pending()
            if not tasks:
                self._stop.wait(1.0)
                continue
            path = tasks[0]
            running = path.with_name(path.stem + ".running.json")
            try:
                os.replace(path, running)  # atomic claim
            except OSError:
                continue
            task = read_json(running)
            self._clear_cancel()
            self.last_activity = time.time()
            try:
                if task.get("type") == "download":
                    self._download(task)
                elif task.get("type") == "install_nodes":
                    self._install_nodes(task)
                elif task.get("type") == "remove":
                    self._remove(task)
                else:
                    self._finish(task, "error", f"unknown task type {task.get('type')}")
            except downloads.DownloadError as err:
                self._finish(task, "cancelled" if err.code == "cancelled" else "error", str(err), code=err.code)
            except Exception as err:  # noqa: BLE001 - must never kill the worker
                self._finish(task, "error", f"{type(err).__name__}: {err}")
            finally:
                try:
                    running.unlink()
                except OSError:
                    pass
                self._clear_cancel()

    # task types --------------------------------------------------------

    def _token(self) -> str:
        return str(read_json(self.config_path).get("hf_token", "") or "")

    def _download(self, task: dict) -> None:
        root = Path(task["models_root"])
        files = task["files"]
        total_all = sum(int(f.get("size") or 0) for f in files)
        done_before = 0
        results = []
        for index, f in enumerate(files):
            dest = root / f["dest"]
            if f.get("optional") and dest.is_file():
                continue
            self._set_current(task_id=task.get("id"), type="download", model_id=task.get("model_id"),
                              file=f["dest"], file_index=index, file_count=len(files), done=done_before,
                              total=total_all, speed=0.0, state="downloading", started=time.time())

            def progress(done, total, speed, _base=done_before):
                self._set_current(done=_base + done, total=total_all or (total or 0), speed=speed,
                                  file_done=done, file_total=total)

            token = self._token() if f.get("gated") or task.get("use_token") else None
            self.log(f"download {f['url']} -> {dest}")
            result = downloads.download_file(f["url"], dest, f.get("size"), f.get("sha256"), token or None,
                                             progress, self.cancel_requested)
            results.append({"dest": f["dest"], "sha256": result.sha256, "skipped": result.skipped,
                            "resumed_from": result.resumed_from})
            done_before += int(f.get("size") or result.bytes_written or 0)
        self._finish(task, "done", f"{len(results)} file(s) ready", files=results)

    def _install_nodes(self, task: dict) -> None:
        nodes_dir = Path(task["custom_nodes_dir"])
        python = Path(task["python"])
        for n in task["nodes"]:
            self._set_current(task_id=task.get("id"), type="install_nodes", model_id=task.get("model_id"),
                              file=n["folder"], state="installing", done=0, total=0, started=time.time())
            downloads.install_custom_node(n["repo"], n["folder"], n["commit"], nodes_dir, python, self.log)
        if self.on_restart_backend and task.get("restart_backend", True):
            self._set_current(state="restarting backend")
            self.on_restart_backend()
        self._finish(task, "done", "custom nodes installed" + (" and backend restarted" if self.on_restart_backend else ""))

    def _remove(self, task: dict) -> None:
        root = Path(task["models_root"])
        removed = []
        for rel in task["files"]:
            if ".." in rel.split("/") or rel.startswith(("/", "\\")):
                continue
            for p in (root / rel, root / (rel + ".part")):
                if p.is_file():
                    p.unlink()
                    removed.append(str(p))
        self._finish(task, "done", f"removed {len(removed)} file(s)", removed=removed)


# ------------------------------------------------------------------- main ----

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stable Boy backend supervisor")
    parser.add_argument("--mode", choices=("backend", "tasks"), default="backend")
    parser.add_argument("--python", default="", help="interpreter that runs ComfyUI")
    parser.add_argument("--main", default="", help="path to ComfyUI main.py")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument("--base", required=True, help="the plug-in's folder in the GIMP profile")
    parser.add_argument("--config", default="", help="config.json (for the Hugging Face token)")
    parser.add_argument("--watch-pid", type=int, default=0, help="exit when this pid ends")
    parser.add_argument("--idle-minutes", type=float, default=20.0, help="0 disables")
    parser.add_argument("--extra-args", default="", help="extra ComfyUI arguments")
    args = parser.parse_args(argv)

    base = Path(args.base)
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / "server-state.json"
    worker_path = base / "tasks-worker.json"
    config_path = Path(args.config) if args.config else base / "config.json"
    log = Logger(base / "stable-boy.log", "supervisor")

    if args.mode == "tasks":
        return run_tasks_only(base, worker_path, state_path, config_path, log)
    return run_backend(args, base, state_path, worker_path, config_path, log)


def run_tasks_only(base: Path, worker_path: Path, state_path: Path, config_path: Path, log: Logger) -> int:
    existing = read_json(worker_path)
    if existing.get("pid") and pid_alive(int(existing["pid"])) and existing["pid"] != os.getpid():
        log(f"another task worker ({existing['pid']}) is alive; exiting")
        return 0
    status = read_json(base / "tasks-status.json")
    if status.get("worker_pid") and pid_alive(int(status["worker_pid"])) and status["worker_pid"] != os.getpid():
        log("backend supervisor is alive and handles tasks; exiting")
        return 0
    write_json(worker_path, {"pid": os.getpid(), "started": time.time(), "mode": "tasks"})

    def ask_backend_restart() -> None:
        """No backend of our own: flag the backend supervisor (if any) to restart."""
        state = read_json(state_path)
        if state.get("supervisor_pid") and pid_alive(int(state["supervisor_pid"])):
            state["restart_backend"] = True
            write_json(state_path, state)
            log("asked the backend supervisor to restart ComfyUI")

    worker = TaskWorker(base, config_path, log, on_restart_backend=ask_backend_restart)
    worker.start()
    log("task worker started (no backend)")
    try:
        while True:
            time.sleep(2.0)
            if not worker.busy() and worker.idle_for() > 30:
                break
            if read_json(state_path).get("supervisor_pid") not in (None, os.getpid()):
                if not worker.busy():
                    break  # a backend supervisor appeared; let it take over
    finally:
        worker.stop()
        try:
            worker_path.unlink()
        except OSError:
            pass
        log("task worker exiting")
    return 0


def run_backend(args, base: Path, state_path: Path, worker_path: Path, config_path: Path, log: Logger) -> int:
    existing = read_json(state_path)
    if existing.get("supervisor_pid") and pid_alive(int(existing["supervisor_pid"])) \
            and existing.get("supervisor_pid") != os.getpid():
        log(f"another supervisor ({existing['supervisor_pid']}) is alive; exiting")
        return 0

    cmd = [args.python, "-s", args.main, "--listen", args.host, "--port", str(args.port),
           "--disable-auto-launch", "--dont-print-server", "--preview-method", "taesd"]
    if args.extra_args.strip():
        cmd += args.extra_args.split()
    url = f"http://{args.host}:{args.port}"

    backend = Backend(cmd, args.cwd, str(base / "comfyui.log"), log)
    backend.start()
    log(f"watching gimp pid {args.watch_pid}")

    now = time.time()
    state = {
        "supervisor_pid": os.getpid(), "server_pid": backend.pid, "url": url, "port": args.port,
        "host": args.host, "started": now, "last_used": now, "watch_pid": args.watch_pid,
        "idle_minutes": args.idle_minutes, "command": cmd, "status": "starting",
    }
    write_json(state_path, state)

    restart_lock = threading.Lock()

    def restart_backend() -> None:
        with restart_lock:
            log("restarting backend after node install")
            backend.stop()
            backend.start()
            current = read_json(state_path)
            current.update({"server_pid": backend.pid, "status": "starting", "started": time.time()})
            write_json(state_path, current)

    worker = None
    other_worker = read_json(worker_path)
    if not (other_worker.get("pid") and pid_alive(int(other_worker["pid"]))):
        worker = TaskWorker(base, config_path, log, on_restart_backend=restart_backend)
        worker.start()

    reason = "unknown"
    idle_limit = args.idle_minutes * 60.0 if args.idle_minutes > 0 else 0.0
    last_busy = now
    try:
        while True:
            time.sleep(2.0)
            if not backend.alive() and not restart_lock.locked():
                reason = f"backend exited with code {backend.child.returncode if backend.child else '?'}"
                break
            if args.watch_pid and not pid_alive(args.watch_pid):
                reason = f"GIMP (pid {args.watch_pid}) is gone"
                break
            current = read_json(state_path)
            if current.get("stop"):
                reason = "stop requested"
                break
            if current.get("supervisor_pid") not in (None, os.getpid()):
                reason = "state file taken over by another supervisor"
                backend.child = None  # do not kill the other supervisor's server
                break
            if current.get("restart_backend"):
                current.pop("restart_backend", None)
                write_json(state_path, current)
                restart_backend()
                continue
            if worker is None:
                other = read_json(worker_path)
                if not (other.get("pid") and pid_alive(int(other["pid"]))):
                    worker = TaskWorker(base, config_path, log, on_restart_backend=restart_backend)
                    worker.start()
                    log("adopted task processing (standalone worker is gone)")
            last_used = float(current.get("last_used", state["last_used"]))
            busy = server_busy(url)
            if busy or (worker and worker.busy()):
                last_busy = time.time()
            if busy is not None and current.get("status") != "ready":
                current["status"] = "ready"
                write_json(state_path, current)
            if idle_limit and busy is False and not (worker and worker.busy()):
                idle_for = time.time() - max(last_used, last_busy)
                if idle_for > idle_limit:
                    reason = f"idle for {idle_for / 60:.1f} min (limit {args.idle_minutes:g})"
                    break
    finally:
        log(f"shutting down: {reason}")
        if worker:
            worker.stop()
        backend.stop()
        if backend.child is None and reason != "state file taken over by another supervisor":
            try:
                state_path.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

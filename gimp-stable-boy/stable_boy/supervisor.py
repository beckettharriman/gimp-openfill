#!/usr/bin/env python3
# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend supervisor: a tiny detached process that owns the ComfyUI server.

GIMP plug-in processes are short-lived, so something else has to keep the
server warm between calls, shut it down when GIMP exits and enforce the idle
timeout. This script is that something. It is started by ``server.py`` with
``pythonw`` (no console) and does the following:

* starts ComfyUI hidden (``CREATE_NO_WINDOW``), stdout/stderr to a log file;
* on Windows puts the child in a Job Object with KILL_ON_JOB_CLOSE so the
  server cannot outlive the supervisor;
* writes ``server-state.json`` (pids, port, timestamps) for the plug-in;
* exits (killing the server) when the watched GIMP pid disappears, when the
  idle timeout elapses with an empty queue, when the child dies, or when a
  ``stop`` request is written into the state file.

It deliberately depends on nothing but the standard library so it can be
launched from any interpreter.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

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
            return False  # no such process (or no access; treat as gone)
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

def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def server_busy(url: str) -> bool | None:
    """True/False from ``/queue``; None if the server did not answer."""
    try:
        with urlopen(url.rstrip("/") + "/queue", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return bool(data.get("queue_running")) or bool(data.get("queue_pending"))
    except Exception:
        return None


# ------------------------------------------------------------------- main ----

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stable Boy backend supervisor")
    parser.add_argument("--python", required=True, help="interpreter that runs ComfyUI")
    parser.add_argument("--main", required=True, help="path to ComfyUI main.py")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument("--state", required=True, help="server-state.json path")
    parser.add_argument("--server-log", required=True)
    parser.add_argument("--log", required=True, help="supervisor log file")
    parser.add_argument("--watch-pid", type=int, default=0, help="exit when this pid ends")
    parser.add_argument("--idle-minutes", type=float, default=20.0, help="0 disables")
    parser.add_argument("--extra-args", default="", help="extra ComfyUI arguments")
    args = parser.parse_args(argv)

    state_path = Path(args.state)
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} INFO  [{os.getpid()} supervisor] {msg}\n")

    # Refuse to run twice for the same state file.
    existing = read_state(state_path)
    if existing.get("supervisor_pid") and pid_alive(int(existing["supervisor_pid"])) \
            and existing.get("supervisor_pid") != os.getpid():
        log(f"another supervisor ({existing['supervisor_pid']}) is alive; exiting")
        return 0

    cmd = [args.python, "-s", args.main, "--listen", args.host, "--port", str(args.port),
           "--disable-auto-launch", "--dont-print-server"]
    if args.extra_args.strip():
        cmd += args.extra_args.split()
    url = f"http://{args.host}:{args.port}"

    popen_kwargs: dict = {}
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # GIMP's interpreter paths must not leak into ComfyUI
    env.pop("PYTHONHOME", None)
    env["PYTHONIOENCODING"] = "utf-8"

    server_log = open(args.server_log, "ab", buffering=0)
    log(f"starting backend: {' '.join(cmd)}")
    child = subprocess.Popen(cmd, cwd=args.cwd, stdin=subprocess.DEVNULL, stdout=server_log,
                             stderr=subprocess.STDOUT, env=env, **popen_kwargs)
    job = _job_object_for_child(child.pid)
    log(f"backend pid {child.pid}, job object {'ok' if job else 'unavailable'}, watching gimp pid {args.watch_pid}")

    now = time.time()
    state = {
        "supervisor_pid": os.getpid(), "server_pid": child.pid, "url": url, "port": args.port,
        "host": args.host, "started": now, "last_used": now, "watch_pid": args.watch_pid,
        "idle_minutes": args.idle_minutes, "command": cmd, "status": "starting",
    }
    write_state(state_path, state)

    reason = "unknown"
    idle_limit = args.idle_minutes * 60.0 if args.idle_minutes > 0 else 0.0
    last_busy = now
    try:
        while True:
            time.sleep(2.0)
            if child.poll() is not None:
                reason = f"backend exited with code {child.returncode}"
                break
            if args.watch_pid and not pid_alive(args.watch_pid):
                reason = f"GIMP (pid {args.watch_pid}) is gone"
                break
            current = read_state(state_path)
            if current.get("stop"):
                reason = "stop requested"
                break
            if current.get("supervisor_pid") not in (None, os.getpid()):
                reason = "state file taken over by another supervisor"
                job = None  # do not kill the other supervisor's server
                child = None  # type: ignore[assignment]
                break
            last_used = float(current.get("last_used", state["last_used"]))
            busy = server_busy(url)
            if busy:
                last_busy = time.time()
            if busy is not None and current.get("status") != "ready":
                current["status"] = "ready"
                write_state(state_path, current)
            if idle_limit and busy is False:
                idle_for = time.time() - max(last_used, last_busy)
                if idle_for > idle_limit:
                    reason = f"idle for {idle_for / 60:.1f} min (limit {args.idle_minutes:g})"
                    break
    finally:
        log(f"shutting down: {reason}")
        if child is not None:
            _terminate(child, log)
        try:
            server_log.close()
        except OSError:
            pass
        if child is not None:
            try:
                state_path.unlink()
            except OSError:
                pass
    return 0


def _terminate(child: subprocess.Popen, log) -> None:
    if child.poll() is not None:
        return
    try:
        child.terminate()
        child.wait(timeout=10)
        log("backend terminated")
    except Exception:
        try:
            child.kill()
            child.wait(timeout=5)
            log("backend killed")
        except Exception as err:
            log(f"could not stop backend: {err}")


if __name__ == "__main__":
    sys.exit(main())

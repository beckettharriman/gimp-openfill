# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inside a GUI GIMP: open every Stable Boy window interactively and capture
it, without ever generating, testing the backend or downloading.

Launch (PowerShell, isolated profile, never the user's own GIMP):

    $env:GIMP3_DIRECTORY = 'C:\\AI\\overnight-scratch\\gimp-profile-ux'
    $env:SB_TEST_UI_FILE = 'C:\\AI\\overnight-scratch\\ux-run\\ui-hooks.json'
    & 'C:\\Users\\...\\GIMP 3\\bin\\gimp-3.2.exe' --new-instance --no-splash `
        --batch-interpreter python-fu-eval `
        -b "exec(open(r'<repo>\\tests\\gimp_batch_ui_screenshots.py').read())"

SB_TEST_UI_FILE must be set before GIMP starts: the plug-in processes are
spawned by GIMP and inherit its environment, not this script's. This script
rewrites that JSON file before each call (the plug-in re-reads it), so the
hooks differ per dialog: ``autoclose`` answers Cancel after N seconds,
``settings_tab``, ``advanced`` (expanders open), ``mode`` ("remove"),
``fake_variations`` (picker with tinted copies of the selection) and
``progress_demo`` (the real progress window fed with scripted steps).

Each window is captured by a PowerShell helper (written next to the output)
that finds the window by its exact title among windows of processes whose
parent is this GIMP, renders it with PrintWindow (works when the window is
covered), crops the invisible resize border (DWM extended frame bounds),
scales to at most 1600 px wide and saves a PNG.
"""

import json
import os
import subprocess
import sys
import time
import traceback

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio  # noqa: E402

REPO = os.environ.get("SB_REPO", os.path.dirname(os.path.dirname(os.path.abspath(
    globals().get("__file__", r"C:\AI\overnight-scratch\ux-worktree\tests\x.py")))))
OUT = os.environ.get("SB_TEST_OUT", os.path.join(REPO, "docs", "screenshots"))
HOOKS = os.environ.get("SB_TEST_UI_FILE", "")
IMAGE = os.environ.get("SB_TEST_IMAGE", os.path.join(REPO, "tests", "data", "test-scene.png"))
WORK = os.environ.get("SB_TEST_WORK", os.path.join(os.environ.get("TEMP", OUT), "stable-boy-ui-shots"))
os.makedirs(OUT, exist_ok=True)
os.makedirs(WORK, exist_ok=True)
GIMP_PID = os.getppid()
report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "gimp_pid": GIMP_PID, "hooks_file": HOOKS,
          "cases": []}

CAPTURE_PS1 = r'''
param([string]$Title, [string]$Out, [int]$ParentPid, [string]$DelaysMs = "2500", [int]$TimeoutSec = 90,
      [int]$MaxWidth = 1600)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class SbWin {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
  public static IntPtr Find(string title, uint[] pids) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr p) {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512); GetWindowText(h, sb, 512);
      if (sb.ToString() != title) return true;
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (Array.IndexOf(pids, pid) < 0) return true;
      found = h; return false;
    }, IntPtr.Zero);
    return found;
  }
}
"@
[SbWin]::SetProcessDPIAware() | Out-Null
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$hwnd = [IntPtr]::Zero
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) {
  $pids = @([uint32]$ParentPid) + @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentPid" | ForEach-Object { [uint32]$_.ProcessId })
  $hwnd = [SbWin]::Find($Title, [uint32[]]$pids)
  if ($hwnd -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 250 }
}
if ($hwnd -eq [IntPtr]::Zero) { "NOT FOUND: $Title"; exit 2 }
$start = Get-Date
$i = 0
foreach ($d in ($DelaysMs -split ",")) {
  $wait = [int]$d - ((Get-Date) - $start).TotalMilliseconds
  if ($wait -gt 0) { Start-Sleep -Milliseconds $wait }
  $r = New-Object SbWin+RECT; [SbWin]::GetWindowRect($hwnd, [ref]$r) | Out-Null
  $f = New-Object SbWin+RECT
  if ([SbWin]::DwmGetWindowAttribute($hwnd, 9, [ref]$f, 16) -ne 0) { $f = $r }
  $w = $r.R - $r.L; $h = $r.B - $r.T
  if ($w -le 0 -or $h -le 0) { "EMPTY RECT: $Title"; exit 3 }
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc(); $ok = [SbWin]::PrintWindow($hwnd, $hdc, 2); $g.ReleaseHdc($hdc); $g.Dispose()
  $crop = New-Object System.Drawing.Rectangle ($f.L - $r.L), ($f.T - $r.T), ($f.R - $f.L), ($f.B - $f.T)
  $img = $bmp.Clone($crop, $bmp.PixelFormat); $bmp.Dispose()
  if ($img.Width -gt $MaxWidth) {
    $nh = [int]($img.Height * $MaxWidth / $img.Width)
    $small = New-Object System.Drawing.Bitmap $MaxWidth, $nh
    $g2 = [System.Drawing.Graphics]::FromImage($small)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($img, 0, 0, $MaxWidth, $nh); $g2.Dispose(); $img.Dispose(); $img = $small
  }
  $name = if ($i -eq 0) { $Out } else { $Out -replace "\.png$", "-$i.png" }
  $img.Save($name, [System.Drawing.Imaging.ImageFormat]::Png)
  "saved $name $($img.Width)x$($img.Height) printwindow=$ok rect=$($r.L),$($r.T),$w,$h"
  $img.Dispose()
  $i++
}
'''


def capture(title, out_name, delays_ms="2500"):
    script = os.path.join(WORK, "capture-window.ps1")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(CAPTURE_PS1)
    out = os.path.join(OUT, out_name)
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell",
                              "v1.0", "powershell.exe")
    return subprocess.Popen([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                             "-Title", title, "-Out", out, "-ParentPid", str(GIMP_PID), "-DelaysMs", delays_ms],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def set_hooks(**hooks):
    if not HOOKS:
        raise RuntimeError("SB_TEST_UI_FILE must be set in the environment GIMP was started with")
    with open(HOOKS, "w", encoding="utf-8") as fh:
        json.dump(hooks, fh)


def run_case(name, proc_name, title, out_name, hooks, image=None, delays_ms="2500", setup=None, names=()):
    case = {"case": name, "procedure": proc_name, "title": title, "hooks": hooks}
    try:
        set_hooks(**hooks)
        cap = capture(title, out_name, delays_ms) if out_name else None
        proc = Gimp.get_pdb().lookup_procedure(proc_name)
        config = proc.create_config()
        config.set_property("run-mode", Gimp.RunMode.INTERACTIVE)
        if image is not None:
            config.set_property("image", image)
            config.set_core_object_array("drawables", image.get_selected_layers() or image.get_layers()[:1])
        if setup:
            setup(config)
        t0 = time.time()
        result = proc.run(config)
        case["status"] = str(result.index(0))
        case["seconds"] = round(time.time() - t0, 1)
        if cap is not None:
            try:
                output, _ = cap.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                cap.kill()
                output = "capture timed out"
            case["capture"] = (output or "").strip()
            case["capture_rc"] = cap.returncode
        for index, extra in enumerate(names, start=1):  # later shots: <out>-<n>.png -> given names
            src = os.path.join(OUT, out_name[:-4] + f"-{index}.png")
            if os.path.exists(src):
                os.replace(src, os.path.join(OUT, extra))
    except Exception as err:  # noqa: BLE001
        case["error"] = f"{type(err).__name__}: {err}"
        case["traceback"] = traceback.format_exc()
    report["cases"].append(case)
    print(f"[sb-ui] {json.dumps(case, default=str)[:400]}")


try:
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(IMAGE))
    Gimp.Display.new(image)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 420, 300, 260, 200)
    Gimp.displays_flush()
    time.sleep(2)
    fill, expand, txt = ("python-fu-stable-boy-generative-fill", "python-fu-stable-boy-generative-expand",
                         "python-fu-stable-boy-text-to-image")
    settings = "python-fu-stable-boy-settings"

    def set_prompt(text):
        return lambda config: config.set_property("prompt", text)

    run_case("fill", fill, "Generative Fill", "fill-dialog.png", {"autoclose": 7}, image,
             setup=set_prompt("a weathered wooden bench, soft afternoon light"))
    run_case("fill-advanced", fill, "Generative Fill", "fill-dialog-advanced.png",
             {"autoclose": 7, "advanced": True}, image)
    run_case("fill-remove", fill, "Generative Fill", "fill-dialog-remove.png",
             {"autoclose": 7, "mode": "remove"}, image)
    run_case("expand", expand, "Generative Expand", "expand-dialog.png", {"autoclose": 7}, image,
             setup=set_prompt(""))
    run_case("txt2img", txt, "Text to Image", "text-to-image-dialog.png", {"autoclose": 7}, image,
             setup=set_prompt("a lighthouse on a cliff at dusk, oil painting"))
    run_case("settings-general", settings, "Generative Fill Settings", "settings-general.png", {"autoclose": 7})
    run_case("settings-advanced", settings, "Generative Fill Settings", "settings-general-advanced.png",
             {"autoclose": 7, "advanced": True})
    run_case("settings-models", settings, "Generative Fill Settings", "settings-models.png",
             {"autoclose": 8, "settings_tab": "models"}, delays_ms="3500")
    run_case("settings-models-token", settings, "Generative Fill Settings", "settings-models-token.png",
             {"autoclose": 8, "settings_tab": "models", "select_model": "flux1-fill-dev"}, delays_ms="3500")
    run_case("progress", fill, "Stable Boy - Generative Fill", "progress-window-start.png",
             {"progress_demo": 11}, image, delays_ms="1200,8500", names=("progress-window.png",))
    run_case("picker", fill, "Choose a variation - Generative Fill", "variations-picker.png",
             {"autoclose": 7, "fake_variations": 3}, image)
    # Keyboard behaviour, without generating: Enter in the prompt answers
    # Generate (dry_run records what reached the procedure config instead of
    # calling the backend); Escape cancels.
    dry_out = os.path.join(WORK, "dry-run.json")
    if os.path.exists(dry_out):
        os.remove(dry_out)
    run_case("keys-enter", fill, "Generative Fill", None,
             {"autoclose": 12, "type": "a red door with brass handles", "press": "Return", "dry_run": True,
              "dry_run_out": dry_out}, image, delays_ms="600")
    try:
        with open(dry_out, encoding="utf-8") as fh:
            report["cases"][-1]["dry_run"] = json.load(fh)
    except OSError as err:
        report["cases"][-1]["dry_run"] = f"missing: {err}"
    run_case("keys-escape", fill, "Generative Fill", None,
             {"autoclose": 12, "press": "Escape"}, image, delays_ms="600")
    run_case("history", fill, "Generative Fill", "fill-dialog-history.png", {"autoclose": 6}, image,
             setup=set_prompt(""))
    report["ok"] = all("error" not in c for c in report["cases"])
except Exception as err:  # noqa: BLE001
    report["ok"] = False
    report["error"] = f"{type(err).__name__}: {err}"
    report["traceback"] = traceback.format_exc()
    print(report["traceback"], file=sys.stderr)
finally:
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(WORK, "ui-screenshots-report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    if HOOKS:
        set_hooks()
    if os.environ.get("SB_TEST_QUIT", "1") == "1":
        q = Gimp.get_pdb().lookup_procedure("gimp-quit")
        cfg = q.create_config()
        cfg.set_property("force", True)
        q.run(cfg)

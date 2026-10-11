# Performance evidence (2026-10-09)

Raw data behind [docs/performance.md](../../../performance.md). Machine: AMD
Ryzen 9 8945HS laptop, 32 GB RAM, RTX 4070 Laptop GPU 8 GB (driver 610.88),
Windows 11, GIMP 3.2.6, ComfyUI 0.39.0 portable. 20 steps, 1 variation,
seed 1234 unless a plan says otherwise; the test image is the centre square
of `landscape.jpg` scaled to 2048 x 2048.

## Sessions

| Folder | What | Plug-in code |
|---|---|---|
| `tiers/` | cold start 1 (SD 1.5, 512 px), then every tier (SD 1.5, `quality` = SDXL + Fooocus, Juggernaut XL v9, MAT) at 512, 1024 and 2048 px selections, two runs each, plus the first call after each model switch | before the changes |
| `soak/` | cold start 2 (SD 1.5, 1024 px), then 20 consecutive SD 1.5 fills at 1024 px with memory and VRAM after each | before the changes |
| `after/` | cold start 3, SD 1.5 and Juggernaut re-runs of the same region with other seeds, one identical repeat | after the changes |
| `gui1/`, `gui8/` | GUI `gimp-3.2.exe`: a non-interactive warm-up fill (cold backend, Juggernaut), then one fill through the real dialog with the progress window; GIMP window pinged with `SendMessageTimeout(WM_NULL, 100 ms)` every 50 ms. `gui1` ran before the progress window fix (window invisible), `gui8` after it and is the session the README GIF was cut from | after the changes (`gui8` also with the progress window fix) |
| `progress-window-visibility/` | window title, style and visibility sampled every 0.5 s during a GUI fill before (`before-fix-watch.jsonl`, style `06c80000`, never visible) and after the fix (`after-fix-watch.jsonl`, `16c80000`); `standalone-check.py` shows the same window outside GIMP is visible | |
| `png-encode-bench.json` | `png.encode` time and size for 1024 and 2048 px photo crops at zlib levels 6, 1 and 0 | |
| `harness/` | the launcher, GUI driver, capture and analysis scripts used (they ran from a scratch folder; paths inside point there) | |

## Files in a session folder

- `batch-command.txt`: the exact command line and environment.
- `plan.json`: the cases, in order.
- `perf-results.jsonl`: one line per call from `tests/gimp_batch_perf.py`
  (epoch start and end, wall time, status, and the `openfill.log` lines of
  that call, including the `timing:` lines).
- `phases.csv` / `phases.json`: per call, the context crop, working size,
  PNG sizes and the split into plug-in start, export + checks, upload, queue
  to first step, sampling, download and insert (`harness/analyse.py`).
- `samples.jsonl`: every 0.5 s, the working set of `gimp-console`, of its
  child processes (plug-ins) and of ComfyUI's Python, and VRAM used.
- `launch-meta.json`: port 8188 state and VRAM before launch, launch and exit
  times, how long after GIMP exited port 8188 closed, VRAM afterwards.
- `cold-start.json`: the cold-start breakdown of the first call
  (`harness/cold.py`).
- `soak/soak.csv` / `soak.json`: memory, VRAM and wall time after each fill
  (`harness/soak_analyse.py`).
- GUI folders: `demo-events.jsonl` (driver events), `capture-events.jsonl`
  (window found, Enter posted to the dialog), `ping.jsonl` (every WM_NULL
  round trip), `gui-stats.json` (summary), `gif-frames.json` (which captured
  frames went into `docs/screenshots/generative-fill.gif`, and which idle
  stretches were cut).

The main-loop stall probe inside the plug-in (`OPENFILL_PERF_STALL=1`) writes
`perf: plug-in main loop max gap ...` to `openfill.log`; the values from
the eight GUI fills are quoted in performance.md.

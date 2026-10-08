# Floating progress window evidence (2026-10-08, GIMP 3.2.6 GUI, python-fu-eval)

Script: `tests/gimp_batch_progress.py`, launched in a fresh `gimp-3.2.exe
--new-instance` while an external PowerShell loop enumerated top-level windows
every 0.5 to 0.7 s, logged every sighting of a window titled "Stable Boy - ..."
and captured it (cropped to the window rectangle, DPI aware). Captures are
numbered in sighting order.

## normal/ (SD 1.5 fill, window enabled)

| Check | Evidence |
|---|---|
| Window appears when the generation starts | `window-sightings.txt`: 24 sightings between 15:28:47 and 15:29:04 (first one within a second of the procedure call) |
| Content | `window-12.png` (warm-up: "Running node sampler...", elapsed), `window-16.png` / `window-20.png` (sampling: "Generating... step 23/25", 92 %, elapsed 0:14, remaining 0:01, live TAESD preview of the boulder forming), title shows operation and model name |
| Preview stream | plug-in log: "progress window: 13 preview frame(s) shown, closing after success" (frames throttled to 4 per second) |
| Closes on success | last sighting 15:29:04.x, procedure finished 15:29:04, log "fill: done" 15:29:04; `batch-report.json` step `generative-fill` status 3 with the new masked layer |
| Status bar still updated | the `GimpProgress` mirror is driven from the same callbacks (idle callbacks on the main thread) |
| Position memory | second run (`cancel/`) opened at the remembered position (1240, 93) stored in `config.json` |

## cancel/ (same fill, Cancel pressed automatically at 30 %)

`SB_TEST_CANCEL_AT=0.3` makes the Runner press the window's Cancel button once
sampling passes 30 % (same code path as a click).

| Check | Evidence |
|---|---|
| Cancel reaches ComfyUI | plug-in log 15:30:48 "cancel requested from the progress window"; the wait loop sent `POST /interrupt` and `POST /queue {clear: true}`; `batch-report.json` step `comfy-queue`: running 0, pending 0 |
| Image untouched | step `generative-fill`: status 0 (EXECUTION_ERROR, message "Generation was cancelled."), `layers_after` identical to `layers_before`, `layer_added: false` |
| Window state | `window-24.png`: "Cancelled" at 32 %, last preview frame kept, message "Cancelled - the image was left unchanged.", Close button; the window closed itself 1.5 s later |
| No leftovers | process list after GIMP quit: no `python.exe` / `gimp-3.2.exe`; no `.part` files under `ComfyUI/models` |

## Not verified

- Download rows inside the window during a real multi-GB download (the
  downloads line is fed from the same `tasks-status.json` the Models tab
  reads; unit-tested formatting only).
- Positioning over the active image window on Linux/macOS (Windows uses the
  native handle GIMP reports; other platforms fall back to the top-right of
  the primary monitor).

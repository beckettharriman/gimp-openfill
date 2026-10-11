# End-to-end evidence (2026-10-08, Windows 11, GIMP 3.2.6, RTX 4070 Laptop 8 GB)

Every run below drove a real `gimp-3.2.exe` GUI instance through the
`python-fu-eval` batch interpreter with `tests/gimp_batch_fill.py`, which
opens `tests/data/test-scene.png`, creates a display, selects the dark box at
(420, 300, 260, 200), calls the registered procedures with
`run_mode=NONINTERACTIVE` via `Gimp.get_pdb().lookup_procedure(...).run(config)`,
exports the result, and quits GIMP through the `gimp-quit` PDB procedure.
The exact command line is in `batch-command.txt`.

The GIMP profile was shared with other plug-ins (PhotoGIMP, G'MIC, GEGL
effects); the `gegl_op_nop` / `port:load` warnings in `gimp-stderr.txt` come
from the LinuxBeaver GEGL effects, not from OpenFill.

## Run 1 - exit condition (files in this folder)

| Check | Evidence |
|---|---|
| Procedures registered, menu path | `pluginrc-excerpt.txt`; `batch-report.json` step `pdb-lookup` (all five true) and `menu` (`<Image>/Filters/AI`, label `Generative _Fill...`) |
| GUI instance | `process-snapshots.txt`: `gimp-3.2 pid=6980 ... title='*[01-before] ... 2 layers ...'` (main window handle non-zero) |
| Backend auto-started hidden | `plugin-log.txt` 14:15:47 "launching supervisor (gimp pid 6980)", 14:15:49 "backend pid 27932, job object ok"; snapshots show `python pid=27932 parent=12368 hwnd=0 path=...python_embeded\python.exe` and `pythonw pid=12368` (supervisor) with `hwnd=0`; no `conhost`/console attached to either (the earlier snapshot format listed consoles explicitly; none belonged to them) |
| Generative Fill result | `batch-report.json` step `generative-fill`: `status=3` (SUCCESS), 110.7 s including the 88 s cold start; layers afterwards: `Generative Fill: a large grey boulder on grass, photo` with `has_mask: true`, plus `Background` |
| Before / after | `01-before.png`, `02-after-fill.png` |
| ComfyUI side | `comfyui-log-excerpt.txt` (model load, `got prompt`, `Prompt executed`) |
| Shutdown on GIMP exit | `plugin-log.txt` 14:17:38 "shutting down: GIMP (pid 6980) is gone", 14:17:39 "backend terminated"; last snapshot after exit lists no python/pythonw/gimp processes; `server-state.json` removed |

## Run 2 - feature matrix and idle timeout (`run2/`)

Config had `idle_timeout_minutes = 1`; the script waited 150 s at the end
while GIMP stayed open.

| Step | Result |
|---|---|
| generative-fill | SUCCESS, 46.3 s (cold start 30 s) |
| generative-expand | FAILED: `INPAINT_MaskedFill: No module named 'cv2'` (fixed afterwards, see run 4) |
| generative-fill-variations (3) | SUCCESS, 12.5 s; group layer with three masked children, first visible |
| text-to-image-layer | SUCCESS, 6.3 s; `Text to Image: ...` layer, no mask |
| generative-fill-sdxl (Quality tier, Fooocus patch) | SUCCESS, 25.6 s at 768x768 |
| idle timeout | `process-snapshots-run2.txt`: ComfyUI present until 14:22:20, gone from 14:22:25 while `gimp-3.2` remained until 14:23:55; `plugin-log.txt` 14:22:22 "shutting down: idle for 1.0 min (limit 1)" |

`run2/06-after-sdxl.png` shows the state after all steps; the black strip on
the right is the canvas growth left behind by the failed expand (bug fixed in
the same session: the canvas now only grows after a successful generation).

## Run 4 - Generative Expand after installing OpenCV (`run4-expand/`)

| Step | Result |
|---|---|
| generative-fill | SUCCESS, 43 s |
| generative-expand (right +256 px) | SUCCESS, 11.6 s; canvas 1024x768 -> 1280x768; layer `Generative Expand: ...` with mask |
| Output | `run4-expand/03-after-expand.png` |

## Unit tests

`unit-tests.txt`: 59 tests, OK, under the system Python 3.13 without GIMP.

## Not verified

- The AUTOMATIC1111 backend (no WebUI installed on this machine).
- Linux/macOS install script paths (written from documentation, not executed).
- Interactive dialogs were exercised only through GIMP's own `ProcedureDialog`
  machinery in registration; the end-to-end runs used `NONINTERACTIVE` mode.

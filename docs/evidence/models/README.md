# Model catalog evidence (2026-10-08, GIMP 3.2.6 GUI instances via python-fu-eval)

Scripts: `tests/gimp_batch_models.py` (download, status, set active, removal
fill, node install, SD 1.5 fill), `tests/gimp_batch_models_restart.py`
(backend restart after a node install), `tests/gimp_batch_settings_dialog.py`
(dialog screenshot). Each run used its own `gimp-3.2.exe --new-instance`;
Beckett's own GIMP window stayed open and untouched throughout.

## batch-report.json (download / status / templates)

| Step | Result |
|---|---|
| catalog | 9 entries loaded; initial statuses: sd15/sdxl/fooocus Installed, FLUX entries "Needs token", others Available |
| download-queued | `mat-places512` queued (task `1791486012652-download`); no backend running, so a tasks-only supervisor was spawned |
| download-finished | state `done` after 5 s; sha256 `309dd6ce...` recorded |
| download-verified | file size 125,280,278 = catalog size; sha256 recomputed in GIMP = catalog hash (`match: true`) |
| status-after-download | `Installed` |
| download-again | second request returned `skipped: true` (already installed, nothing transferred) |
| set-active | active = `mat-places512`, template `inpaint_model`, prompt-free |
| removal-fill | Generative Fill with model "active" and an empty prompt: status 3 (SUCCESS), 34 s including backend start; layer `Object Removal` with mask; output `01-removal-mat.png` |
| nodes-needed / nodes-installed | `ComfyUI-GGUF @ 6ea2651e` cloned into `custom_nodes`, requirements installed with the embedded Python (`gguf` importable afterwards) |
| backend-restarted-with-gguf-nodes | **false** in this run: the task was executed by the tasks-only worker which has no backend to restart (bug found here, fixed: the backend supervisor now adopts task processing when the standalone worker exits, and a `restart_backend` flag is honoured) |
| sd15-fill-after | active switched back to `sd15-inpainting`; fill status 3, 24.5 s; layer with mask; output `02-sd15-fill.png` |

## restart-report.json (after the fix)

| Step | Result |
|---|---|
| backend-up | supervised backend pid 19524, `UnetLoaderGGUF` already served (nodes present from the previous run) |
| install-queued / install-finished | task handled by the backend supervisor's worker: "custom nodes installed and backend restarted" (4 s) |
| backend-restarted | `restarted: true`, server pid 19524 -> 28240, `UnetLoaderGGUF` present on the new process |
| settings-dialog | opened interactively, auto-closed, status 3 |

## Screenshots

- `settings-general-tab.png`: the Settings dialog, General tab (ProcedureDialog
  content inside a notebook).
- `settings-models-tab.png`: the Models tab with the catalog table (Active
  marker, tier, status, size, license, source), buttons and token field.
  Captured with a window-rect screen copy of the dialog only.

## Also in this folder

`catalog-url-check.txt` (one level up): HEAD results for all 37 catalog URLs
(pages, license pages, files), all resolving; gated BFL files answer 401 as
expected. `process-snapshots.txt`: process list every 10 s during the first
run (plug-in `python.exe` processes, `pythonw.exe` supervisor, ComfyUI
`python.exe`, all without a window handle).

## Not verified here

- Downloads of the FLUX, Qwen and Juggernaut entries (multi-GB; Beckett will
  run one himself). Their URLs, sizes and hashes were checked with HEAD only.
- The FLUX Fill and Qwen-Image-Edit workflow templates against real weights
  (built and link-checked by unit tests only).
- Gated download with a token (the 401 path is unit-tested against a stub).

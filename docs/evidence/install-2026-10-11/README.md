# Fresh-PC install test, 2026-10-11

A PC with nothing set up, simulated without touching the owner's setup:

- GIMP 3.2.6, new empty profile `gimp-profile-fresh` (`GIMP3_DIRECTORY`), plug-in put there by
  the release zip: `python tools/make_release_zip.py`, unzip, `Install OpenFill.cmd -ProfileDir ...`
  (3 s, no git on the PATH of the installer, `OPENFILL_NO_FIXED_ROOTS=1` so the owner's ComfyUI is
  not detected). The written `config.json` has no `comfy_dir`.
- The GUI GIMP was started with the same git-free PATH and `OPENFILL_INSTALL_DIR=fresh-comfy`
  (a test override of the default `%LOCALAPPDATA%\OpenFill\ComfyUI`).
- Driver: `tests/gimp_batch_install_flow.py` (run inside GIMP). Everything below is the real
  interactive Generative Fill procedure; windows are captured with PrintWindow as they appear.
- Input was scripted with the plug-in's test hooks (`setup_action` answers "Download ComfyUI",
  `models_starter_button` presses "Download both starting models", `type`/`press` and `click`
  answer Generate), not with the physical mouse: the PC was in use, and an earlier attempt with
  synthetic mouse clicks landed on another window and was dropped.
- Real downloads: ComfyUI portable 1.9 GB, LaMa 0.2 GB, DreamShaper 8 Inpainting 2.0 GB.
  GPU: RTX 4070 Laptop (8 GB). The test copies were deleted afterwards.

Contact sheets: `sheet-ui.png` (windows) and `sheet-results.png` (before/after).
Timings come from `log-excerpt.txt` and `report.json`.

| # | Step | What the user sees | Result | Time |
|---|---|---|---|---|
| 1 | Unzip OpenFill, double-click `Install OpenFill.cmd` | Console: plug-in copied, no ComfyUI found, next steps (Start GIMP, run Generative Fill, press Download ComfyUI when asked); "Press any key" | pass | 3 s |
| 2 | Open image, select sky, Filters > OpenFill > Generative Fill | Notice "ComfyUI is required": install folder with Change folder, graphics card (RTX 4070, 8 GB), free disk (needs 12 GB), port 8188 free; buttons Download ComfyUI (about 1.9 GB), I already have ComfyUI..., Cancel (`01-notice.png`) | pass | instant |
| 3 | Download ComfyUI | Progress window "Setting up ComfyUI": "Downloading ComfyUI: 345 MB of 1.9 GB", percent, elapsed, time left (`02-setup-progress-1.png`) | pass | 2:01 |
| 4 | (same task) verify, unpack | "Unpacking ComfyUI: x MB of about 6.2 GB" with a bar; Windows tar.exe read the .7z, no 7-Zip needed (`02-setup-progress-4.png`) | pass | 2:16 |
| 5 | (same task) nodes and packages | Inpaint nodes from the pinned GitHub zip (no git), opencv-python-headless installed; progress window closes, `comfy_dir` saved | pass | 8 s |
| 6 | Model manager opens | "Download the two starting models below to begin", button "Download both starting models (2.2 GB)", list with LaMa and DreamShaper first (`03-model-manager.png`) | pass | instant |
| 7 | Download both starting models | "Model downloads" window: 54 MB of 2.0 GB, queued DreamShaper (`04-model-downloads-1.png`); manager closes when both are installed | pass | 2:22 |
| 8 | Fill dialog | Generative Fill with prompt box, Model DreamShaper 8 Inpainting (`05-fill-dialog.png`) | pass | instant |
| 9 | Generate "hot air balloon" | "Starting the AI backend (first time takes about a minute)", then sampling with preview; layer "Generative Fill: hot air balloon" (`06-fill-progress-2.png`, `fill-after.png`) | pass | 76 s backend start, 13 s fill |
| 10 | Remove object (cup handle) | Remove dialog, LaMa used, layer "Object Removal"; handle gone (`07-remove-dialog.png`, `remove-after.png`) | pass | 5 s |

From pressing Download ComfyUI to the first finished fill: 8 min 25 s on this connection
(download 2:01, unpack 2:16, models 2:22, backend start 1:16, generation 13 s).

Friction found and fixed during the runs: the unpacked folder could not be renamed on Windows
(access denied while the virus scanner held files), so ComfyUI is now unpacked in place with a
marker for a cut-short unpack; unpacking had no progress (now measured by folder size); the model
manager needed two clicks and said "Open the download manager" (now one button and a plainer
message).

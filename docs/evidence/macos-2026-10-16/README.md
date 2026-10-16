# macOS end to end, 2026-10-16

MacBook Air M3 (16 GB unified memory), macOS 14.7, GIMP 3.2.6 (Homebrew cask,
the notarized GNOME Foundation build), PhotoGIMP 3.1 applied to the profile,
ComfyUI from git in `~/ComfyUI` with a Python 3.13 venv and PyTorch 2.14 (MPS).
OpenFill installed with `sh install.sh` (it found `~/ComfyUI` by itself).

All runs use the real GIMP through `python-fu-eval`; the drivers are next to
their reports. Command line (gimp-console for the generation runs, gimp-3.2 for
the GUI run):

    /Applications/GIMP.app/Contents/MacOS/gimp-console-3.2 --new-instance --no-splash \
        --console-messages --batch-interpreter python-fu-eval \
        -b "exec(open('driver.py').read())" -b "Gimp.get_pdb().lookup_procedure('gimp-quit').run(None)"

## launch-constraint/

Before the fix in `server.py`, the task worker the plug-in started with
`GIMP.app/Contents/MacOS/python3` was killed at once: `SIGKILL (Code Signature
Invalid)`, `CODESIGNING`, `Launch Constraint Violation`. Nothing reached
`supervisor-stderr.log`; queued downloads never started and the backend could
not start. `codesign.txt` shows the parent launch constraint on that binary.

## models/

The starter models through `App.queue_download` (what the Models tab does):
comfyui-inpaint-nodes at the pinned commit, LaMa (196 MB, 10 s) and
DreamShaper 8 Inpainting (2.1 GB, 90 s), both sha256-verified.

## e2e-with-opencv/

Eight cases on `tests/data/test-scene.png` with DreamShaper 8 active:

| case | result | seconds |
|---|---|---|
| fill with a prompt (backend cold start) | success, new layer | 88.9 |
| fill again (warm) | success | 57.5 |
| remove object (LaMa) | success | 3.6 |
| 3 variations | success, layer group | 208.8 |
| expand right by 256 px | success, canvas 1024 to 1280 | 190.4 |
| text to image (layer) | success | 104.8 |
| 24 px selection | success | 63.2 |
| fill without a selection | refused with "Nothing is selected..." | 1.5 |

## e2e-without-opencv/

The same expand before `opencv-python-headless` was installed in ComfyUI's
venv: OpenFill retries with a neutral pre-fill and the new border comes out as
a flat brown wall. Hence OpenCV in the README's macOS steps.

## gui/

Every OpenFill window opened interactively in a GUI GIMP (fill, remove,
advanced, expand, text to image, settings general and models), then a real
fill typed into the dialog and started with its Generate button (success,
25 live preview frames in the progress window).

## Robustness

`robustness-driver.py`, one case per GIMP start:

- Port 8188 held by another program: "Port 8188 is used by another program
  (it is not ComfyUI)..." in 1.2 s.
- `comfy_dir` pointing nowhere: "ComfyUI was not found in ..." in 0.8 s.
- GIMP killed with SIGKILL during a session: the supervisor stopped ComfyUI
  3 s later.
- GIMP quit normally: ComfyUI and the supervisor gone after every run.

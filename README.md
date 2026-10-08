# Stable Boy 2 - Generative Fill for GIMP 3

Photoshop-style **Generative Fill**, **Generative Expand** and **Text to Image**
inside GIMP 3, with the AI backend fully managed by the plug-in. Select an
area, type what should be there, press OK, and the result appears as a new
layer with a layer mask in the same image. No terminal, no browser tab, no
second application.

Stable Boy 2 is a GIMP 3 rewrite of [Stable Boy](https://github.com/thndrbrrr/gimp-stable-boy)
by Torben Giesselmann (thndrbrrr), the GIMP 2.10 plug-in for the AUTOMATIC1111
WebUI. Version 2 keeps the name, the license and the idea; the code, the
backend (ComfyUI, started and stopped by the plug-in) and the UX are new.

![Generative Fill before/after placeholder](docs/screenshots/generative-fill.png)
*(screenshot placeholder: selection on the left, filled layer with mask on the right)*

## What it does

| Menu entry (`Filters > AI`) | What happens |
|---|---|
| **Generative Fill...** | Fills the current selection from a prompt. The plug-in crops a context region around the selection, generates, and adds a new layer with a feathered layer mask. 1 to 8 variations go into a layer group. Strength below 1.0 keeps part of the original. |
| **Generative Expand...** | Grows the canvas by the margins you enter and outpaints the new border into a new masked layer. The image is untouched if generation fails. |
| **Text to Image...** | Generates from text into a new layer (sized to the selection when there is one) or a new image. |
| **Generative Fill Settings...** | Backend folder/URL, model tier and checkpoints, steps, CFG, sampler, mask grow/feather, idle timeout, and a "check backend now" button that lists the server's models. |
| **Stop AI Backend** | Shuts the managed ComfyUI process down to free the GPU. It restarts on the next request. |

Two model tiers, switchable per call:

- **Fast**: Stable Diffusion 1.5 inpainting checkpoint. A few seconds per fill on an RTX 4070 Laptop (8 GB).
- **Quality**: SDXL base plus the Fooocus inpaint patch (via comfyui-inpaint-nodes). Slower, noticeably better for large areas.

All generation is local. Nothing leaves the machine.

## How the backend is managed

GIMP plug-ins are short-lived processes, so Stable Boy launches a tiny
supervisor (`stable_boy/supervisor.py`, run with `pythonw`, no console) the
first time you need the backend. The supervisor:

- starts ComfyUI hidden (`CREATE_NO_WINDOW`, output to `comfyui.log`) and ties
  it to a Windows Job Object so it can never outlive the supervisor;
- watches the GIMP process and shuts the server down when GIMP exits;
- shuts it down after the configured idle timeout (default 20 minutes) so the
  model does not hold VRAM forever; the next request starts it again;
- writes `server-state.json` so later plug-in runs find the running server.

Progress is shown in GIMP's progress bar (step-level, via ComfyUI's websocket).
Errors come back as plain GIMP messages: backend not found, failed to start
(with the last log lines), missing model, out of VRAM, timeout.

## Requirements

- GIMP 3.2 or newer (tested with 3.2.6 on Windows 11). GIMP's bundled Python is
  used; the plug-in needs no extra Python packages.
- ComfyUI (tested with 0.39.0, Windows portable NVIDIA build) with
  [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes).
- An NVIDIA GPU with 8 GB VRAM is enough for both tiers. CPU-only works for the
  Fast tier but is slow.
- Models: see [docs/models.md](docs/models.md) for the exact files, sizes,
  checksums and licenses (about 4.3 GB for the Fast tier, 12.5 GB with Quality).

## Install

1. **ComfyUI.** Download the official portable build from the
   [Comfy-Org/ComfyUI releases](https://github.com/Comfy-Org/ComfyUI/releases)
   and extract it to `C:\AI\ComfyUI` (so that
   `C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI\main.py` exists), or point
   the settings dialog at any other ComfyUI checkout.
2. **Custom nodes.** `git clone https://github.com/Acly/comfyui-inpaint-nodes`
   into `ComfyUI\custom_nodes\`. For Generative Expand's border pre-fill also
   run `python_embeded\python.exe -s -m pip install opencv-python-headless`
   (without it the plug-in falls back to a neutral grey pre-fill).
3. **Models.** Put `sd-v1-5-inpainting.ckpt` into `ComfyUI\models\checkpoints\`.
   Optionally add `sd_xl_base_1.0.safetensors` there and
   `fooocus_inpaint_head.pth` + `inpaint_v26.fooocus.patch` into
   `ComfyUI\models\inpaint\` for the Quality tier. Links in
   [docs/models.md](docs/models.md).
4. **Plug-in.** Close GIMP, then from this repository:

   ```powershell
   # Windows
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```
   ```sh
   # Linux / macOS / Flatpak
   sh install.sh
   ```
   Both copy `gimp-stable-boy/` into the GIMP profile
   (`%APPDATA%\GIMP\3.2\plug-ins\gimp-stable-boy\` or `~/.config/GIMP/3.2/plug-ins/...`)
   and write a default `stable-boy/config.json`. Add `-Link` / `--link` to
   symlink the checkout instead of copying.
5. Start GIMP. The entries appear under `Filters > AI`. The first request
   starts ComfyUI (about 30 to 90 s); later requests reuse it.

## Usage

1. Open an image, make any selection (rectangle, lasso, fuzzy select, mask).
2. `Filters > AI > Generative Fill...`, type a prompt, optionally a negative
   prompt, number of variations, strength, seed, and the model tier.
3. OK. The progress bar shows upload, backend start (first time), sampling
   steps and download.
4. A layer named `Generative Fill: <prompt>` with a layer mask appears above
   the active layer. Paint on the mask to refine the blend, or delete the layer
   to discard. With several variations, they sit in a group with only the first
   visible; toggle visibility to compare.

Generative Expand works the same way with margins instead of a selection.
Text to Image needs no selection; with one, the new layer takes its size and
position.

Non-interactive use (scripts, batch mode) is supported through the PDB; see
`tests/gimp_batch_fill.py` for a complete example that opens an image, selects
a region, runs the fill and exports the result.

## Settings

Stored in `<GIMP profile>/stable-boy/config.json` and edited through
`Filters > AI > Generative Fill Settings...`.

| Setting | Default | Notes |
|---|---|---|
| backend | comfyui | or `a1111` (external AUTOMATIC1111 WebUI with `--api`; not auto-started) |
| comfy_dir | `C:\AI\ComfyUI\ComfyUI_windows_portable` | portable root or a ComfyUI checkout with a venv |
| url / a1111_url | `http://127.0.0.1:8188` / `:7860` | host and port the plug-in talks to and starts on |
| autostart | true | start ComfyUI when it is not running |
| idle_timeout_minutes | 20 | 0 keeps the server until GIMP exits |
| quality | fast | default tier; `quality` = SDXL + Fooocus |
| checkpoint / sdxl_checkpoint | `sd-v1-5-inpainting.ckpt` / `sd_xl_base_1.0.safetensors` | pick from the server's list after "check backend" |
| fooocus_head / fooocus_patch | `fooocus_inpaint_head.pth` / `inpaint_v26.fooocus.patch` | SDXL only |
| steps / cfg / sampler / scheduler | 25 / 7.0 / dpmpp_2m / karras | sampling defaults |
| grow / feather | 16 / 24 px | mask dilation sent to the model, soft edge of the layer mask |
| prefill | true | blur/fill old content under the mask before sampling (needs inpaint nodes) |
| max_side_sd15 / max_side_sdxl | 768 / 1024 | longest side the model sees; larger regions are scaled |
| request_timeout / startup_timeout | 0 (auto) / 240 s | |
| extra_server_args | | for example `--lowvram` |

Logs: `<GIMP profile>/stable-boy/stable-boy.log` (plug-in and supervisor) and
`comfyui.log` (server).

## Troubleshooting

| Symptom | What to do |
|---|---|
| "ComfyUI was not found at ..." | Set the ComfyUI folder in the settings dialog; it must contain `ComfyUI\main.py` (portable) or `main.py` (checkout). |
| "ComfyUI did not come up within N s" | Read the last lines shown in the message or `comfyui.log`. Typical causes: an old NVIDIA driver, a missing VC++ redistributable (`c10.dll`), another program on port 8188. Raise `startup_timeout` on slow disks (first start unpacks a lot of files). |
| "A model file is missing on the backend" | The checkpoint named in the settings is not in `models/checkpoints` (or `models/inpaint` for the Fooocus files). Run "Check backend now" to see what the server offers. |
| "The GPU ran out of memory" | Use a smaller selection, 1 variation, the Fast tier, or add `--lowvram` to the extra server arguments. |
| Fill looks washed out or the seam is visible | Increase `feather`, keep `prefill` on, and make sure comfyui-inpaint-nodes is installed (it enables color matching and mask growth). |
| Menu entry missing | Check `%APPDATA%\GIMP\3.2\pluginrc` for `python-fu-stable-boy-generative-fill`; if absent, confirm the folder name matches the file name (`gimp-stable-boy\gimp-stable-boy.py`) and restart GIMP. |
| Backend keeps running after GIMP closed | Should not happen (the supervisor watches the GIMP pid); use `Filters > AI > Stop AI Backend` next time, or end `python.exe` from `python_embeded` in Task Manager and report a bug with `stable-boy.log`. |
| Expand seam looks hard | Install `opencv-python-headless` into ComfyUI's Python so the navier-stokes border fill is available. |

## Development

```sh
python -m unittest discover -t . -s tests -v     # pure-Python tests, no GIMP needed
powershell -File install.ps1 -Link              # junction the checkout into the GIMP profile
```

Layout: `gimp-stable-boy/gimp-stable-boy.py` (GIMP entry point),
`gimp-stable-boy/stable_boy/` (package; only `gimp_io.py` and `app.py` import
GIMP), `tests/`, `docs/design.md` (architecture and what was learned from
related projects), `docs/models.md`, `docs/evidence/` (end-to-end run logs).

## Roadmap

- Multi-line prompt widget and prompt history in the dialog
- Cancel button during generation
- ControlNet / IP-Adapter reference images
- LoRA selection
- Live preview of intermediate steps
- Automatic model download from the settings dialog
- Flatpak/Snap GIMP smoke tests on Linux

## Credits

- **Torben Giesselmann (thndrbrrr)** wrote the original Stable Boy for GIMP
  2.10 and the AUTOMATIC1111 integration this project started from.
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by comfyanonymous and
  Comfy-Org is the backend.
- [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) and
  [krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion) by Acly
  provided the inpaint nodes and the reference for the workflow design and
  server management.
- Fooocus inpaint models by lllyasviel; Stable Diffusion models by
  Runway/CompVis and Stability AI (see `docs/models.md` for licenses).

## License

GPL-3.0-or-later. See [COPYING](COPYING).
Copyright (C) 2022 Torben Giesselmann, (C) 2026 Stable Boy contributors.

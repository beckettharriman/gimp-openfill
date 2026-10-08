# Models and backend setup

Everything below was downloaded from the official project pages only
(GitHub releases of Comfy-Org, GitHub clone of Acly, Hugging Face repos of
the model authors). Checksums were verified with `certutil -hashfile`
against the SHA-256 values published by Hugging Face (LFS metadata).

## ComfyUI (backend)

| Item | Value |
|---|---|
| Version | ComfyUI 0.39.0 (release 2026-10-05) |
| Source | https://github.com/Comfy-Org/ComfyUI/releases/download/v0.39.0/ComfyUI_windows_portable_nvidia.7z (2,003,629,308 bytes) |
| Installed at | `C:\AI\ComfyUI\ComfyUI_windows_portable\` |
| Interpreter | `C:\AI\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe` (Python 3.13.14, torch 2.14.0+cu130) |
| Start command (what the plug-in runs) | `python_embeded\python.exe -s ComfyUI\main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --dont-print-server` |
| Port | 8188 (configurable in the settings dialog) |
| Logs | `%APPDATA%\GIMP\3.2\stable-boy\comfyui.log` (server), `stable-boy.log` (plug-in and supervisor) |

The official `run_nvidia_gpu.bat` passes `--windows-standalone-build`, which
opens a browser tab. The plug-in deliberately omits it and adds
`--disable-auto-launch`, so nothing visible is ever opened.

### Custom nodes

| Node pack | Commit | Purpose |
|---|---|---|
| [Acly/comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) | `5b7681746fe19e563113d27366ba85236bc1ba5b` (v1.4.4, 2026-10-04), GPL-3.0 | `INPAINT_ExpandMask`, `INPAINT_MaskedFill`, `INPAINT_MaskedBlur`, `INPAINT_StabilizeMask`, Fooocus SDXL inpaint patch nodes |

Installed with `git clone` into `ComfyUI\custom_nodes\`. It needs only
`kornia`, which the portable build already ships (0.8.3), so no extra pip
install was required. ComfyUI-Manager was not needed and is not installed.

## Model files

All paths are relative to `C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI\models\`.

| File | Location | Size (bytes) | SHA-256 | License | Source |
|---|---|---|---|---|---|
| `sd-v1-5-inpainting.ckpt` | `checkpoints/` | 4,265,437,280 | `c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19` | CreativeML OpenRAIL-M | https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting |
| `sd_xl_base_1.0.safetensors` | `checkpoints/` | 6,938,078,334 | `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b` | CreativeML OpenRAIL++-M | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 |
| `fooocus_inpaint_head.pth` | `inpaint/` | 52,602 | `32f7f838e0c6d8f13437ba8411e77a4688d77a2e34df8857e4ef4d51f6b97692` | OpenRAIL (repo tag) | https://huggingface.co/lllyasviel/fooocus_inpaint |
| `inpaint_v26.fooocus.patch` | `inpaint/` | 1,323,362,033 | `f8657a025104e22d70f9c060635d8e8c2196f433871a2f68dc40abd2171f0d59` | OpenRAIL (repo tag) | https://huggingface.co/lllyasviel/fooocus_inpaint |

Total on disk: about 12.5 GB.

### Why these

- **SD 1.5 inpainting** (`sd-v1-5-inpainting.ckpt`) is the "Fast" tier and the
  default. It is a real inpainting UNet (9-channel input), loads in seconds,
  samples 768 px regions in a few seconds on the RTX 4070 Laptop and needs
  roughly 2.5 GB of VRAM. The repo publishes only the `.ckpt`; ComfyUI loads
  it with `weights_only` safe unpickling.
- **SDXL base + Fooocus inpaint patch** is the "Quality" tier. The patch
  turns any regular (non-Turbo/Lightning) SDXL checkpoint into an inpainting
  model, as used by Fooocus and Krita AI Diffusion. At 1024 px it uses most
  of the 8 GB; ComfyUI's model management offloads to RAM automatically
  (`NORMAL_VRAM` mode on this GPU, no `--lowvram` flag needed). Expect 30 to
  60 s per fill versus 5 to 10 s for SD 1.5.

### VRAM budget (8 GB RTX 4070 Laptop)

| Scenario | Working size | Peak VRAM (observed/expected) |
|---|---|---|
| SD 1.5 inpaint, 1 variation | up to 768 x 768 | about 2.5 GB |
| SD 1.5 inpaint, 4 variations | up to 768 x 768 | about 3.5 GB |
| SDXL + Fooocus, 1 variation | up to 1024 x 1024 | 6.5 to 7.5 GB, partial offload |
| SDXL + Fooocus, 2+ variations | up to 1024 x 1024 | offload heavy; prefer 1 at a time |

If a request fails with an out-of-memory message, use a smaller selection,
fewer variations, or the Fast tier. `--lowvram` can be added through
"Extra ComfyUI arguments" in the settings dialog.

## Adding other models

Any SD 1.5 or SDXL checkpoint dropped into `models/checkpoints/` appears in
the settings dialog after the next "Check backend now". For SDXL, keep the
Fooocus patch; for SD 1.5, prefer checkpoints trained for inpainting (names
usually contain `inpainting`), although regular checkpoints also work with
`InpaintModelConditioning` at reduced quality.

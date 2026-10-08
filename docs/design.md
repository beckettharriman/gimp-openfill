# Design: Stable Boy 2 for GIMP 3

Status: implemented (2.0.0-alpha.1). This note records what was built, why, and
what was learned from the projects surveyed before the port.

## Goal

A Photoshop "Generative Fill" equivalent inside one GIMP 3 window:

1. Select an area.
2. `Filters > AI > Generative Fill...`, type a prompt, press OK.
3. A new layer with a layer mask appears in the same image.

The plug-in owns the whole backend lifecycle. The user never sees a terminal,
a browser tab or a second application. The backend (ComfyUI) is started
hidden, health-checked, kept warm between calls, shut down when GIMP exits,
and shut down earlier by an idle timeout so the GPU is not held forever.

## Why a redesign, not a port

The original Stable Boy (thndrbrrr, 2022) is a Python 2 `gimpfu` plug-in that
posts base64 PNGs to the AUTOMATIC1111 WebUI JSON API and expects the user to
paint on a layer literally named `Inpainting Mask`. GIMP 3 removed `gimpfu`,
`gimpshelf`, `pdb.*` calls and Python 2; the plug-in API is now libgimp 3 via
GObject Introspection. None of the old code compiles under GIMP 3, and the UX
(mask layer by name, A1111 in a browser) is not what the feature request
[GNOME/gimp#10086](https://gitlab.gnome.org/GNOME/gimp/-/issues/10086) asks
for. The 2.10 tree was removed rather than left as dead code; the command
pattern, the "results as layers" idea and the A1111 request shapes were kept
as the design starting point.

## Architecture

```
gimp-stable-boy/gimp-stable-boy.py      GIMP entry point: Gimp.PlugIn subclass,
                                        five procedures, dialogs, orchestration
gimp-stable-boy/stable_boy/
  __init__.py        version string
  config.py          Settings dataclass, JSON load/save under Gimp.directory()/stable-boy
  log.py             file logger (one log per GIMP profile)
  png.py             pure-Python PNG encoder (RGB/RGBA/Gray 8-bit) and IHDR reader
  geometry.py        pure: Rect, context-region growth, working-size snapping,
                     outpaint canvas math
  workflow.py        pure: ComfyUI API-format graph builders (SD 1.5 inpaint,
                     SDXL + Fooocus inpaint, text-to-image)
  websocket.py       pure: minimal RFC 6455 client (stdlib sockets only)
  comfy_api.py       pure: urllib client for /system_stats, /object_info,
                     /upload/image, /prompt, /ws, /history, /view, /interrupt
  backend.py         abstract Backend + request/result dataclasses + errors
  backends/comfy.py  ComfyBackend (builds graph, uploads, queues, streams progress)
  backends/a1111.py  A1111Backend (sdapi/v1 img2img, txt2img, progress, interrupt)
  server.py          ServerManager: discovers/starts the hidden backend,
                     talks to the supervisor through a state file
  supervisor.py      standalone process: owns the ComfyUI child in a Win32 Job
                     Object, watches the GIMP pid, enforces the idle timeout
  gimp_io.py         everything that touches Gimp/Gegl: export region and mask,
                     insert result layer with mask, canvas resize, new image
tests/               pure-Python unit tests (run with system Python, no GIMP)
install.ps1/.sh      copy the plug-in folder into the GIMP profile, write config
```

Rule: everything under `stable_boy/` except `gimp_io.py` imports neither
`gi` nor GTK, so it is testable under any Python 3.10+ and reusable outside
GIMP. `gimp-stable-boy.py` and `gimp_io.py` are the only GIMP-aware modules.

### Plug-in process model (the part that shapes everything)

A GIMP Python plug-in is a short-lived process: GIMP spawns it for one
procedure call and it exits when the procedure returns. That means a plug-in
process cannot itself "keep the server warm" or "shut it down when GIMP
exits". The design therefore splits responsibilities:

- `supervisor.py` is launched once, detached (`DETACHED_PROCESS |
  CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` on Windows, `start_new_session`
  elsewhere) with GIMP's bundled `pythonw.exe`. It starts ComfyUI as its child
  with `CREATE_NO_WINDOW`, stdout/stderr redirected to `comfyui.log`, and
  assigns it to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, so the
  server can never outlive the supervisor even if the supervisor crashes.
- The supervisor polls: is the GIMP pid still alive (`OpenProcess` +
  `WaitForSingleObject`, or `os.kill(pid, 0)`), has the idle timeout elapsed
  since the last generation (`last_used` in the state file) with an empty
  ComfyUI queue, is the child still running. Any of those ends the server.
- `server-state.json` (pid, port, supervisor pid, started, last_used) in the
  profile folder is the only contract between plug-in runs and the
  supervisor. Every plug-in run reads it, health-checks the URL, and only
  spawns a new supervisor if there is no healthy server.
- The plug-in process reads `os.getppid()` to learn GIMP's pid and passes it
  to the supervisor as `--watch-pid`.

Krita's `ai_diffusion/server.py` does the same thing in-process because the
Krita plug-in is long-lived; the Job Object trick (`win32.py`) is borrowed as
an idea and reimplemented with `ctypes`.

### Backend interface

```python
class Backend(ABC):
    name: str
    def health(self) -> HealthStatus            # ok, detail, models, inpaint_nodes
    def inpaint(self, request, progress) -> GenerationResult
    def outpaint(self, request, progress) -> GenerationResult
    def txt2img(self, request, progress) -> GenerationResult
    def progress(self) -> Progress               # fraction, text
    def cancel(self) -> None
```

`ComfyBackend` is the primary implementation and the only one tested on this
machine. `A1111Backend` keeps the original project's protocol alive behind the
same interface (base64 PNGs to `/sdapi/v1/img2img` and `/txt2img`,
`/sdapi/v1/progress`, `/sdapi/v1/interrupt`). It is documented as
untested-on-this-machine because A1111 is not installed here.

### Data flow for Generative Fill

1. `gimp_io.selection_rect(image)` reads the selection bounds. If the
   selection is empty the whole image is used.
2. `geometry.context_rect()` grows the selection by a padding proportional to
   its size (35 % of the larger side, at least 32 px), enforces a minimum
   context size (512 for SD 1.5, 768 for SDXL) centered on the selection, and
   clamps to the image.
3. `geometry.working_size()` picks the resolution the model will actually see:
   the context region is scaled so that its longer side does not exceed the
   model's maximum (768 / 1024), it is never upscaled more than 2x, and both
   sides are multiples of 8.
4. `gimp_io.export_region()` composites the visible image
   (`Gimp.Layer.new_from_visible`) and reads the context rectangle from its
   `Gegl.Buffer` as `R'G'B'A u8`; `gimp_io.export_mask()` reads the selection
   channel as `Y u8`. Both are encoded with `png.py` and uploaded to ComfyUI.
5. `workflow.build_inpaint()` assembles the graph below and `ComfyBackend`
   queues it, streams `progress` events over the websocket into
   `Gimp.progress_update`, then downloads the output PNGs from `/view`.
6. `gimp_io.insert_result()` loads each PNG with `Gimp.file_load_layer`,
   offsets it to the context origin, adds alpha, and attaches a layer mask
   created from the original selection feathered by the configured radius
   (`Gimp.Selection.feather` on a saved copy, `layer.create_mask(SELECTION)`).
   Variations go into a layer group with only the first one visible. The
   original selection is restored and everything sits in one undo group.

### The ComfyUI graphs

Node ids are stable strings so errors from `/prompt` can be mapped back to a
readable message. Inputs are the API ("prompt") format, not the UI format.

SD 1.5 inpainting checkpoint (default, `sd-v1-5-inpainting.ckpt`):

```
CheckpointLoaderSimple ---- MODEL --> DifferentialDiffusion --> KSampler
          |---- CLIP ---> CLIPTextEncode (+) / CLIPTextEncode (-)
          '---- VAE ----> InpaintModelConditioning <-- pixels, mask
LoadImage(crop) --> [ImageScale] --> [INPAINT_MaskedBlur/MaskedFill] --> pixels
LoadImage(mask) --> ImageToMask(red) --> [ImageScale] --> INPAINT_ExpandMask
                                                           (grow, blur) --> mask
InpaintModelConditioning --> positive, negative, latent --> [RepeatLatentBatch]
KSampler --> VAEDecode --> [ImageScale back to crop size] --> SaveImage
```

SDXL + Fooocus inpaint patch (`sd_xl_base_1.0.safetensors` +
`fooocus_inpaint_head.pth` + `inpaint_v26.fooocus.patch`):

```
... same image/mask preparation ...
INPAINT_VAEEncodeInpaintConditioning --> positive, negative,
                                         latent_inpaint, latent_samples
INPAINT_LoadFooocusInpaint --> INPAINT_ApplyFooocusInpaint(model, patch,
                                                           latent_inpaint)
KSampler(model=patched, latent=latent_samples) --> VAEDecode --> SaveImage
```

Both graphs degrade gracefully: when `/object_info` reports no `INPAINT_*`
nodes, mask growth and feathering fall back to core `GrowMask` +
`MaskToImage` / `ImageBlur` / `ImageToMask`, and pre-fill is skipped. The
Fooocus path is only offered when the nodes and both model files are present.

Outpaint ("Generative Expand") is the same graph with a different mask: the
canvas is resized in GIMP, the new area plus an overlap band becomes the mask,
and pre-fill uses `INPAINT_MaskedFill(navier-stokes)` followed by
`INPAINT_MaskedBlur` (Krita's `FillMode.border`), which removes the hard seam
between old content and the gray/transparent new area before sampling.

Text-to-image is `CheckpointLoaderSimple -> CLIPTextEncode x2 ->
EmptyLatentImage(batch) -> KSampler -> VAEDecode -> SaveImage`, inserted as a
new layer or opened as a new image.

### Models and VRAM budget (RTX 4070 Laptop, 8 GB)

| Model | Role | Disk | Typical VRAM | Notes |
|---|---|---|---|---|
| sd-v1-5-inpainting.ckpt | default fill/expand | 4.27 GB | about 2.5 GB at 768 px | fast, reliable, proper inpaint UNet |
| sd_xl_base_1.0.safetensors + Fooocus head/v26 patch | quality mode | 6.94 GB + 1.32 GB | 6 to 7.5 GB at 1024 px, ComfyUI offloads as needed | slower, much better coherence for large fills |

ComfyUI picks `NORMAL_VRAM` on this GPU and offloads automatically; no
`--lowvram` flag is forced. Details and checksums: `models.md`.

### Progress, cancellation, errors

- Progress: websocket `progress` events (`value/max`) drive
  `Gimp.progress_update`; the `executing` event with `node == null` marks
  completion. If the websocket cannot connect, `/history/<id>` is polled.
- Cancel: the ProcedureDialog has no cancel hook once generation is running,
  so cancellation is time based (`request_timeout`) and `/interrupt` is sent
  when the plug-in gives up or hits an exception.
- Errors are surfaced with `Gimp.message()` in plain words: backend not
  installed (path check), failed to start (last lines of `comfyui.log`),
  missing model (name from `/prompt` node_errors), out of VRAM
  (`OutOfMemoryError` in `execution_error`), timeout.

### Settings

Stored as JSON at `<GIMP profile>/stable-boy/config.json`, edited through
`Filters > AI > Generative Fill Settings...` (a `GimpUi.ProcedureDialog` whose
choice lists are built from the last cached model list). Keys: backend,
comfy_dir, url, port, checkpoint, sdxl_checkpoint, inpaint mode preference,
steps, cfg, sampler, scheduler, denoise, grow, feather, idle_timeout_minutes,
autostart, request_timeout, max working sizes.

## What was learned from each surveyed project

- **gwpelletier/gimp-plugin-ComfyUI** (GPL-3.0, GIMP 3): confirmed the GIMP 3
  entry pattern (`Gimp.ImageProcedure.new`, `add_menu_path`, `set_image_types`),
  `Gimp.file_load_layer` for results, `Gimp.file_save` with
  `RunMode.NONINTERACTIVE`, and that a stdlib-only websocket client is
  practical. Its design is workflow-template substitution (user supplies a
  JSON); this project builds graphs in code so the user never sees ComfyUI.
- **swaynos/gimp-comfyui-sam** (GPL-3.0, GIMP 3.2): showed reading pixels
  directly from `drawable.get_buffer().get(rect, 1.0, "R'G'B' u8", ...)` and
  writing masks back through `Gimp.Channel` buffers, `Gimp.Selection.save`,
  settings under `Gimp.directory()/plug-in-settings`, and careful undo-group
  handling. Adopted the buffer-based export (no temp XCF, no export dialog).
- **Intel openvino-ai-plugins-gimp**: Intel-hardware only (OpenVINO on Intel
  CPU/iGPU/NPU); bundles its own model runtime. Noted, not applicable to an
  NVIDIA laptop, but its "Stable Diffusion inpainting inside GIMP" UI is the
  closest published precedent to this feature.
- **Acly/krita-ai-diffusion** (GPL-3.0): the reference UX. Reused as ideas:
  hidden server launch (`CREATE_NO_WINDOW`) with a Job Object so the server
  dies with the host; "To see the GUI go to" as the readiness signal (here
  `/system_stats` is polled instead); the inpaint graph shape
  (`DifferentialDiffusion`, `INPAINT_ExpandMask` grow/feather,
  `INPAINT_MaskedBlur`/`MaskedFill` pre-fill, Fooocus patch via
  `INPAINT_VAEEncodeInpaintConditioning` + `ApplyFooocusInpaint`); the
  context-crop then scale-to-working-size then scale-back pattern; and the
  fill-mode heuristics (blur for fill, border fill for expand).
- **Acly/comfyui-inpaint-nodes** (GPL-3.0 nodes, run inside ComfyUI): node ids
  and exact inputs (`INPAINT_ExpandMask(mask, grow, blur, blur_type)`,
  `INPAINT_MaskedFill(image, mask, fill, falloff)`,
  `INPAINT_VAEEncodeInpaintConditioning(positive, negative, vae, pixels,
  mask)`), the requirement that Fooocus patches apply to regular SDXL
  checkpoints only (no Turbo/Lightning), and that the nodes need only kornia,
  which the portable already ships.
- **GNOME/gimp#10086**: open since 2023, labelled Feature/Plugins/Dependencies;
  asks for "as easy as Photoshop", explicitly cites gimp-stable-boy, and wants
  the plug-in to handle installing/prompting for the backend. That framed the
  zero-terminal lifecycle requirement.
- **maorcc/gimp-mcp** (GPL-3.0): a persistent GIMP 3.2 plug-in with a TCP
  socket on 9877; useful as a driving harness for tests, and a reminder that
  GIMP 3.2 is the baseline (`Gimp.ProcedureSensitivityMask`, `get_selected_*`).

## Non-goals for 2.0.0-alpha

ControlNet, IP-Adapter, regional prompts, live preview, LoRA management, a
custom GTK canvas. Those belong to Krita-scale projects; this plug-in aims to
be the small, reliable "fill the selection" tool.

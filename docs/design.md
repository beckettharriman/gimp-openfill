# Design: Stable Boy 2 for GIMP 3

Status: implemented, 2.0.0-beta.1 (first public beta). This note records what
was built, why, and what was learned from the projects surveyed before the
port. Tested end to end on Windows 11 with GIMP 3.2.6 and ComfyUI 0.39.0;
see `docs/evidence/` and `CHANGELOG.md`.

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
                                        five procedures, dialog wiring
gimp-stable-boy/stable_boy/
  __init__.py        version string
  app.py             orchestration of fill, expand, text to image and removal
  config.py          Settings dataclass, JSON load/save under Gimp.directory()/stable-boy
  log.py             file logger (one log per GIMP profile), token redaction
  png.py             pure-Python PNG encoder (RGB/RGBA/Gray 8-bit) and IHDR reader
  geometry.py        pure: Rect, context-region growth, working-size snapping,
                     mask grow/feather, colour-match and timeout heuristics,
                     outpaint canvas math
  workflow.py        pure: ComfyUI API-format graph builders (SD 1.5 inpaint,
                     SDXL + Fooocus inpaint, FLUX Fill, Qwen-Image-Edit,
                     LaMa/MAT removal, text-to-image)
  catalog.py         pure: models/catalog.json parsing and validation
  downloads.py       pure: resumable, sha256-verified downloads; pinned
                     custom-node installs
  progress.py        pure: preview frame parsing, ETA, frame throttling
  websocket.py       pure: minimal RFC 6455 client (stdlib sockets only)
  comfy_api.py       pure: urllib client for /system_stats, /object_info,
                     /upload/image, /prompt, /ws, /history, /view, /interrupt
  backend.py         abstract Backend + request/result dataclasses + errors
  backends/comfy.py  ComfyBackend (builds graph, uploads, queues, streams progress)
  backends/a1111.py  A1111Backend (sdapi/v1 img2img, txt2img, progress, interrupt)
  server.py          ServerManager: discovers/starts the hidden backend,
                     talks to the supervisor through a state file
  supervisor.py      standalone process: owns the ComfyUI child in a Win32 Job
                     Object, watches the GIMP pid, enforces the idle timeout,
                     runs download and node-install tasks
  ui_text.py         pure: dialog strings, status lines, error next steps
  dialogs.py         GTK: Fill, Expand, Text to Image and Settings dialogs
  models_ui.py       GTK: the Models tab
  progress_window.py GTK: floating progress window with preview and Cancel
  ui_picker.py       GTK: variations picker
  runner.py          worker thread for a generation, main-loop marshalling
  gimp_io.py         everything that touches Gimp/Gegl: export region and mask,
                     insert result layers with masks, canvas resize, new image
tests/               pure-Python unit tests (run with system Python, no GIMP)
                     and gimp_batch_*.py harnesses that run inside GIMP
install.ps1/.sh      copy the plug-in folder into the GIMP profile, write config
```

Rule: only the entry point, `gimp_io.py` and the GTK modules (`dialogs.py`,
`models_ui.py`, `progress_window.py`, `ui_picker.py`, `runner.py`) import
`gi`; image access goes through `gimp_io` (`dialogs.py` and `runner.py` use
GIMP only for UI initialisation and window placement). Everything else imports
neither GIMP nor GTK, so it is testable under any Python 3.10+ and reusable
outside GIMP; the dialog text and layout logic lives in `ui_text.py` for the
same reason.

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

Two GIMP instances sharing one profile are the awkward case: both plug-ins
can find no state file at the same moment, and the GIMP that started the
backend may exit while the other still generates. Two pieces handle it:

- **Start lock.** The supervisor creates `supervisor.lock` in the profile's
  `stable-boy` folder exclusively, with its pid inside
  (`supervisor.acquire_start_lock`), and holds it for its lifetime; a second
  supervisor that finds the lock held exits at once. A lock whose pid is dead
  or not a Python process is stale and taken over. Without it, two requests
  1 s apart started two supervisors and two ComfyUI servers
  (`rob-two-requests-first-gimp-exits`).
- **Watchers.** Every plug-in run that uses the managed backend touches
  `watchers/<gimp pid>` (`server.ServerManager.register_watcher`, called from
  `touch()`), and the supervisor keeps ComfyUI up while
  `supervisor.live_watchers` finds any of those pids alive and still a GIMP
  process, not only the `--watch-pid` it was started with. Otherwise closing
  the first GIMP killed the second one's generation.

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
   selection is empty the call stops with "Nothing is selected ..." before
   the backend is started (`Select > All` regenerates the whole image).
   Indexed images are refused with a hint to convert them to RGB.
2. `geometry.context_rect()` grows the selection by a margin proportional to
   its larger side (`geometry.fill_padding`: 0.5x for prompted fills, 1x for
   removal with a generation model, 0.5x for the LaMa/MAT removal models, at
   least 32 px), enforces the model's minimum context, centres it
   on the selection and clamps it to the image. The tighter margin for
   prompted fills came from the SD 1.5 prompt-adherence ablation
   (`docs/evidence/overnight-2026-10-09/sd15-prompt-ablation/`).
3. `geometry.working_size()` picks the resolution the model will actually see:
   the context region is downscaled so that its longer side fits the model's
   maximum (768 for SD 1.5, 1024 for SDXL, FLUX and Qwen, 512 for LaMa and
   MAT), upscaled (at most 8x) so that small selections reach the model's
   minimum side, and snapped
   to the latent multiple (8, or 16 for FLUX and Qwen).
4. `gimp_io.export_region_png()` composites the visible image
   (`Gimp.Layer.new_from_visible`, from a throw-away duplicate with channels
   hidden when a channel is visible) and reads the context rectangle from its
   `Gegl.Buffer` as `R'G'B'A u8`, flattened over the mean visible colour where
   it is transparent (`geometry.flatten_over_mean`; ComfyUI's LoadImage drops
   alpha); `gimp_io.export_selection_mask_png()` reads the selection channel
   as `Y u8`. Both are encoded with `png.py` and uploaded to ComfyUI.
5. `workflow.build_inpaint()` assembles the graph below and `ComfyBackend`
   queues it, streams `progress` events over the websocket into
   `Gimp.progress_update`, then downloads the output PNGs from `/view`.
6. `gimp_io.insert_results()` loads each PNG with `Gimp.file_load_layer`,
   offsets it to the context origin, adds alpha, and attaches a layer mask
   built from the selection, grown (`geometry.layer_mask_grow`: by the
   feather radius for prompted fills so the mask is opaque over the selection
   and fades outward, by the full grow for removal) and feathered, both as a
   percentage of the selection size. Variations go into a layer group with
   only the first one visible; interactive runs then open the variations
   picker. The
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

Pre-fill per tier (`geometry.prefill_for`): removal always gets the border
fill (navier-stokes), and a partial Change amount gets a blur so the original
still guides the result. For full-strength prompted fills SD 1.5 gets a
neutral grey hole, because with a border fill it continues the surrounding
sky instead of drawing the prompt; the SDXL tier with the Fooocus patch gets
the border fill, because it reads a flat grey rectangle as a separate picture
and paints a framed photo into it (`photo-ab/README.md`, section 2).

Removal models (LaMa, MAT) have their own profile (`geometry.INPAINT_MODEL`:
working size at most 512 px, a 0.5x margin): the removal node always runs on
a 512 px square, so a larger crop was shrunk with nearest-neighbour sampling
inside the node and came back soft, with ghosts.

Outpaint ("Generative Expand") is the same graph with a different mask: the
canvas is resized in GIMP, the new area plus an overlap band becomes the mask,
and pre-fill uses `INPAINT_MaskedFill(navier-stokes)` followed by
`INPAINT_MaskedBlur` (Krita's `FillMode.border`), which removes the hard seam
between old content and the gray/transparent new area before sampling.

Expand context band (`geometry.plan_expand`, `_strip_context`): a
one-sided expansion sends the new strip plus a band of the old image twice
as deep as the strip (at least the model's minimum context, and at least half
the edge length) instead of the whole canvas. The generic context turned a
256 px strip along a 1440 px edge into the whole canvas at 0.47x, where the
new area was a thin band the model filled with a flat bar. Expansions on two
or more sides still use the whole canvas.

PNG upload padding (`workflow.probe_safe_png`): ComfyUI 0.39's `LoadImage`
decodes uploads with PyAV, which guesses the format from the first 2048
bytes. A mask with identical rows (an expansion strip) deflates into a
periodic byte stream that the MPEG-TS probe scores above PNG, and the load
fails with "End of file". Both uploads therefore get a `tEXt` chunk of 2048
spaces right after `IHDR`; decoders ignore it and the pixels are unchanged.

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
- Progress window: generation runs in a worker thread (`runner.py`) while
  GIMP's main loop drives a small always-on-top window
  (`progress_window.py`) with the step text, percent, elapsed and remaining
  time, and a live TAESD preview (ComfyUI started with
  `--preview-method taesd`, binary websocket frames, at most four per
  second). GTK and GIMP calls from the worker are marshalled to the main
  loop.
- Cancel: the window's Cancel button sets a flag that every phase checks,
  and nothing is inserted, so the image stays unchanged:
  - while the backend starts, `server.ServerManager.ensure_running`, `start`
    and `_wait_ready` take the cancel callback (`App.backend` passes it), so
    Cancel takes effect within a few seconds instead of when sampling begins;
  - while uploading and sampling, `ComfyClient.wait_for` checks it every loop,
    sends `/interrupt`, clears the queue and stops, and `ComfyBackend`
    raises `GenerationCancelled`;
  - after the result has arrived (downloading it), `Runner.run` drops the
    result when Cancel was pressed, because the window has already promised
    an unchanged image;
  - a cancel ends the procedure with the CANCEL status and an info log line,
    not an error dialog; only a job stopped from ComfyUI itself (its own
    Cancel or `/interrupt`) gets a message (`ui_text.INTERRUPTED_OUTSIDE`),
    since the user did not press anything in GIMP.
- A ComfyUI that dies mid-job shows up as a transport error with no HTTP
  status while the server no longer answers; `ComfyBackend` maps that to a
  plain "ComfyUI stopped while it was generating" message instead of the raw
  socket error.
  `request_timeout` (0 = estimated per request) remains as a safety net, and
  `/interrupt` is also sent when the plug-in gives up or hits an exception.
- Errors are plain sentences that end with a next step
  (`backend.describe_error`, `ui_text.with_next_step`): backend not installed
  (path check), port taken by another program (named), failed to start (last
  lines of `comfyui.log`), model not downloaded, out of VRAM
  (`OutOfMemoryError` in `execution_error`), timeout, cancelled. They are
  shown in the progress window and returned as the procedure's error for
  scripts.

### Settings

Stored as JSON at `<GIMP profile>/stable-boy/config.json` (`config.Settings`)
and edited through `Filters > AI > Generative Fill Settings...`. An unreadable
file is moved aside as `config.json.corrupt-<time>` and defaults are used; on
POSIX the file is written owner-only because it can hold the Hugging Face
token. Every key:

| Key | Default | Dialog label (section) | Notes |
|---|---|---|---|
| `comfy_dir` | `C:\AI\ComfyUI\ComfyUI_windows_portable` (Windows) | AI backend folder (General) | portable root or a ComfyUI checkout with a venv |
| `autostart` | true | Start backend automatically (General) | start ComfyUI hidden when needed |
| `idle_timeout_minutes` | 20 | Idle timeout (minutes) (General) | 0 keeps the server until GIMP exits |
| `progress_window` | true | Show the floating progress window (General) | |
| `active_model` | `sd15-inpainting` | Set active (Models) | catalog id used when a dialog says "active" |
| `hf_token` | empty | token field (Models) | only for gated files; never logged |
| `steps` / `cfg` | 25 / 7.0 | Steps, Prompt strictness (CFG) (Advanced generation) | |
| `sampler` / `scheduler` | `dpmpp_2m` / `karras` | Sampler, Scheduler (Advanced generation) | |
| `grow_percent` / `grow` | 15 % / 48 px | Repaint margin, limit (Advanced generation) | mask dilation as a percentage of the selection's larger side, capped |
| `feather_percent` / `feather` | 6 % / 24 px | Edge softness, limit (Advanced generation) | layer mask feather, same scaling |
| `prefill` | true | Hide old content before generating (Advanced generation) | needs the inpaint nodes |
| `max_side_sd15` / `max_side_sdxl` | 768 / 1024 | Working size for SD 1.5 / SDXL (Advanced generation) | longest side the model sees |
| `txt2img_width` / `txt2img_height` | 768 / 512 | Text to Image default width / height (Advanced generation) | used without a selection |
| `backend` | `comfyui` | Backend (Connection and troubleshooting) | or `a1111`: an AUTOMATIC1111 WebUI started by the user with `--api`, untested |
| `url` / `a1111_url` | `http://127.0.0.1:8188` / `:7860` | ComfyUI address, AUTOMATIC1111 address (Connection) | host and port used to talk to and start the server |
| `startup_timeout` | 240 s | Startup time limit (Connection) | |
| `request_timeout` | 0 | Generation time limit (Connection) | 0 estimates a limit per request |
| `extra_server_args` | empty | Extra ComfyUI options (Connection) | for example `--lowvram` |
| `quality` | `fast` | Model for scripts asking 'fast' or 'quality' (Connection) | legacy tiers for older scripts |
| `checkpoint` / `sdxl_checkpoint` | `sd-v1-5-inpainting.ckpt` / `sd_xl_base_1.0.safetensors` | SD 1.5 / SDXL model file (Connection) | used by the legacy tiers |
| `fooocus_head` / `fooocus_patch` | `fooocus_inpaint_head.pth` / `inpaint_v26.fooocus.patch` | Fooocus patch file (Connection) | SDXL only |
| `debug` | false | Verbose log (Connection) | also `SB_DEBUG_DUMP=1` keeps the exact crop, mask and raw result |
| `denoise` | 1.0 | - | default Change amount for scripts |
| `progress_window_x` / `_y` | -1 | - | remembered window position; -1 = top right of the image window |
| `prompt_history` | empty | Recent prompts (Fill dialog) | JSON list, last 20, newest first |

## UX design

The dialogs follow the Photoshop flow and put the prompt first; everything a
first-time user does not need is collapsed. The screens are in
`docs/screenshots/` (captured by `tests/gimp_batch_ui_screenshots.py`).

1. **Generative Fill** opens centred on the image window. Two toggle buttons
   pick the mode: **Fill with a prompt** (a large multi-line prompt box; the
   last prompt is pre-filled and selected so typing replaces it; **Recent
   prompts** lists the last 20) or **Remove object** (no prompt; an installed
   LaMa or MAT model is used automatically). **Advanced** holds Model, Avoid,
   Variations, Change amount and Seed. A status line shows the selection
   size, warns when nothing is selected, and notes when the active model can
   only remove objects. Enter generates, Shift+Enter starts a new line,
   Escape cancels; Generate is the only blue button. Generate with an empty
   prompt in Fill mode asks for a prompt instead of generating.
2. **Generative Expand** has an optional prompt, four margin boxes around a
   "your image" placeholder, the quick buttons Wider, Taller and All sides,
   and a status line with the canvas size before and after.
3. **Text to Image** has a prompt, Size (automatic or width x height),
   Result as (New layer in this image or New image) and Advanced.
4. While generating, the **progress window** sits at the top right of the
   image window, never takes the keyboard focus, and shows plain steps
   ("Starting the AI backend (first time takes about a minute)", "Generating,
   step 12 of 25", "Placing the result"), the preview and a red Cancel. On
   failure it says "Something went wrong" with the message and a next step.
5. With several variations the **variations picker** shows thumbnails;
   clicking one (or 1 to 9) shows it in the image. Keep selected (also Enter,
   Escape or closing) hides the others but keeps them in the layer group, Keep
   all leaves the group, Discard removes all variations in one undo step.
6. **Settings** keeps four controls and Check backend on the General tab and
   moves everything else into Advanced generation and Connection and
   troubleshooting, each field with a one-line explanation. The **Models**
   tab has one row per model with one state-driven primary button, and shows
   the token field only when a gated model needs it.

The generic GIMP procedure dialog remains as a fallback if the custom dialog
cannot be built, and non-interactive PDB calls use the same arguments, so
scripts are unaffected by the redesign. GIMP does not let a plug-in claim a
keyboard shortcut; the Fill dialog's last line tells the user how to assign
one in `Edit > Keyboard Shortcuts`.

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

## Non-goals for 2.0

ControlNet, IP-Adapter, regional prompts, LoRA management, a custom GTK
canvas (live preview, cancel and model download, once listed here, are now
implemented). Those belong to Krita-scale projects; this plug-in aims to
be the small, reliable "fill the selection" tool.

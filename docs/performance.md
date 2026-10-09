# Performance

This page records how fast Stable Boy is on real hardware and what the
plug-in does to keep it fast. Cells that read "measured later tonight" have
not been measured yet; nothing on this page is an estimate.

## Method

| Item | Value |
|---|---|
| Machine | measured later tonight (CPU, RAM, GPU and VRAM, driver version) |
| Operating system | Windows 11 |
| GIMP | 3.2.6, started with `--new-instance` and an isolated profile (`GIMP3_DIRECTORY`) |
| ComfyUI | 0.39.0, Windows portable NVIDIA build, comfyui-inpaint-nodes v1.4.4 |
| Models | as in [models.md](models.md) |
| Driver | `tests/gimp_batch_*.py` through GIMP's `python-fu-eval` batch interpreter, procedures called with `RunMode.NONINTERACTIVE` |

How timings are taken:

- **Wall time per call** is measured by the batch driver around the PDB call
  (`time.perf_counter()` before and after `procedure.run(config)`), so it
  includes export, upload, queueing, sampling, download and layer insertion.
- **Cold start** is a call with no ComfyUI running: it includes the
  supervisor launch, ComfyUI start-up until `/system_stats` answers, and the
  first model load.
- **Warm** calls run with the server already up and the same model loaded.
  The first warm call after a model switch is reported separately.
- **Memory** is sampled from the processes (GIMP, the plug-in, the
  supervisor, ComfyUI's Python) and from `nvidia-smi` before and after each
  call.
- Each figure is the median of several runs unless a row says otherwise; the
  raw numbers go into `report.json` next to the evidence in
  `docs/evidence/<run>/<case-id>/`.

## Cold start

| Step | Time |
|---|---|
| Supervisor launch to ComfyUI process started | measured later tonight |
| ComfyUI process started to `/system_stats` answering | measured later tonight |
| First fill including model load (SD 1.5, 512 px selection) | measured later tonight |
| First fill including model load (SDXL + Fooocus, 512 px selection) | measured later tonight |

## Warm fill per tier

Square selections in a 3000 x 2000 px photo, 1 variation, default steps (25),
Fill with a prompt unless noted.

| Model (tier) | 512 px selection | 1024 px selection | 2048 px selection |
|---|---|---|---|
| SD 1.5 Inpainting (fast) | measured later tonight | measured later tonight | measured later tonight |
| SDXL 1.0 Base + Fooocus (quality) | measured later tonight | measured later tonight | measured later tonight |
| Juggernaut XL v9 + Fooocus (quality) | measured later tonight | measured later tonight | measured later tonight |
| MAT Places512 (removal) | measured later tonight | measured later tonight | measured later tonight |

## Memory and VRAM over 20 fills

Twenty consecutive warm fills with SD 1.5 on the same image, 512 px
selection.

| Fill | GIMP RAM | ComfyUI RAM | VRAM used | Wall time |
|---|---|---|---|---|
| 1 | measured later tonight | measured later tonight | measured later tonight | measured later tonight |
| 5 | measured later tonight | measured later tonight | measured later tonight | measured later tonight |
| 10 | measured later tonight | measured later tonight | measured later tonight | measured later tonight |
| 15 | measured later tonight | measured later tonight | measured later tonight | measured later tonight |
| 20 | measured later tonight | measured later tonight | measured later tonight | measured later tonight |

After the idle timeout: VRAM used measured later tonight.

## UI responsiveness

| Check | Result |
|---|---|
| GIMP canvas responds (pan, zoom) while a fill runs | measured later tonight |
| Progress window updates per sampling step | measured later tonight |
| Preview frame rate in the progress window | measured later tonight |
| Time from Cancel to "Cancelled - the image was left unchanged." | measured later tonight |
| Settings dialog stays usable during Check backend | measured later tonight |

## Plug-in side optimizations

What the code already does to keep calls short and memory bounded:

- **Context crop and working size.** Only a region around the selection is
  sent, never the whole image: `geometry.context_rect` grows the selection by
  a margin proportional to its size (`geometry.fill_padding`: 0.5x for
  prompted fills, 1x for removal) and clamps it to the image;
  `geometry.working_size` scales that region so its longer side fits the
  model's maximum (768 px for SD 1.5, 1024 px for SDXL, FLUX and Qwen; the
  `max_side_*` settings) and snaps it to the latent multiple. A 6000 x 4000
  image therefore costs about the same as a 1024 px one for the same
  selection, and generation time depends on the working size, not on the
  image size. Small selections are upscaled (at most 8x) so the model works
  at its native resolution. The result is scaled back in GIMP.
  (`gimp-stable-boy/stable_boy/geometry.py`, `app.py`)
- **PNG transfer through the API.** The crop and mask are read straight from
  GEGL buffers (`gimp_io.export_region_png`,
  `gimp_io.export_selection_mask_png`), encoded by a small stdlib PNG encoder
  (`stable_boy/png.py`) and uploaded with `/upload/image`; results come back
  from `/view`. No temporary XCF, no GIMP export dialog, no base64 JSON.
  (`stable_boy/comfy_api.py`)
- **Websocket progress.** Step progress and preview frames arrive over
  ComfyUI's websocket (`stable_boy/websocket.py`, a stdlib RFC 6455 client
  with a frame size limit); `/history` is polled once a second as a safety
  net, and is the only signal when the websocket cannot connect. (`stable_boy/backends/comfy.py`,
  `comfy_api.ComfyClient.wait_for`)
- **Preview throttling.** ComfyUI is started with `--preview-method taesd`
  (`supervisor.py`); the progress window admits at most one preview frame
  every 0.25 s (`progress.FrameThrottle`, used in `progress_window.py`) and
  scales it to 320 px on the long side, so previews never flood GTK's main loop.
- **Worker thread.** Generation runs in a worker thread and GTK and GIMP calls
  are marshalled to the main loop (`stable_boy/runner.py`), so the progress
  window and Cancel stay responsive.
- **Keep-warm with an idle timeout.** The supervisor keeps ComfyUI and the
  loaded model alive between plug-in calls, so only the first call pays the
  start-up and model load. It stops the server after `idle_timeout_minutes`
  (default 20) without a request and with an empty queue, and when GIMP
  exits, to give the VRAM back. (`stable_boy/supervisor.py`,
  `stable_boy/server.py`, `last_used` in `server-state.json`)
- **Request time limit.** With `request_timeout` at 0 the limit is estimated
  per request from the steps, batch size and working size
  (`geometry.estimate_timeout`), so a large request is not cut off and a stuck one does
  not wait forever.

# Performance

This page records how fast OpenFill is on real hardware and what the
plug-in does to keep it fast. Every number below was measured on the machine
in the Method table on 2026-10-09; nothing on this page is an estimate. Cells
that say "not measured" were not measured. The raw data (per-call JSON, CSV,
memory samples, the scripts that produced them) is in
[evidence/overnight-2026-10-09/perf/](evidence/overnight-2026-10-09/perf/README.md).

## Method

| Item | Value |
|---|---|
| Machine | Laptop, AMD Ryzen 9 8945HS, 32 GB RAM, NVIDIA GeForce RTX 4070 Laptop GPU 8 GB (8188 MiB), driver 610.88 |
| Operating system | Windows 11 Home (10.0.26200), display 2560 x 1600 at 150 % |
| GIMP | 3.2.6, started with `--new-instance` and an isolated profile (`GIMP3_DIRECTORY`) |
| ComfyUI | 0.39.0, Windows portable NVIDIA build, comfyui-inpaint-nodes v1.4.4, started by the plug-in's supervisor with `--preview-method taesd` |
| Models | as in [models.md](models.md): `sd15-inpainting`, `quality` (SDXL 1.0 Base + Fooocus inpaint), `juggernaut-xl-v9` (+ Fooocus), `mat-places512` |
| Driver | `tests/gimp_batch_perf.py` inside `gimp-console-3.2.exe` through the `python-fu-eval` batch interpreter, Generative Fill called with `RunMode.NONINTERACTIVE`; a launcher outside GIMP samples memory and VRAM every 0.5 s. The GUI measurements use `gimp-3.2.exe` and the real dialog. |
| Settings | 20 steps (`steps` in the test profile), 1 variation, seed 1234, the profile's defaults otherwise (dpmpp_2m / karras, CFG 7, `max_side_sd15` 768, `max_side_sdxl` 1024) |
| Test image | the centre square of `landscape.jpg` (a 1920 x 1440 photo of a field, trees and sky) scaled to 2048 x 2048; centred square selections of 512, 1024 and 2048 px |

How timings are taken:

- **Wall time per call** is measured by the batch driver around the PDB call
  (`time.perf_counter()` before and after `procedure.run(config)`), so it
  includes the plug-in process start, export, upload, queueing, sampling,
  download and layer insertion.
- **Phase split.** The ComfyUI backend writes `timing:` lines to
  `openfill.log` (`backends/comfy.py`): upload bytes and seconds, then
  queue to first sampling step, first step to finished (called "sampling"
  below; it also contains the VAE decode, colour match and ComfyUI saving
  the result), and download. Export is the time from the plug-in's `fill:`
  log line to the start of the upload (it also contains the backend health
  check and one `/object_info` request); insert is the time from the
  download to `fill: done`; plug-in start is from the PDB call to the
  `fill:` line (new Python process, imports, settings).
- **Cold start** is a fresh `gimp-console` with nothing listening on port
  8188 (checked before each launch) and VRAM idle (11 MiB used): the first
  fill pays for GIMP start, the supervisor launch, ComfyUI start-up until
  `/system_stats` answers, and the first model load.
- **Warm** calls run with the server already up and the model loaded. The
  first call after switching to another model is reported separately.
- **Memory** is the working set of `gimp-console-3.2.exe`, of its plug-in
  processes and of ComfyUI's `python.exe`, and `memory.used` from
  `nvidia-smi`, taken from the first 0.5 s sample after each call returned.
- Each warm case ran twice in the same session; both values are given.
  The layers a fill adds are deleted after each call so every call starts
  from the same image.

## Cold start

From launching `gimp-console` with no ComfyUI running to the first result.
Runs 1 and 2 were measured before, run 3 after the health-check change
described under [Changes made after measuring](#changes-made-after-measuring).

| Step | Run 1 (SD 1.5, 512 px) | Run 2 (SD 1.5, 1024 px) | Run 3 (SD 1.5, 1024 px, after the change) |
|---|---|---|---|
| GIMP launch to test image ready (GIMP start-up, not the plug-in) | 6.2 s | 7.0 s | 6.1 s |
| Fill call to supervisor launch (plug-in start, export, health check of the stopped server) | 4.3 s | 5.0 s | 2.9 s |
| Supervisor launch to ComfyUI answering `/system_stats` | 22.1 s | 26.1 s | 22.2 s |
| GIMP launch to "backend ready" | 32.6 s | 38.1 s | 31.2 s |
| Queue to first sampling step (includes loading the checkpoint) | 6.5 s | 10.0 s | 6.6 s |
| GIMP launch to the first fill's layer in the image | 45.3 s | 55.4 s | 45.0 s |
| First fill, wall time of the call | 39.0 s | 48.3 s | 38.8 s |

In the GUI (`gimp-3.2.exe`), a cold first fill with Juggernaut XL v9 on a
256 px selection took 42.9 to 45.3 s (six sessions); the plug-in logged
"backend ready after 22 s" to "after 24 s" in each of them, and the
checkpoint load showed as 9.5 to 10.2 s from queueing to the first step.

## Warm fill per tier

Wall time of the PDB call, two runs each, model already loaded. Selections
are centred squares in the 2048 x 2048 image; a 1024 px selection already
has a 2048 x 2048 context crop (the margin is half the selection on each
side for prompted fills, a full selection for removal), so 1024 and 2048 px
cost the same.

| Model (tier) | 512 px selection | 1024 px selection | 2048 px selection | First call after switching to it (512 px) |
|---|---|---|---|---|
| SD 1.5 Inpainting (fast) | 8.4 / 8.7 s | 10.8 / 10.9 s | 10.8 / 10.9 s | first model of the session (cold start above) |
| SDXL 1.0 Base + Fooocus (quality) | 20.6 / 22.1 s | 28.1 / 24.4 s | 22.3 / 23.9 s | 26.8 s |
| Juggernaut XL v9 + Fooocus (quality) | 22.8 / 23.2 s | 25.1 / 25.3 s | 24.7 / 24.6 s | 28.0 s |
| MAT Places512 (removal) | 3.3 / 2.9 s | 5.1 / 5.7 s | 5.5 / 5.0 s | 5.1 s |

Where the time goes (mean of the two runs, seconds; measured before the
changes below):

| Model | Selection | Context crop | Working size | Crop PNG uploaded | Plug-in start | Export + checks | Upload | Queue to first step | Sampling | Download | Insert | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SD 1.5 Inpainting | 512 | 1024 x 1024 | 768 x 768 | 2.5 MB | 0.67 | 0.40 | 0.03 | 1.59 | 5.35 | 0.02 | 0.49 | 8.57 |
| SD 1.5 Inpainting | 1024 | 2048 x 2048 | 768 x 768 | 8.5 MB | 0.68 | 1.17 | 0.10 | 2.09 | 6.10 | 0.03 | 0.67 | 10.84 |
| SD 1.5 Inpainting | 2048 | 2048 x 2048 | 768 x 768 | 8.5 MB | 0.65 | 1.16 | 0.07 | 2.03 | 6.18 | 0.04 | 0.73 | 10.87 |
| SDXL 1.0 Base + Fooocus | 512 | 1024 x 1024 | 1024 x 1024 | 2.5 MB | 0.68 | 0.41 | 0.05 | 5.85 | 13.81 | 0.03 | 0.50 | 21.36 |
| SDXL 1.0 Base + Fooocus | 1024 | 2048 x 2048 | 1024 x 1024 | 8.5 MB | 0.66 | 1.26 | 2.65 * | 6.28 | 14.69 | 0.02 | 0.71 | 26.29 |
| SDXL 1.0 Base + Fooocus | 2048 | 2048 x 2048 | 1024 x 1024 | 8.5 MB | 0.67 | 1.15 | 0.07 | 5.87 | 14.55 | 0.02 | 0.73 | 23.08 |
| Juggernaut XL v9 + Fooocus | 512 | 1024 x 1024 | 1024 x 1024 | 2.5 MB | 0.66 | 0.40 | 0.04 | 5.61 | 15.71 | 0.02 | 0.54 | 23.00 |
| Juggernaut XL v9 + Fooocus | 1024 | 2048 x 2048 | 1024 x 1024 | 8.5 MB | 0.67 | 1.15 | 0.06 | 6.22 | 16.34 | 0.05 | 0.71 | 25.20 |
| Juggernaut XL v9 + Fooocus | 2048 | 2048 x 2048 | 1024 x 1024 | 8.5 MB | 0.67 | 1.15 | 0.06 | 5.87 | 16.19 | 0.02 | 0.68 | 24.65 |
| MAT Places512 | 512 | 1024 x 1024 | 512 x 512 | 2.5 MB | 0.67 | 0.40 | 0.04 | 0.97 | 0.54 | 0.03 | 0.45 | 3.10 |
| MAT Places512 | 1024 | 2048 x 2048 | 512 x 512 | 8.5 MB | 0.67 | 1.14 | 0.07 | 1.75 | 1.00 | 0.05 | 0.69 | 5.37 |
| MAT Places512 | 2048 | 2048 x 2048 | 512 x 512 | 8.5 MB | 0.67 | 1.15 | 0.06 | 1.78 | 0.89 | 0.02 | 0.67 | 5.25 |

\* One upload of 8.5 MB took 5.25 s (SDXL, 1024 px, run 1); every other
upload of that size took 0.05 to 0.10 s. ComfyUI was answering slowly at
that moment; the cause was not found.

The request time limit estimated per request (`geometry.estimate_timeout`,
`request_timeout` 0) was 125 s for SD 1.5 at 768 x 768, 153 s for SDXL at
1024 x 1024 and 120 s (the minimum) for MAT: five to eight times the warm
generation times above, and about three times the cold first fill.

## Memory and VRAM over 20 fills

Twenty consecutive warm fills with SD 1.5 in one `gimp-console` session,
1024 px selection (2048 x 2048 context, 768 x 768 working size), same seed,
after one cold fill. Values are working sets in MB and VRAM used in MiB.

| Fill | GIMP RAM (`gimp-console`) | Plug-in processes | ComfyUI RAM | VRAM used | Wall time |
|---|---|---|---|---|---|
| cold fill | 327 MB | 126 MB | 6647 MB | 2292 MiB | 48.3 s |
| 1 | 355 MB | 126 MB | 6656 MB | 2292 MiB | 11.1 s |
| 5 | 355 MB | 126 MB | 6660 MB | 2292 MiB | 11.4 s |
| 10 | 355 MB | 126 MB | 6661 MB | 2292 MiB | 11.6 s |
| 15 | 355 MB | 126 MB | 6662 MB | 2292 MiB | 11.6 s |
| 20 | 356 MB | 126 MB | 6663 MB | 2292 MiB | 11.9 s |

Least-squares slope over fills 1 to 20: GIMP +0.22 MB per fill (the values
move between 342 and 356 MB and end where fill 1 was), ComfyUI +0.37 MB per
fill (7.5 MB over 20 fills), VRAM 0, wall time +0.038 s per fill.

**There is no memory growth** in GIMP, in the plug-in processes or in VRAM;
ComfyUI grew by 7.5 MB (0.1 %) over the 20 fills. **Wall time grew by 7 %**
(11.1 s to 11.9 s), and all of that growth is in the server-side sampling
phase (5.8 s to 7.1 s); export (1.13 to 1.19 s), queue to first step (2.0
to 2.2 s) and insert (0.61 to 0.70 s) stayed flat. The GPU read 77 °C right
after the tier series; thermal or power throttling of the laptop GPU fits
this pattern but was not verified.

When `gimp-console` quit, the supervisor stopped ComfyUI: port 8188 was
closed 0.5 to 1.5 s after GIMP exited in all three sessions and VRAM went
back to 11 MiB. The idle timeout (20 minutes) was not waited out.

## UI responsiveness

One fill driven through the real dialog in `gimp-3.2.exe` (Juggernaut XL v9,
520 x 330 px selection, working size 1024 x 840, the progress window on),
model already loaded. Two probes ran during the fill:

- inside the plug-in, a 20 ms GLib timer on the plug-in's main loop
  (`OPENFILL_PERF_STALL=1`, `runner._StallProbe`) records the longest gap between
  two ticks while the job runs;
- outside, `SendMessageTimeout(WM_NULL, 100 ms)` is sent to GIMP's image
  window every 50 ms.

| Check | Result |
|---|---|
| Plug-in main loop, longest gap between 20 ms ticks during the generation | 43.8 to 60.2 ms in eight GUI fills (51.7 ms in the recorded one); Windows fires a 20 ms timer about every 31 ms, so this is one to two missed ticks, never a stall over 100 ms |
| GIMP's window answers `WM_NULL` while a fill runs | 0 of 499 polls timed out at 100 ms, slowest answer 31 ms (dialog opened to layer inserted, 25.3 s); in an earlier session 0 of 511, slowest 50 ms |
| GIMP's window while a non-interactive fill inserts its layer | slowest answer 72 ms; the only 100 ms timeouts (three in one session, five in the other) came in the first 2.5 s after GIMP's window appeared, before any fill |
| GIMP canvas pan and zoom while a fill runs | not measured (no pointer input was sent) |
| Progress window updates per sampling step | yes: "Generating, step N of 20" for every step, the bar and the elapsed / remaining time move once per step |
| Preview frame rate in the progress window | 20 preview frames for 20 steps in 9.9 to 10.8 s of sampling, about 1.9 frames per second; the 0.25 s throttle (4 per second) never had to drop a frame at this step rate |
| Time from Cancel to "Cancelled - the image was left unchanged." | not measured |
| Settings dialog stays usable during Check backend | not measured |

No main-loop stall over 100 ms was found, so nothing on the UI path needed a
change. The export (up to 1.2 s for a 2048 x 2048 crop) runs on the plug-in's
main thread before the progress window opens and before the worker thread
starts; GIMP's own window kept answering during it.

**Progress window found invisible.** While measuring, the floating progress
window turned out never to appear on screen in GUI runs: its native window
existed at the right place with the right size, GTK counted it as shown and
painted 20 previews into it, but the Win32 `WS_VISIBLE` style was never set
(style `06c80000` throughout the fill; a standalone GTK test of the same
window, outside GIMP, gets `16c80000`). The progress window now checks the
native window after `show()` and, if it is not visible, shows it with
`SW_SHOWNOACTIVATE` (`progress_window._NoActivate.ensure_visible`); after
that it is visible (`16c80000`) and appears in the recording. The root
cause inside GIMP's plug-in process was not found. Logs of both states:
`evidence/overnight-2026-10-09/perf/progress-window-visibility/`.

## Changes made after measuring

Each change keeps the result identical (same graph, same model parameters,
same pixels); only time changes. Unit tests stay green.

| Change | Before | After |
|---|---|---|
| **Faster crop encode.** `png.encode` now defaults to zlib level 1 instead of 6 (`openfill/png.py`). A 2048 x 2048 RGBA photo crop: | 1.14 s, 9.13 MB | 0.64 s, 9.38 MB (+3 %) |
| Same, measured inside the plug-in: export + checks for a 2048 x 2048 context | 1.16 to 1.17 s | 0.63 to 0.68 s |
| **Uploads named after their content.** The crop and mask are uploaded as `sb-<12 hex digits of SHA-256 of both>-image.png` / `-mask.png` instead of a random id (`backends/comfy.py`), so a second fill of the same region (another seed or prompt, which is how people re-roll) lets ComfyUI reuse the nodes that only depend on the image and mask. Queue to first step, SD 1.5, 1024 px: | 2.03 to 2.24 s (22 fills) | 0.75 to 0.87 s (re-runs with seeds 1235, 1236, 1237 and 1235 again) |
| Same, Juggernaut XL v9, 1024 px | 6.18 to 6.27 s | 2.17 to 2.20 s |
| Both changes together, whole call, SD 1.5, 1024 px | 10.8 to 10.9 s | 9.1 to 9.4 s |
| Both changes together, whole call, Juggernaut XL v9, 1024 px | 25.1 to 25.3 s | 19.5 to 20.0 s |
| **Fast "is ComfyUI running" check.** On Windows a refused connection to 127.0.0.1 is only reported after about 2 s of retries (2.04 s measured). `ComfyClient.is_alive` now first opens a TCP connection with a 0.5 s timeout when the server is on this machine and returns False at once when nothing listens (`openfill/comfy_api.py`); a running ComfyUI accepts within milliseconds even while busy. Cold start, fill call to supervisor launch: | 4.3 s, 5.0 s | 2.9 s |

The first fill of a region still pays the full queue time (it has new
content); an identical repeat (same region, same seed, same prompt) is not
returned from ComfyUI's cache: it sampled again in the test (6.6 s), so the
content naming never hands back a stale result.

What was measured and left alone:

- **Websocket and history polling.** The plug-in receives each step over the
  websocket; the end of the job arrives as an event, and the `/history`
  poll (once a second) only runs as a safety net. Download of the 0.5 to
  4.9 MB result PNG took 0.01 to 0.05 s. Nothing to gain here.
- **Preview throttle.** At about 2 steps per second the 0.25 s throttle
  admits every preview; decoding and scaling them kept the main loop's
  longest gap at about 50 ms.
- **Request time limit.** The estimate (120 to 153 s) is several times the
  measured generation times and three times the cold first fill; it was not
  changed.
- **Still on the table** (outside the files changed tonight): the cold path
  also spends 1.0 s in `server.port_answers(timeout=1.0)` before launching
  the supervisor (the same Windows refused-connection delay; `server.py`,
  `ServerManager.start`), and `_wait_ready` sleeps 1.5 s between checks.
  Layer insertion takes 0.45 to 0.75 s (`gimp_io.insert_results`) and the
  plug-in process start about 0.67 s per call. Sampling itself is 55 to
  70 % of every warm SD and SDXL call.

## Plug-in side optimizations

What the code does to keep calls short and memory bounded:

- **Context crop and working size.** Only a region around the selection is
  sent, never the whole image: `geometry.context_rect` grows the selection by
  a margin proportional to its size (`geometry.fill_padding`: 0.5x for
  prompted fills, 1x for removal) and clamps it to the image;
  `geometry.working_size` scales that region so its longer side fits the
  model's maximum (768 px for SD 1.5, 1024 px for SDXL, FLUX and Qwen; the
  `max_side_*` settings) and snaps it to the latent multiple. A 6000 x 4000
  image therefore costs about the same as a 1024 px one for the same
  selection, and generation time depends on the working size, not on the
  image size (the 1024 and 2048 px columns above are equal for that
  reason). Small selections are upscaled (at most 8x) so the model works
  at its native resolution. The result is scaled back in GIMP.
  (`gimp-openfill/openfill/geometry.py`, `app.py`)
- **PNG transfer through the API.** The crop and mask are read straight from
  GEGL buffers (`gimp_io.export_region_png`,
  `gimp_io.export_selection_mask_png`), encoded by a small stdlib PNG encoder
  at zlib level 1 (`openfill/png.py`) and uploaded with `/upload/image`
  under content-derived names; results come back from `/view`. No temporary
  XCF, no GIMP export dialog, no base64 JSON. (`openfill/comfy_api.py`,
  `openfill/backends/comfy.py`)
- **Websocket progress.** Step progress and preview frames arrive over
  ComfyUI's websocket (`openfill/websocket.py`, a stdlib RFC 6455 client
  with a frame size limit); `/history` is polled once a second as a safety
  net, and is the only signal when the websocket cannot connect. (`openfill/backends/comfy.py`,
  `comfy_api.ComfyClient.wait_for`)
- **Preview throttling.** ComfyUI is started with `--preview-method taesd`
  (`supervisor.py`); the progress window admits at most one preview frame
  every 0.25 s (`progress.FrameThrottle`, used in `progress_window.py`) and
  scales it to 320 px on the long side, so previews never flood GTK's main loop.
- **Worker thread.** Generation runs in a worker thread and GTK and GIMP calls
  are marshalled to the main loop (`openfill/runner.py`), so the progress
  window and Cancel stay responsive.
- **Keep-warm with an idle timeout.** The supervisor keeps ComfyUI and the
  loaded model alive between plug-in calls, so only the first call pays the
  start-up and model load. It stops the server after `idle_timeout_minutes`
  (default 20) without a request and with an empty queue, and when GIMP
  exits, to give the VRAM back. (`openfill/supervisor.py`,
  `openfill/server.py`, `last_used` in `server-state.json`)
- **Fast local health check.** `ComfyClient.is_alive` probes a local port
  with a 0.5 s TCP connect before the HTTP request, so a stopped local
  server is detected without Windows' 2 s refused-connection delay.
  (`openfill/comfy_api.py`)
- **Request time limit.** With `request_timeout` at 0 the limit is estimated
  per request from the steps, batch size and working size
  (`geometry.estimate_timeout`), so a large request is not cut off and a stuck one does
  not wait forever.
- **Timing in the log.** Every ComfyUI fill writes its upload size and time,
  queue to first step, sampling and download time to `openfill.log`
  (`timing:` lines), so a slow call can be diagnosed from a user's log.

## Reading the numbers

- On this laptop a warm SD 1.5 fill takes 8 to 11 s and a warm SDXL or
  Juggernaut fill 20 to 25 s at 20 steps; removal with MAT takes 3 to 6 s.
  Sampling is the largest part of every generative call; the plug-in's own
  share (process start, export, upload, download, insert) is about 1.6 s at
  1024 x 1024 context and 2.6 s at 2048 x 2048 before the changes, about
  2.1 s at 2048 x 2048 after them.
- The selection size only matters through the context crop: past a 1024 px
  selection in this image the crop is the whole 2048 x 2048 image and the
  time stops growing. The working size, not the image size, sets the GPU
  cost.
- The SDXL tiers spend about 6 s between queueing and the first step on
  every new region (image preparation, VAE encode, the Fooocus patch); with
  content-named uploads a re-roll of the same region skips most of it.
- A cold start costs about 45 s to the first result, of which about 22 s is
  ComfyUI starting and 6 to 10 s loading the first checkpoint; the
  keep-warm supervisor means it is paid once per GIMP session, not per
  fill.
- 20 fills in a row show no memory growth anywhere and a 7 % slow-down
  that sits entirely in GPU sampling.
- These are numbers from one laptop GPU on one night, two runs per case;
  a desktop GPU will sample faster. The two runs of an SD or SDXL case
  were at most 7 % apart (except for the one slow upload marked above); the
  short MAT calls varied by up to 14 %.

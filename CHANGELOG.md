# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0-beta.1] - 2026-10-09

First public beta: model management from inside GIMP, a redesigned
prompt-first UX with progress, preview and cancel, a hardened backend and
downloader, and fixes from an end-to-end test matrix run in a real GIMP 3.2.6
(`docs/evidence/overnight-2026-10-09/`).

### Added

- Model catalog (`models/catalog.json`): SD 1.5 inpainting, SDXL base,
  Fooocus inpaint patch, Juggernaut XL v9, FLUX.1 Fill [dev] (GGUF Q4_0
  community quantization and gated first-party safetensors), Qwen-Image-Edit-2511
  GGUF Q4_K_M, LaMa and MAT for prompt-free removal, each with license,
  source type, gating flag, sizes, sha256 and pinned custom nodes.
- Models tab in the Settings dialog: one row per model, downloaded models
  first, one primary button that follows the state (Download, Downloading N% -
  Cancel, Resume download, Set active, Active, Install nodes), a menu for the
  model page, the license and deleting files, Open models folder, and a
  Hugging Face token field shown only when a gated model needs it (stored in
  the profile `config.json` only).
- Windowless downloader in the supervisor: queue, HTTP Range resume, sha256
  verification, atomic rename, disk-space and gated (401/403) errors, cancel;
  a tasks-only supervisor mode when the backend is not running.
- On-demand custom node installation (git clone at the pinned commit, pip
  install with ComfyUI's Python) with confirmation and backend restart;
  ComfyUI-GGUF for the FLUX and Qwen tiers.
- Workflow templates selected by the active model: FLUX Fill (GGUF or fp8
  loaders), Qwen-Image-Edit, LaMa/MAT removal (prompt skipped), SDXL
  checkpoint swap for Juggernaut.
- `install.ps1 -ListModels` and `-Model <id> [-HfToken]` for headless parity;
  `-ProfileDir` / `--profile-dir`, `-RemoveConfig` / `--remove-config` and
  `GIMP3_DIRECTORY` support; `install.sh --uninstall` and Linux, Flatpak and
  macOS profile detection.
- Remove object mode in Generative Fill (routes to LaMa/MAT when installed,
  otherwise a background prompt with border pre-fill).
- Floating progress window (`progress_window.py`, `runner.py`): always on top
  without taking the focus, placed over the image window, position remembered
  and moved back on screen when its monitor is gone; plain step text, percent,
  elapsed and remaining time, live TAESD preview from ComfyUI's websocket
  (throttled), download rows, and Cancel (interrupt and clear the queue, image
  untouched). Generation runs in a worker thread.
- Redesigned dialogs (`dialogs.py`): prompt-first Generative Fill, Expand and
  Text to Image with a large multi-line prompt, a Fill with a prompt / Remove
  object switch, Recent prompts (last 20, persisted), an Advanced section
  (Model, Avoid, Variations, Change amount, Seed), a status line, Enter to
  generate, Shift+Enter for a new line, Escape to cancel. Non-interactive PDB
  calls keep the same arguments.
- Variations picker after Fill or Expand with several variations: thumbnails,
  1 to 9 to pick, Keep selected, Keep all, Discard (one undo step).
- Settings General tab with AI backend folder and Browse, Start backend
  automatically, Idle timeout, Show the floating progress window and a
  threaded Check backend button with a readable result; the remaining options
  behind Advanced generation and Connection and troubleshooting expanders.
- Debug dump of the exact crop, mask and raw result (`debug` setting or
  `SB_DEBUG_DUMP=1`).
- `pyproject.toml` (ruff configuration), GitHub Actions CI (ruff and unit
  tests on Python 3.10 and 3.12), `CONTRIBUTING.md`, `SECURITY.md`,
  `docs/security.md`, `docs/performance.md`.
- Tests: catalog validation, resumable downloads, template selection, preview
  parsing, ETA and frame throttling, dialog text logic, config recovery,
  port probing, supervisor argument parsing, geometry helpers; GIMP batch
  harnesses for the case matrix, robustness, the progress window and the UI
  screenshots.

### Changed

- The dialogs' Model field offers the active model, then downloaded catalog
  models, then the rest; the legacy fast/quality tiers remain for scripts.
- Every error message ends with a plain next step (`ui_text.with_next_step`,
  `backend.describe_error`); unexpected errors read "Something went wrong:
  ..." instead of a bare exception name. Settings labels match the messages
  (Start backend automatically, Check backend).
- Prompted fills use a tighter context (a margin of 0.5x the selection instead
  of 1x). The pre-fill depends on the tier: SD 1.5 gets a neutral grey hole,
  SDXL-tier models get the border pre-fill (a grey hole made Juggernaut paint
  a framed picture into the selection). Removal with a generation model keeps
  the wide context and the border pre-fill.
- The removal models (LaMa, MAT) work at a 512 px working size with a 0.5x
  margin, the size their node uses internally; the old 1024 px crop was
  shrunk inside the node and came back soft, with ghosts.
- A one-sided Generative Expand sends a local band of the old image next to
  the new strip as context instead of the whole canvas.
- One backend supervisor per GIMP profile (a start lock), and ComfyUI stays up
  while any GIMP that used it is still running.
- Cancel ends the command quietly (no error dialog, no traceback in the log);
  a message appears only when the job was stopped from outside GIMP.
- Previewing variations in the picker no longer adds undo steps: the fill is
  one undo step, and Discard is one more.
- Messages about a missing model use the short catalog name (for example
  "FLUX.1 Fill [dev]") instead of the packaging details.
- Messages no longer repeat the next step twice; the timeout advice names the
  real field, "Generation time limit".
- The Models tab shows failures of Cancel, Install nodes and Delete
  downloaded files in the tab, and keeps polling after a failed refresh.
- The layer mask of a prompted fill grows only by the feather radius, so it is
  opaque over the selection and fades outward; removal keeps the full grow.
- ComfyUI is started with `--preview-method taesd`; extra server arguments are
  passed as one argument so values such as `--cpu` work.
- Dialogs open centred on the image window.
- Crop PNGs are encoded at zlib level 1 (about half the encode time) and
  uploads are named by content, so re-rolling the same region with a new
  seed or prompt skips the image and mask preparation. Measured timings are
  in `docs/performance.md` (cold start 31 to 38 s, warm SD 1.5 fills 8 to
  11 s, SDXL tiers 20 to 28 s, MAT 3 to 6 s, no memory growth over 20 fills).

### Fixed

- Generative Fill with no selection regenerated the whole image; it now stops
  with "Nothing is selected ..." before starting the backend (`sel-none`).
- Transparent areas in the context were sent to the model as black; the
  context is now flattened over the mean visible colour
  (`img-alpha-transparent`, `img-text-layer`).
- A visible channel tinted the fill; the context is composited with channels
  hidden (`sel-channel-active`).
- Whole-image and edge-to-edge fills got a colour cast from colour matching
  without reference pixels; colour matching is skipped then
  (`sel-whole-image`).
- A pale band around fills, caused by the grown layer mask exposing the
  repainted context.
- Text to Image into a layer produced a layer at the model's working size
  instead of the selection's size (`mode-txt2img-layer`).
- Text to Image into a new image failed in batch mode (no display) and leaked
  the image (`mode-txt2img-image`).
- Indexed images passed in by scripts were filled and squeezed into the
  palette; they are now refused with a hint to convert to RGB.
- Small selections produced a blurry, semi-transparent blob and the removed
  object stayed visible: grow and feather now scale with the selection, the
  model-side mask is no longer blurred past full strength, tiny selections are
  upscaled, and LaMa/MAT get hard masks (`docs/evidence/small-selection/`).
- The Model choice ignored catalog ids when the plug-in was installed through
  a junction or symlink.
- An unreadable `config.json` stopped the plug-in; it is now moved aside as
  `config.json.corrupt-<time>` and defaults are used.
- A busy port produced a server log dump; start-up now names the program that
  holds the port, reports the real elapsed time and strips ANSI codes from log
  excerpts.
- The Settings dialog reports a failing save instead of losing it.
- A ComfyUI that crashed or was closed during a job produced a raw connection
  error; it now gives a plain message and the image is left unchanged
  (`rob-backend-crash-mid-job`).
- Two GIMP instances requesting a fill at the same moment started two
  supervisors and two ComfyUI servers, and the backend shut down when the
  first GIMP closed while the second was still generating
  (`rob-two-requests`, `rob-two-requests-first-gimp-exits`).
- Cancel while the backend was starting took effect only after about 23 s; it
  now stops within a few seconds (`rob-cancel-starting-backend`).
- Cancel while the result was downloading still inserted the layer
  (`rob-cancel-downloading`).
- Cancels were reported as errors with a traceback.
- A resumed download whose checksum failed stopped for good; it is now fetched
  once more from zero (`rob-download-corrupt-part`).
- Download network errors showed raw socket text; they now say what to check.
  Disk-space errors use readable sizes.
- Some uploads, such as the mask of a one-sided expansion, failed with
  "LoadImage: End of file": ComfyUI's PyAV-based image loader took the PNG
  for a video stream. Uploaded PNGs now carry a padding chunk.
- Removal with MAT came back soft and left ghosts of the removed object
  (`photo-*-remove`).
- Quality-tier fills painted a framed picture into the selection
  (`photo-fabric-replace`, `photo-landscape-replace`).
- One-sided Generative Expand came back as a flat colour bar
  (`photo-*-extend`).
- A GLib "Source ID was not found" warning when the progress window closed,
  and picker timers that fired after the picker had closed.
- HTTP error responses were not closed (ResourceWarning).
- The floating progress window was created but never marked visible by
  Windows inside a GUI GIMP session (screenshots taken with PrintWindow did
  not reveal it); it is now shown without taking focus.

### Security

- The Hugging Face token is sent only to Hugging Face hosts over https, never
  forwarded on redirects, and redacted from logs; `config.json` is saved
  owner-only on POSIX.
- Catalog paths must be plain relative names and every catalog file needs a
  sha256 (LaMa gained one); downloads reject wrong resume offsets and
  oversize bodies and remove `.part` files on failure.
- Custom node installs validate the GitHub URL, folder and full commit and
  verify the checked-out commit before pip runs.
- Supervisor tasks are re-validated against the catalog and the config; pids
  from state files only count when they belong to a Python process.
- Multipart upload parameters are escaped.
- A stale supervisor start lock or GIMP watcher entry only counts while its
  pid belongs to a live Python or GIMP process.
- A resumed download that fails its sha256 check is discarded and never used.

### Known issues

- SD 1.5 (the Fast tier) often ignores the prompt on flat or featureless
  regions and on small selections and continues the background instead
  (`sd15-prompt-ablation`). Use the Quality tier (an SDXL model under
  Advanced > Model) for new content there.
- The Quality tier can return a flat tinted area instead of the requested
  content on some structured backgrounds (`photo-architecture-replace`).
- Generative Expand on all sides at once fails on the Quality tier (a blurred
  frame, `photo-landscape-extend-all`); expand one side at a time, or use the
  Fast tier.
- Fine textures (fabric) come back softer in large fills and expansions,
  which are generated below 1:1 resolution.
- MAT cannot rebuild structured backgrounds such as window frames behind a
  removed object (`photo-architecture-remove`).
- The out-of-VRAM and disk-full paths are covered by unit tests only; neither
  could be reproduced end to end on the 8 GB development machine.
- Generative Expand's Discard removes the new layers but keeps the larger
  canvas; `Edit > Undo` twice restores it.
- AUTOMATIC1111, FLUX, Qwen and the Linux, macOS and Flatpak installs are
  not verified end to end.

## [2.0.0-alpha.1] - 2026-10-08

Complete rewrite for GIMP 3. Nothing from the 0.x code base runs under GIMP 3
(`gimpfu`, Python 2 and the old PDB calls are gone), so this is a new major
version that keeps the name, the license and the original author's credit.

### Added

- GIMP 3 plug-in (`Gimp.PlugIn`, libgimp 3 via GObject Introspection) with
  five procedures under `Filters > AI`: Generative Fill, Generative Expand,
  Text to Image, Generative Fill Settings, Stop AI Backend.
- Generative Fill from any selection: context crop, working-size scaling,
  mask grow/feather, result inserted as a new layer with a feathered layer
  mask; 1 to 8 variations in a layer group.
- Generative Expand (outpaint) by margins with seam pre-fill; the canvas only
  grows when generation succeeds.
- Text to Image into a new layer (selection-sized) or a new image.
- ComfyUI backend (primary): API-format workflow builders for SD 1.5 inpainting
  and SDXL + Fooocus inpaint patch, upload/queue/history/view client, stdlib
  websocket progress, readable error mapping (missing model, out of VRAM,
  timeout, rejected workflow).
- Managed backend lifecycle: detached supervisor process starts ComfyUI hidden
  (no console window), binds it to a Job Object, watches the GIMP pid, enforces
  an idle timeout, and exposes state through `server-state.json`.
- AUTOMATIC1111 backend behind the same `Backend` interface (untested on the
  development machine).
- Settings dialog persisted to `<profile>/stable-boy/config.json`, with model
  lists populated from the server.
- `install.ps1` / `install.sh`, unit tests (`tests/`), end-to-end batch script
  (`tests/gimp_batch_fill.py`), `docs/design.md`, `docs/models.md`,
  `docs/evidence/`.

### Changed

- Inpainting no longer needs a layer named `Inpainting Mask`; the selection is
  the mask.
- Results are always layers with masks (the old "Images" target survives only
  in Text to Image).

### Removed

- GIMP 2.10 / Python 2 sources (`src/`), the X/Y plot script, the upscale
  command and the img2img command. Image to Image is covered by Generative
  Fill with a strength below 1.0.

## [0.4] - 2023

Last GIMP 2.10 release by Torben Giesselmann. Script support (X/Y plot),
inpainting mask applied to new layers, shared preferences dialog, command
pattern refactoring.

## [0.3.3] / [0.3.2] / [0.3.1] / [0.3] - 2022-12

Timeout handling, progress bar, sampler list updates, automatic inpainting
area detection, upscaler settings.

## [0.2] - 2022-12-04

Rectangular selections as processing region; Windows startup fix.

## [0.1] - 2022-12-02

Initial release: text to image, image to image, inpainting, upscaling via the
AUTOMATIC1111 WebUI API.

[Unreleased]: https://github.com/thndrbrrr/gimp-stable-boy/compare/v2.0.0-beta.1...HEAD
[2.0.0-beta.1]: https://github.com/thndrbrrr/gimp-stable-boy/compare/v2.0.0-alpha.1...v2.0.0-beta.1
[2.0.0-alpha.1]: https://github.com/thndrbrrr/gimp-stable-boy/compare/v0.4...v2.0.0-alpha.1

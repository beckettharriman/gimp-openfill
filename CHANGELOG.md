# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/thndrbrrr/gimp-stable-boy/compare/v2.0.0-alpha.1...HEAD
[2.0.0-alpha.1]: https://github.com/thndrbrrr/gimp-stable-boy/compare/v0.4...v2.0.0-alpha.1

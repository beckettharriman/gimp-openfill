# Small-selection removal bug (2026-10-08)

Report: removing a ~40 px button on a black knit jacket (selection 38 x 33 px
in a 3024 x 4032 photo) with Juggernaut XL, and again with MAT, produced a soft
near-black blob under the feathered mask; the button was only darkened.

Reproduced here with synthetic scenes (dark knit, small bright button) at two
image sizes, with `tests/gimp_batch_small_selection.py` driving a real GIMP
instance, an empty prompt, and the debug dump (`SB_DEBUG_DUMP=1`) that keeps
the exact crop and mask sent to ComfyUI plus the raw result. Beckett's own
crop was tested as well (at native and 20 % scale) but those files are not
committed.

## Root causes (with evidence)

1. **Fixed 24 px layer-mask feather and 16 px model-side grow, independent of
   the selection size.** `before-560px/report.json`, mask statistics measured
   on the actual layer mask: center value 253/255, only 688 of the 3,216
   selected pixels at >= 250 opacity, 9,896 pixels with partial opacity (3x
   the selection). On Beckett's 38 px selection the 24 px feather exceeds the
   object, so the new layer is semi-transparent everywhere and the original
   button shows through "darkened".
2. **The model-side mask was blurred by that same 24 px before it reached the
   model.** `INPAINT_ExpandMask(grow=16, blur=24)` on a ~40 px disk leaves no
   pixel at mask value 1.0; ComfyUI (InpaintModelConditioning,
   DifferentialDiffusion) and the LaMa/MAT node only treat values >= 1.0 as
   "repaint fully", so every model family repainted the region only
   partially. `before-560px/mat-dump/result-0.png` (raw MAT output) still
   contains a ghost of the button; same for Juggernaut and SD 1.5.
3. **Context crop at 1:1 for tiny selections.** A 38 px selection became a
   768 x 768 crop (SDXL minimum) at scale 1.0, the object being 5 % of the
   frame, which diffusion models paint as blur.
4. **Prefill blurred the object into the hole.** For "fill" the masked area
   was pre-filled with a blur of its own content, so an empty prompt on SD 1.5
   / Juggernaut produced a disc or sphere in the button's colour
   (`after-560px` first iteration, superseded below).
5. **Dialog model choice silently ignored on junction installs.** The Model
   choice was registered without the catalog ids (plug-in folder resolved
   without following the junction), so `model=juggernaut-xl-v9` fell back to
   the active model. Fixed (`Path(__file__).resolve()`); evidence: pluginrc had
   zero catalog ids before, every run used the active model.

The paste path itself was correct: in every run the layer content is
byte-identical to the raw ComfyUI output (`content_vs_raw.identical: true`
in all reports), offsets and sizes match the context rectangle.

## What changed

- `geometry.context_rect`: margin = 1x the selection's larger side on each
  side (context about 3x the selection), minimum context 192 (SD 1.5) / 256
  (SDXL, FLUX, Qwen) instead of 512 / 768; `working_size` upscales up to 8x
  (Lanczos in ComfyUI) so the object fills the frame, the result is scaled
  back and composited only inside the mask.
- `geometry.mask_params`: grow = 15 % of the larger side (6 to 48 px), layer
  feather = 6 % (1 to 24 px), model-side blur never larger than the grow so
  the original selection stays at 1.0; removal models get a hard mask (blur
  0); the GIMP layer mask is the selection grown then feathered.
- Removal tier (LaMa/MAT): 512 px context at 1:1, no upscaling (texture scale
  matches the surroundings).
- Empty prompt or the new **Remove object** checkbox: routes to an installed
  LaMa/MAT model, otherwise uses a background prompt plus an object-averse
  negative prompt, strength 1.0, and a border pre-fill (navier-stokes from the
  surroundings) instead of blurring the object into the hole.
- Settings: `grow_percent`, `feather_percent` (caps remain `grow`, `feather`).

## Before / after (same scene, same seed, empty prompt)

| Case | Before (`before-560px/`) | After (`after-560px/`) |
|---|---|---|
| SD 1.5 | button darkened, soft blob (`sd15-after-crop.png`) | clean fabric (`sd15-after-crop.png`); context 192 px upscaled 2.67x to 512 |
| Juggernaut XL + Fooocus | button darkened (`juggernaut-after-crop.png`) | clean fabric, weave continuous (`juggernaut-after-crop.png`); context 256 px upscaled 3x to 768 |
| MAT | button darkened, ghost in raw output | button gone, faint texture wobble (`mat-after-crop.png`); 512 px context at 1:1 |
| Layer mask | center 253, 688 px >= 250 of 3,216 | center 255, 3,900 px >= 250 (selection grown 6 px, feather 4 px) |

`after-1600px/` repeats the three models on the 1600 x 1200 scene with a
52 px selection (all three clean; `report.json` has the numbers).
`00-before-crop.png` in each folder is the input crop. Two debug dumps are kept:
`before-560px/mat-dump/` (blurred `sent-mask.png`, ghosted `result-0.png`,
`request.json` with grow 16 / feather 24) and `after-560px/juggernaut-dump/`
(hard-edged grown mask, clean `result-0.png`, `request.json` with the new
parameters).

On Beckett's real crop scaled to 20 % (53 x 45 px selection, not committed):
SD 1.5 and Juggernaut remove the button and leave only a faint ring where the
rim lay just outside the lasso (reason for the 15 % default grow); MAT at
1:1 removes it with slightly softer knit texture.

## Settings guidance

- **Object removal**: tick "Remove object" (or leave the prompt empty) with
  `mat-places512` or `lama-big` installed. Fast, no hallucinated objects.
  Juggernaut/SD 1.5 with the same checkbox also work now but can invent
  texture on very large holes.
- **Generative fill (put something there)**: a descriptive prompt, strength
  1.0, Quality tier (SDXL/Juggernaut) for photos; keep the selection snug
  around the area, the plug-in adds the context and the grow itself.
- Mask grow 15 % / feather 6 % of the selection are the new defaults; raise
  the grow when an object's edge (rim, shadow) is not fully inside the
  selection.

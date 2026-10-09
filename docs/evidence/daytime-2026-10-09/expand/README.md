# Generative Expand: all sides in one pass (2026-10-09, daytime)

Requirement: Generative Expand renders all sides at once, in one pass, and the
new area continues the scene. An empty prompt means "continue the scene". A
large expansion may run in rounds, but every round grows all sides at once.
The sequential one-side-at-a-time workaround (`geometry.expand_steps`, added
overnight for the SDXL tier) is replaced.

## Diagnosis

The overnight all-sides failure (`../../overnight-2026-10-09/sd15-ab/expand-all-before-fix-raw-layer.png`)
was reproduced outside GIMP with the plug-in's own geometry and workflow code
on landscape (192 px on all sides) and architecture (192 px, then 128 px).
Juggernaut XL v9 with the Fooocus patch paints a matted picture frame with a
drop shadow, or a flat grey or blurred ring, around the untouched old image
(`variants/diagnosis-prefill-variants-old-prompt.jpg`, first two rows of
`variants/landscape-192-seed1234.jpg` and `variants/architecture-128-seed1234.jpg`).

The candidates were checked one at a time (seed 1234, same canvas):

| Candidate | Test | Result |
|---|---|---|
| Border pre-fill (navier-stokes + 65 px blur) preserved by the sampler | Pre-fill replaced by edge extension + blur, mirror + blur, neutral grey, or edge extension with no blur, all with the old prompt | Frame with every smooth pre-fill (edge, mirror, neutral); no blur gives a continued scene but turns the streaks into objects (bowls, planter). The pre-fill shapes the result, but no pre-fill fixes it on its own. |
| Prompt | Old empty-prompt positive ("seamless continuation of the surrounding background, ...") vs an empty positive with the negative "new objects, people, text, frame, border, vignette, watermark, blurry" | **The frame disappears** with the new negative, whatever the pre-fill (navier-stokes, edge, mirror). A user prompt with the old negative also gives the frame (`landscape-jugg-cur-prompted`); adding frame terms to the negative removes it. |
| Denoise schedule / Fooocus | denoise 0.95 with 35 steps; two-stage (half-size layout pass, then refine at 0.6) | 0.95: no change. Two-stage: worse (green side panels, an invented pink pot) (`variants/diagnosis-prompt-and-two-stage.jpg`). |
| Working size 1024 on a 4-side strip | max side 768, 1152, 1280 | No consistent effect: 1152 helps the landscape bottom once and invents a second person on the face strip. |
| Mask grow / overlap | overlap 8, 16, 32 (default), 64, 96; grow 0 to 32 | Overlap under 32 leaves a visible frame line at the old edge (`variants/diagnosis-insets-and-edge-prefill.jpg`); 64 to 96 do not improve the join. |
| Ring size ("the mask covers so much") | 640 px on all sides of the landscape (old image 60 % of the width, 53 % of the height of the canvas) | With the new prompt the blurred ring comes back in a single pass; two all-sides rounds of 320 px give a continued scene (`variants/landscape-640-onepass-vs-2rounds.jpg`). |

Mechanism: ComfyUI's KSampler at denoise 1.0 adds noise to the VAE-encoded
pre-fill rather than replacing it, so the low-frequency look of the pre-filled
ring survives sampling. A smooth band around a sharp photograph is what a
matted, framed or vignetted print looks like. Juggernaut renders exactly that
unless the negative names it and the positive does not ask for a "background".
SD 1.5 inpainting did not show the frame (it continued the scene with the old
prompt too, apart from a dark blob in one corner).

A faint vertical step in smooth skies at the left keep edge comes from the
photo itself, not from the pre-fill: the original landscape darkens by about 15
levels over its outer 120 px (lens vignetting). The generated sky continues the
brighter interior.

## Variant table (Quality tier, Juggernaut XL v9, empty prompt)

Scores from 1 to 5, judged by looking at each composite: continuity of horizon,
lighting and texture on all sides; no invented objects; no vignette or frame;
no visible join. Sheets are in `variants/`. "cont" = empty positive plus the
continuation negative; "remcont" = the old removal positive plus the
continuation negative; "seam" = overlap 64 and a layer feather of 48 px.

| Variant | Landscape 192 all (s1234 / s7) | Architecture 128 all (s1234 / s7) | Product 192 top+bottom (s1234 / s7) | Face 256 right (s1234 / s7) |
|---|---|---|---|---|
| old default, one pass (old prompt, cfg 7) | 1 frame / 2 wooden wall at the right | 1 grey frame / 2 bar across the bottom | 1 hard grey bands / 1.5 | 5 / 1.5 invented machinery |
| old default, sequential sides (emulated) | 1 frames and green panels | - | - | (one side: same as the one-pass row) |
| (a) edge pre-fill + blur, old prompt | 1 frame | - | - | - |
| (a) edge pre-fill + cont + cfg 4 | 3 objects at the bottom / 3 ditch, whitewashed trunk | 3 lamp, distorted pillar | 2.5 grey band, hard edge | - |
| (b) two-stage, cont | 1.5 side panels, pot | - | - | - |
| (c) cont + cfg 4 + working size 1152 | 3.5 / 3 second birch | 3.5 | 3 grey floor band | 1 invented person |
| (d) cont, cfg 7 | 3 turf band and seams at the bottom, tree pit | 3.5 | 4 | 3 tonal step |
| (d) cont + cfg 4 | **3.5** bright band at the bottom / 3.5 ditch | **3.5** / 3.5 orange tank at the right | **4.5** / 4 | **3.5** faint step / run failed (backend timeout) |
| (d) remcont + cfg 4 | 3 stones at the bottom / 3.5 | 3.5 / 3 | 2 grey bands / 2.5 | 4.5 / 2.5 dark panels |
| (e) cont + cfg 4 + seam (overlap 64, feather 48) | 2.5 sign post, stones | 3 | 4 | 3 |
| (e) overlap 8 or 16 (cont, cfg 7) | 2.5 visible frame line | - | - | - |

User prompt ("green meadow and evening sky with trees, photo"): with only
"frame, border, vignette, picture in picture, watermark" appended to the user
negative there is no frame (3: blurred foliage at the bottom edge;
`variants/landscape-seed7-remcont-oldsequential-userprompt.jpg`). The old
default gives the frame.

SD 1.5 (landscape 192, all sides): old prompt 3.5 (dark blob in the bottom-left
corner); cont 4.5; cont + cfg 4 4.5 (`variants/sd15-old-vs-new-prompt.jpg`). No
regression.

Rounds, landscape 640 px on all sides: one pass 1 (blurred ring); 2 rounds of
320 px 2.5 (scene continues, smeared grass and a lamp post in the outer ring);
3 rounds of about 213 px 1.5 (wooden frame at the top, green bokeh patches).
More rounds compound the errors, so the round size stays at 0.25 of the canvas.

## Chosen default

- One pass with every growing side and the whole canvas as context
  (`App.generative_expand` -> `App._expand_round`, `geometry.plan_expand`).
- Rounds only when a margin exceeds 0.25 of the canvas side it grows from
  (`geometry.expand_rounds`, `EXPAND_ROUND_FRACTION`). Every round grows all
  requested sides; only the last round makes the requested variations.
- Empty prompt: empty positive, negative `workflow.EXPAND_NEGATIVE` ("new
  objects, people, text, frame, border, vignette, watermark, blurry") plus the
  user's negative. User prompt: kept as typed, with `workflow.EXPAND_FRAME_NEGATIVE`
  appended to the user's negative (`workflow.expand_prompts`).
- SDXL tier: cfg capped at 4 for expands (`workflow.expand_cfg`); SD 1.5 keeps
  the configured cfg.
- Unchanged: navier-stokes + blur pre-fill, overlap 32, mask grow and feather.
  The edge, mirror and neutral pre-fills, the two-stage schedule, larger working
  sizes and other insets did not beat these.
- `geometry.expand_steps` (sequential sides) is removed, not kept as a fallback.
  It scored 1 with the old prompt here, and in no tested case did it do better
  than the one-pass default.

Why: the frame is a prompt problem. The new negative removes it on every
tested photo and seed while the scene continues across all four sides at once;
cfg 4 removes most of the over-saturated bands that cfg 7 left at the bottom
edge and around the white product.

## Headless verification (GIMP 3.2.6, final code)

`gimp-console-3.2.exe` with the test profile, launched by
`C:\AI\overnight-scratch\day\expand\run_verify.py` (a copy of the overnight
matrix launcher writing JPEG evidence), spec `verify-spec.json`, empty prompt,
seed 1234, 1 variation. Each case folder has `before.jpg`, `after.jpg`,
`composite.jpg` (before placed on the new canvas | after), `join-1to1.jpg`
(1:1 crop across the old edge of the first growing side), `report.json`,
`plugin-log.txt` and `batch-command.txt`.

| Case | Model | Mechanical checks | Score | Notes |
|---|---|---|---|---|
| landscape-all-192 | Juggernaut XL v9 | PASS (seam metric 5.6) | 3.5 | No frame. Horizon, sky and meadow continue on all four sides, with foliage at the right. Bottom: a brighter turf band and an invented tree pit at the trunk. Faint sky step at the left (the photo's own vignetting). |
| face-right-256 | Juggernaut XL v9 | PASS | 3.5 | Grey-green backdrop continues; a lighter vertical band at the join is visible at 1:1. The old default scored 5 on this seed (4 overnight), so this one-sided case regresses slightly. |
| architecture-all-128 | Juggernaut XL v9 | FAIL no_hard_seam_at_old_edge (34.1) | 3.5 | No frame. Facade, windows and wall continue on all sides. The seam metric is high because window frames and the pink pillar meet the old edge; the pillar is distorted bottom right. |
| product-top-bottom-192 | Juggernaut XL v9 | PASS | 4 | White background continues; very faint soft bands near the top and bottom. Old default: hard grey bands (1). |
| landscape-all-192-sd15 | SD 1.5 inpainting | PASS | 4.5 | Seamless; birch crown and meadow continue. |
| landscape-all-640-rounds | Juggernaut XL v9 | FAIL new_layer_or_group, old_pixels_outside_mask_unchanged (by construction: two rounds give two layers, and the second round regenerates the first round's overlap band) | 1.5 | Two rounds of 320 px. The first round's ring continues the scene, but the second round's outer ring comes back smeared and green with a visible rectangle. Large expansions remain an open issue. |

## Open issues

- Very large expansions (more than about 25 % per side) are still poor on the
  Quality tier, even in rounds: each further round reads a downscaled canvas
  (0.32x at 3200 px) and its ring tends to come back smeared.
- One-sided strips on smooth backdrops (face-right-256) show a faint tonal step
  that the old "seamless continuation" positive avoided on seed 1234 (but not
  on seed 7). A per-case positive was not adopted on two seeds of evidence.
- The bottom edge of the landscape tends to get a band (turf strip, ditch) and
  sometimes a small invented object, despite "new objects" in the negative.
- Photos with lens vignetting leave a faint step where the original's darker
  edge meets the brighter generated continuation.

Experiment scripts and every run (generated layer, pre-fill input, composite,
graph): `C:\AI\overnight-scratch\day\expand\` (`exp.py`, `exp2.py`,
`variants.json`, `runs\`).

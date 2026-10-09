# Quality ledger, overnight 2026-10-09

Visual scoring of every evidence case that has a report.json (rob-fresh-install
is an installer transcript and sd15-prompt-ablation is an analysis folder; both
are skipped). Each case was judged from before.png, after.png and the crops,
plus a histogram-equalized copy of the after crop to expose faint tonal steps.
Where after.png was pixel-identical to mode-fill (checked numerically) the
mode-fill scores are reused.

Scale, 1 to 5 (5 best):

- 5: no visible problem, even in the equalized view
- 4: only visible in the equalized view or on close inspection
- 3: visible at normal view if you look for it
- 2: obvious at normal view
- 1: severe, or the requested content is absent

Columns: seams (boundary between generated and original), color (tonal shift of
the generated area), blur (generated area softer than surroundings), artifacts
(blobs, duplicated edges, ghosts, text garbage), mask edge (feathered transition,
halo), content (requested content present; for removal, object gone and
background continues). "-" means not applicable (error cases, plain txt2img).

Verdicts: PASS = good result; PASS-WITH-NOTES = usable but with a visible flaw
or partial content; FAIL = requested content missing, wrong, or damaging
artifacts. A synthetic scene is used (sky gradient, checker grass, dark box,
sun), so "red brick wall" only needs to read as brick.

Selection respect: for every fill case the report measured outside_max_abs_diff
= 0 outside the grown mask, and no case showed changes outside the selection,
wrong layer offsets, hidden-layer leaks or aspect errors, so this is not
repeated per row.

Counts: PASS 5, PASS-WITH-NOTES 27, FAIL 23, not scored 0 (of 55 cases with a report.json).

| case | model | report time | status (report / plug-in) | seams | color | blur | artifacts | mask edge | content | verdict | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| img-1024 | sd15-inpainting | 2026-10-09T00:30:58 | pass / success | 3 | 3 | 4 | 3 | 3 | 1 | FAIL | 1024x1024: dark box removed and sky/grass continued, no brick at all; faint horizontally striped pale rectangle in the sky and a darker patch in the grass where the box was. |
| img-16bit-int | sd15-inpainting | 2026-10-09T00:31:18 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill (max diff 2/255), so 16-bit integer precision is handled; same faint sky halo as mode-fill. |
| img-256 | sd15-inpainting | 2026-10-09T00:30:56 | pass / success | 3 | 3 | 3 | 4 | 3 | 1 | FAIL | 256x256: box removed, no brick; soft pale box clearly visible in the sky at this size; result slightly softer than surroundings. |
| img-3000 | sd15-inpainting | 2026-10-09T00:31:02 | pass / success | 3 | 4 | 4 | 4 | 3 | 3 | PASS-WITH-NOTES | 3000x2000: flat red building block with small windows, no brick/mortar pattern; faint pale halo on its right; layer 2286x2000 at (468,0) clipped at canvas height, no offset error. |
| img-32bit-float | sd15-inpainting | 2026-10-09T00:31:19 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill (max diff 2/255); float precision handled. |
| img-6000 | sd15-inpainting | 2026-10-09T00:31:14 | pass / success | 3 | 4 | 4 | 4 | 3 | 3 | PASS-WITH-NOTES | 6000x4000: two flat red blocks with windows, no brick texture; layer 4572x4000 at (936,0); 14.7 s. |
| img-alpha-transparent | sd15-inpainting | 2026-10-09T00:31:21 | pass / success | 2 | 1 | 3 | 1 | 2 | 1 | FAIL | Part of the selection over the transparent hole became an opaque black rounded block; the dark box part was replaced by sky; no brick. |
| img-aspect-tall | sd15-inpainting | 2026-10-09T00:31:15 | fail / success | 4 | 4 | 3 | 3 | 4 | 1 | FAIL | 256x4096: the selected section of the dark pole was reproduced, no brick (mean diff 4.3); faint striped ghosts beside the pole. |
| img-aspect-wide | sd15-inpainting | 2026-10-09T00:31:15 | fail / success | 3 | 4 | 4 | 3 | 4 | 1 | FAIL | 4096x256: the dark bar inside the selection was kept, no brick (mean diff 3.0); faint pale smear in the sky above it. |
| img-grayscale | sd15-inpainting | 2026-10-09T00:31:16 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Grey stone/brick block courses, plausible for a grayscale image; result stays grayscale; faint halo box in the sky. |
| img-indexed | sd15-inpainting | 2026-10-09T00:35:03 | fail / success | - | - | - | - | - | - | FAIL | Expected an indexed-mode error, but the test image was RGB (base_type 0): the harness never converted it, the plug-in ran a normal fill identical to mode-fill. Error path untested. |
| img-linear | sd15-inpainting | 2026-10-09T00:31:20 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill (max diff 2/255); linear-light precision handled, no gamma shift. |
| img-multilayer-hidden | sd15-inpainting | 2026-10-09T00:31:24 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill, so the hidden layer did not leak into the context; same faint halo. |
| img-rotated-layer | sd15-inpainting | 2026-10-09T00:31:23 | pass / success | 2 | 3 | 2 | 3 | 3 | 1 | FAIL | Inside the selection the crisp coloured mosaic turned into a muddy, blurred mosaic; visible rectangular soft patch; no brick. |
| img-text-layer | sd15-inpainting | 2026-10-09T00:31:22 | pass / success | 3 | 4 | 4 | 1 | 3 | 1 | FAIL | Black blocky shapes that continue the strokes of "SALE" (text garbage); the "E" outside the selection stays; no brick. |
| img-unsaved-new | sd15-inpainting | 2026-10-09T00:35:10 | fail / success | 3 | 3 | 4 | 3 | 3 | 1 | FAIL | Different scene (four coloured boxes): almost unchanged (mean diff 1.2); dark red smudge in the brown box corner and a tonal step inside the white box; no brick. |
| img-with-path | sd15-inpainting | 2026-10-09T00:31:33 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill; the vector path did not interfere. |
| mode-expand-all | sd15-inpainting | 2026-10-09T00:31:44 | pass / success | 3 | 4 | 4 | 2 | 3 | 4 | PASS-WITH-NOTES | 1280x1024: sky and grass continue on all sides, but a spurious dark hut-shaped object appears on the right horizon with a smeared vertical left edge; faint vertical band in the left sky. |
| mode-expand-bottom | sd15-inpainting | 2026-10-09T00:31:43 | pass / success | 4 | 4 | 4 | 4 | 4 | 5 | PASS | Grass continues into the new 128 px strip; texture very slightly noisier, no visible seam at normal view. |
| mode-expand-left | sd15-inpainting | 2026-10-09T00:31:40 | pass / success | 3 | 4 | 4 | 4 | 3 | 5 | PASS-WITH-NOTES | Faint vertical band at the old canvas edge in the sky; the new grass strip is slightly noisier than the original checker. |
| mode-expand-right | sd15-inpainting | 2026-10-09T00:31:42 | pass / success | 3 | 3 | 4 | 4 | 3 | 5 | PASS-WITH-NOTES | The new right strip of sky is slightly brighter, giving a visible vertical band; the grass checker is a little rotated and softer. |
| mode-expand-top | sd15-inpainting | 2026-10-09T00:35:11 | fail / success | 4 | 4 | 5 | 4 | 4 | 5 | PASS | Sky gradient continues cleanly into the new strip. The report's new_area_not_flat check failed (Laplacian var 0.38), but a flat sky is the correct result, so that check is a false positive here. |
| mode-fill | sd15-inpainting | 2026-10-09T00:31:39 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Baseline: brick wall fills the upper (sky) half of the box, grass continues below; faint pale rectangle in the sky around the grown/feathered band; faint dark ghost in the grass. |
| mode-remove | sd15-inpainting (Remove -> mat-places512) | 2026-10-09T00:31:40 | pass / success | 3 | 4 | 3 | 3 | 3 | 4 | PASS-WITH-NOTES | Remove routes to MAT. The box is gone and the sky is clean apart from a faint pale box; under the old box the grass has blotchy irregular strokes that break the checker pattern. |
| mode-seed-fixed-repeat | sd15-inpainting | 2026-10-09T00:31:59 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Two runs were byte-identical (repeat diff 0); the image equals mode-fill. |
| mode-seed-random | sd15-inpainting | 2026-10-09T00:31:56 | pass / success | 3 | 3 | 4 | 2 | 3 | 1 | FAIL | Seeds do differ (run1: black slab with a green slab beside it; run2: black house silhouette), but neither run has brick; hard-edged black blobs. |
| mode-tier-juggernaut | juggernaut-xl-v9 | 2026-10-09T00:31:51 | pass / success | 3 | 3 | 5 | 3 | 3 | 5 | PASS-WITH-NOTES | Crisp red brick pillar with mortar; a clearly visible pale halo rectangle around it in the sky; small dark shadow wedge at its lower right. |
| mode-tier-mat | mat-places512 | 2026-10-09T00:31:52 | pass / success | 3 | 4 | 3 | 3 | 3 | 4 | PASS-WITH-NOTES | Same as mode-remove (diff under 0.01); MAT in 4.2 s; same blotchy grass under the old box. |
| mode-tier-sd15 | fast (sd15-inpainting) | 2026-10-09T00:31:49 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | The "fast" tier resolved to sd15-inpainting; pixel-identical to mode-fill. |
| mode-tier-sdxl-fooocus | quality (sdxl-base + Fooocus) | 2026-10-09T00:31:50 | pass / success | 3 | 3 | 5 | 3 | 3 | 5 | PASS-WITH-NOTES | The "quality" tier is sdxl-base plus Fooocus: crisp brick column, visible pale halo rectangle in the sky, dark green shadow slab spilling onto the grass. |
| mode-txt2img-image | sd15-inpainting | 2026-10-09T00:35:12 | pass / success | - | - | 5 | 4 | - | 5 | PASS | New 680x512 image (matches the 4:3 source aspect) showing a log cabin in a meadow, photographic; thin bright vertical line on the right border. |
| mode-txt2img-layer | sd15-inpainting | 2026-10-09T00:35:12 | pass / success | - | - | 5 | 5 | - | 5 | PASS | The cabin photo sits exactly in the 256x192 selection at (100,100), hard edge by design; nothing outside the selection changed. |
| mode-variations-4 | sd15-inpainting | 2026-10-09T00:31:48 | pass / success | 3 | 3 | 4 | 3 | 3 | 3 | PASS-WITH-NOTES | The group has 4 masked variations with only the first visible. v1 is brick (same as mode-fill), v2 is a black block, v3 and v4 are plain sky/grass, so only 1 of 4 has the requested content. |
| prompt-empty | sd15-inpainting | 2026-10-09T00:31:34 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | An empty prompt became "seamless continuation..."; box removed cleanly; faint pale box in the sky. |
| prompt-negative-only | sd15-inpainting | 2026-10-09T00:31:38 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Same as prompt-empty (negative "red, bricks, text, people" respected); faint pale box in the sky. |
| prompt-quotes-backslashes | sd15-inpainting | 2026-10-09T00:31:37 | pass / success | 3 | 4 | 4 | 4 | 3 | 2 | PASS-WITH-NOTES | The string survived (the layer name keeps the quotes and backslashes), but the model painted background continuation, no sign. |
| prompt-unicode-emoji | sd15-inpainting | 2026-10-09T00:31:36 | pass / success | 3 | 4 | 4 | 4 | 3 | 2 | PASS-WITH-NOTES | No crash, and the layer name keeps the unicode; the result is background continuation with nothing related to the prompt. |
| prompt-very-long | sd15-inpainting | 2026-10-09T00:31:35 | pass / success | 3 | 4 | 5 | 4 | 3 | 5 | PASS-WITH-NOTES | Fine-grained weathered brick with white mortar, crisp; faint pale halo; long prompt accepted (13 s). |
| sel-channel-active | sd15-inpainting | 2026-10-09T00:30:56 | pass / success | 2 | 1 | 1 | 1 | 2 | 1 | FAIL | The active drawable was the user channel. The generated layer has the pink/orange channel tint baked in and composites as a flat salmon rounded block with no texture; no brick. |
| sel-corner-bottomright | sd15-inpainting | 2026-10-09T00:30:49 | fail / success | 4 | 4 | 3 | 4 | 4 | 1 | FAIL | Grass continued, no brick (mean diff 3.8); a softer strip runs along the right canvas edge inside the selection. |
| sel-corner-topleft | sd15-inpainting | 2026-10-09T00:30:48 | fail / success | 4 | 4 | 4 | 4 | 4 | 1 | FAIL | Sky continued, no brick (mean diff 1.0); clean otherwise. |
| sel-edge-bottom | sd15-inpainting | 2026-10-09T00:30:47 | fail / success | 4 | 4 | 4 | 4 | 4 | 1 | FAIL | Grass continued, no brick (mean diff 1.9). |
| sel-edge-left | sd15-inpainting | 2026-10-09T00:30:45 | fail / success | 3 | 4 | 4 | 4 | 4 | 1 | FAIL | Sky/grass continued, no brick; faint pale box in the sky. |
| sel-edge-right | sd15-inpainting | 2026-10-09T00:30:46 | fail / success | 3 | 4 | 4 | 4 | 4 | 1 | FAIL | Sky/grass continued, no brick; faint pale box in the sky. |
| sel-edge-top | sd15-inpainting | 2026-10-09T00:35:03 | fail / success | 4 | 4 | 4 | 4 | 4 | 1 | FAIL | Sky continued, no brick (mean diff 0.85); faint banding only in the equalized view. |
| sel-feathered | sd15-inpainting | 2026-10-09T00:30:51 | pass / success | 3 | 3 | 4 | 4 | 3 | 3 | PASS-WITH-NOTES | 20 px feather: flat red wall with faint vertical streaks, weak brick pattern (no mortar courses); soft bluish glow around it; feathered edge itself looks natural. |
| sel-huge-85pct | sd15-inpainting | 2026-10-09T00:30:44 | pass / success | 3 | 3 | 3 | 2 | 3 | 1 | FAIL | No brick: the grass checker grows into city-skyline silhouettes with cartoon clouds, and the sun is gone (it was inside the selection); 4% border ring faintly visible. |
| sel-layer-in-group | sd15-inpainting | 2026-10-09T00:30:54 | pass / success | 2 | 2 | 2 | 3 | 3 | 1 | FAIL | Layer inside a group, no offset error, but the selected part of the vivid mosaic became a desaturated, muddy green-grey rectangle, clearly visible; no brick. |
| sel-layer-mask-active | sd15-inpainting | 2026-10-09T00:30:55 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill; an active layer mask did not redirect the fill. |
| sel-layer-offset | sd15-inpainting | 2026-10-09T00:30:53 | pass / success | 2 | 2 | 2 | 3 | 3 | 1 | FAIL | Offset 400x300 layer: aligned correctly, but the selected mosaic became a muddy, desaturated, blurred rectangle; no brick. |
| sel-multi-disjoint | sd15-inpainting | 2026-10-09T00:30:50 | fail / success | 4 | 4 | 4 | 4 | 4 | 1 | FAIL | Both rectangles were continued as sky/grass, no brick (mean diff 1.6); one layer spans the full 1024x768 canvas. |
| sel-none | sd15-inpainting | 2026-10-09T00:30:35 | pass / execution-error | - | - | - | - | - | - | PASS | Error case. Message is plain and names next steps ("Select the area ... Rectangle or Free Select ... To regenerate the whole image, use Select > All"); no layer added, composite and selection unchanged. The log carries a full traceback for this user error (noise only). |
| sel-quickmask-painted | sd15-inpainting | 2026-10-09T00:30:52 | pass / success | 3 | 4 | 4 | 2 | 3 | 1 | FAIL | Painted blob over the box's upper-left: the box gains a step/notch shape and vertical streak lines, plus a grey haze smear in the sky above; no brick. |
| sel-tiny-20px | sd15-inpainting | 2026-10-09T00:35:02 | fail / success | 4 | 5 | 4 | 3 | 4 | 1 | FAIL | 20 px selection inside the flat dark box: effectively unchanged (mean diff 0.0) apart from a faint L-shaped edge line along the top/left of the mask; no brick. |
| sel-whole-image | sd15-inpainting | 2026-10-09T00:30:39 | pass / success | 5 | 2 | 5 | 4 | 5 | 3 | PASS-WITH-NOTES | Full-frame brick wall with clear mortar, sharp, but mint/teal instead of red. |

## Failures and concerns

Every FAIL and every score of 2 or lower, with what was seen and the most
likely cause on the plug-in side. "Hypothesis" means not verified in code.

### A. SD 1.5 ignores the prompt over flat or small regions (13 FAILs)

Cases: img-1024, img-256, img-aspect-tall, img-aspect-wide, img-unsaved-new,
sel-corner-bottomright, sel-corner-topleft, sel-edge-bottom, sel-edge-left,
sel-edge-right, sel-edge-top, sel-multi-disjoint, sel-tiny-20px (content 1).

Seen: the masked area becomes a clean continuation of the surroundings (sky,
grass, the dark box or pole) with no brick. Seams are mostly good (3 to 4), so
these are quiet failures that look like nothing happened. The same prompt and
seed on the 1024x768 mode-fill case does produce brick, so the outcome flips
with small changes in crop size or position.

Hypothesis: the sd15-prompt-ablation folder shows the SD 1.5 inpainting
checkpoint itself continues flat context at denoise 1.0, independent of
pre-fill, colour match and DifferentialDiffusion. On the plug-in side, the
blurred pre-fill gives the model a smooth colour inside the mask that it is
happy to keep. Suggested direction: for Fill (not Remove), pre-fill with noise
or a neutral grey instead of the blurred surroundings, or route Fill to the
SDXL/Fooocus tier by default. In mode-tier-sdxl-fooocus and
mode-tier-juggernaut the content appears reliably. sel-tiny-20px also shows a
faint L-shaped line along the mask's top/left edge (artifacts 3): a 3 px
feather at 2.67x upscale leaves a one-pixel step.

### B. img-alpha-transparent (FAIL; seams 2, color 1, artifacts 1, mask edge 2, content 1)

Seen: where the selection overlaps the fully transparent hole, the new layer is
an opaque black rounded block. Where it overlaps the dark box, the box is
replaced by sky.

Hypothesis: the context crop is exported with alpha dropped (transparent pixels
become RGB 0,0,0) instead of being composited over a neutral colour or
inpainted. The model continues the black, and the result layer is fully opaque
there, so the transparent area becomes black. Fix in the context export
(composite over mid-grey or the image background before sending) and keep the
source alpha outside the original opaque region if transparency should
survive.

### C. sel-channel-active (FAIL; seams 2, color 1, blur 1, artifacts 1, mask edge 2, content 1)

Seen: drawables = ["user channel"]. The generated layer (raw layer.raw in
scratch) is the box-free scene, but tinted pink/orange like the channel overlay.
In the composite it shows as a flat salmon rounded block with no texture
(Laplacian variance in/out about 9.8, a flat blob).

Hypothesis: when a channel is the active drawable, the context is taken from the
projection/visible composite, which includes the visible channel's colour
overlay. That tint is baked into the generated pixels and tinted again by the
overlay on display. The plug-in should resolve the target to the topmost
visible layer (or refuse with a message) when the active drawable is a channel,
and read context from layers only.

### D. img-text-layer (FAIL; artifacts 1, content 1)

Seen: black blocky shapes that continue the strokes of "SALE": horizontal bars
and blocks, which is text garbage. The "E" outside the selection is intact.

Hypothesis: the high-contrast black glyph strokes in the unmasked context
dominate SD 1.5 at denoise 1.0, and the mask grow (16 px) cuts through letters,
leaving stroke stubs the model extends. Possibly the text layer is also the
source drawable, so its transparent-plus-black content is sent as context
(same alpha issue as B). Check which drawable is sampled for a text layer and
whether its alpha is flattened to black.

### E. sel-layer-offset, sel-layer-in-group, img-rotated-layer (FAIL; seams 2, color 2, blur 2)

Seen: the selection sits on a crisp, saturated mosaic layer. The generated area
is a desaturated, muddy, softened version of the mosaic: an obvious rectangle
in all three. Layer alignment is correct (no offset or group error).

Hypothesis: the blurred pre-fill turns the fine mosaic into a grey average.
SD 1.5 at about 1x working scale cannot rebuild 8 px colour tiles, and the
colour-match step pulls the region toward the averaged colour. Fine
high-frequency texture is the worst case for blur pre-fill. Try a smaller blur,
or only pre-fill the inner core of the mask.

### F. sel-huge-85pct (FAIL; artifacts 2, content 1)

Seen: no brick. The grass checker grows into a city-skyline silhouette with
cartoon clouds, and a faint 4% border ring is visible.

Hypothesis: with 85% masked, the model has only a thin border of context and
hallucinates. The prompt is ignored for the same reason as in A. For very large
selections the plug-in could warn, or fall back to text-to-image plus blending.

### G. mode-seed-random (FAIL; artifacts 2, content 1)

Seen: both random seeds give hard-edged black shapes (a slab, a house
silhouette) in place of the dark box, with no brick. Seed variation itself
works.

Hypothesis: the same SD 1.5 behaviour as A. Seed 1234 happens to give brick,
other seeds keep the dark box's tone and turn it into a silhouette. This shows
that mode-fill's success is seed luck rather than a reliable result.

### H. sel-quickmask-painted (FAIL; artifacts 2, content 1)

Seen: the dark box gains a step/notch outline and vertical streaks, and a grey
haze smear appears in the sky above. No brick.

Hypothesis: same as A, plus the soft painted mask makes the model blend the box
edge into a new shape. The smear in the sky follows the soft painted falloff,
so the mask's partial-alpha zone is regenerated at partial strength.

### I. img-indexed (FAIL, harness)

The report shows base_type 0 (RGB). The image was never converted to indexed,
so the plug-in's indexed-mode error path was not exercised. The output is
identical to mode-fill. Fix in tests/gimp_batch_matrix.py (the "base: indexed"
setup is not applied). This is not a plug-in defect.

### Scores of 2 or lower in passing cases

- sel-whole-image, color 2: the brick wall is mint/teal, not red. Hypothesis:
  the colour-match step uses the original image statistics (sky blue plus grass
  green) even though nothing unmasked is left to match. Colour match should be
  skipped when the selection covers the whole image or the unmasked ring is
  empty.
- mode-expand-all, artifacts 2: a spurious dark hut-shaped object appears at
  the right horizon with a smeared vertical left edge. Hypothesis: the model
  copies the dark box from the context into the new border. It could be
  suppressed with a negative prompt for expand, or by giving the border its own
  prompt.

### Systemic note (not a FAIL by itself)

Almost every SD 1.5 and SDXL fill shows a faint pale rectangle in the sky that
matches the grown plus feathered mask band (grow 16 px, feather 16 px). It is
clearly visible in mode-tier-juggernaut and mode-tier-sdxl-fooocus. The band is
regenerated slightly lighter than the original sky. Hypothesis: colour matching
is computed over the whole crop rather than over the unmasked ring, or the VAE
round trip lifts flat gradients; blending the band back toward the original
with a narrower feather, or colour-matching only on the ring just outside the
selection, should remove it.

The report check new_area_not_flat failed on mode-expand-top, but the visual
result is correct (a flat sky is expected). That check should be relaxed for
sky-like content; it is a false positive, not a plug-in fault.

## Re-score needed

none (no report.json is newer than the start of the scoring pass, 2026-10-09T00:43:43)

## Not yet scored

none

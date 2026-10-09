# Quality ledger, overnight 2026-10-09

Visual scoring of every evidence case that has a report.json. The rob-* folders
belong to the robustness lane and are skipped. sd15-prompt-ablation is an
analysis folder: it was read for the model-limitation section and is not scored.
Each case was judged from before.png, after.png and the crops, plus a
histogram-equalized copy of the after crop to show faint tonal steps. Where
after.png was pixel-identical to mode-fill (checked numerically, max diff 3/255
or less) the mode-fill scores are reused. This pass re-scores the evidence from
the 01:21 full run and the 01:37 partial re-run, both made after the plug-in
fixes.

Scale, 1 to 5 (5 best):

- 5: no visible problem, even in the equalized view
- 4: only visible in the equalized view or on close inspection
- 3: visible at normal view if you look for it
- 2: obvious at normal view
- 1: severe, or the requested content is absent

Columns: seams (boundary between generated and original), color (tonal shift of
the generated area), blur (generated area softer or flatter than its
surroundings), artifacts (blobs, duplicated edges, ghosts, text garbage), mask
edge (feathered transition, halo), content (requested content present; for
removal, object gone and background continues). "-" means not applicable
(error cases, plain txt2img).

Verdicts: PASS = good result; PASS-WITH-NOTES = usable but with a visible flaw
or partial content; FAIL = requested content missing, wrong, or damaging
artifacts. The test scene is synthetic (sky gradient, checker grass, dark box,
sun), so "red brick wall" only needs to read as brick. A flat red or brown
block without any brick pattern does not count as brick.

Error cases (sel-none, img-indexed, err-model-missing) are scored on the
message: plain words, a next step, and the image left untouched.

Harness quirks taken into account: the driver's composites include visible
channel overlays, so sel-channel-active is judged on the generated content,
not the pink tint. In img-alpha-transparent the transparent hole is drawn black
in before.png; a flat fill over it is acceptable as long as it is not black.

Selection respect: every fill case reports outside_max_abs_diff = 0 outside the
grown mask. No case showed changes outside the selection, wrong layer offsets,
hidden-layer leaks or aspect errors. The three error cases left the composite
pixel-identical (max diff 0) and added no layer. This is not repeated per row.

## Before and after

At 00:51, before the fixes, 55 cases were scored: 5 PASS, 27 PASS-WITH-NOTES,
23 FAIL. This pass scores 64 cases (the 55 plus nine new ones: err-model-missing,
three *-quality cases and five extra seeds): **11 PASS, 31 PASS-WITH-NOTES,
22 FAIL**. On the same 55 cases as before, the counts are 10 PASS,
28 PASS-WITH-NOTES, 17 FAIL. Of the nine new cases, one passes
(err-model-missing), three are PASS-WITH-NOTES (the quality tier at positions
where SD 1.5 fails) and five fail (sel-tiny-20px-quality and four SD 1.5 seed
repeats at flat-sky positions).

Fixed since 00:51: img-indexed (the image is now really indexed and the error
path works), sel-channel-active (no tint baked in), img-alpha-transparent (no
black block), img-text-layer (brick instead of text garbage), sel-whole-image
(red brick, no teal shift), sel-huge-85pct (brick wall, no skyline
hallucination). sel-quickmask-painted, sel-corner-bottomright, sel-edge-left,
mode-seed-random, prompt-quotes-backslashes and prompt-unicode-emoji now show
prompt-related content. The pale halo around the SDXL-tier fills is gone.

New or worse since 00:51: sel-feathered (was a weak red wall, now no content),
img-3000 and img-6000 (were red blocks with windows, now flat untextured
terracotta blocks), sel-edge-bottom (was clean grass, now a flat maroon blob)
and img-aspect-wide (was unchanged, now a dark slab growing into the sky).
Several cases now pass the report's content_changed check only because the
dark box was removed (img-1024, img-256, img-aspect-wide, sel-feathered). They
contain no brick, so they are FAIL here even though report.json says pass.

| case | model | report time | status (report / plug-in) | seams | color | blur | artifacts | mask edge | content | verdict | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| err-model-missing | flux1-fill-dev (not installed) | 2026-10-09T01:32:32 | pass / execution-error | - | - | - | - | - | - | PASS | Error case. Message names the missing model and the next step (Filters > AI > Generative Fill Settings > Models, press Download); no layer added, composite unchanged. The model label carries an internal detail "(first-party safetensors, fp8 at load time)" that is noise for a user. The log has a full traceback for this expected error. |
| img-1024 | sd15-inpainting | 2026-10-09T01:39:16 | pass / success | 3 | 4 | 4 | 3 | 3 | 1 | FAIL | Box removed and sky/grass continued, but no brick; a small green-grey stub stands on the horizon; pale rectangle in the sky. The report passes only because the box was removed. Unchanged from 00:51. |
| img-16bit-int | sd15-inpainting | 2026-10-09T01:25:30 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Matches mode-fill (max diff 3/255); 16-bit integer precision handled. |
| img-256 | sd15-inpainting | 2026-10-09T01:24:19 | pass / success | 3 | 4 | 3 | 4 | 3 | 1 | FAIL | 256x256: box removed, no brick; soft pale box clearly visible in the sky. Unchanged from 00:51. |
| img-3000 | sd15-inpainting | 2026-10-09T01:24:34 | pass / success | 3 | 4 | 2 | 3 | 3 | 2 | FAIL | Flat terracotta rectangle with no brick, mortar or any texture (Laplacian var 3.4 inside); faint pale halo. Working size 768x648 at scale 0.50. Worse than 00:51 (it had windows then). |
| img-32bit-float | sd15-inpainting | 2026-10-09T01:25:38 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Matches mode-fill (max diff 3/255); float precision handled. |
| img-6000 | sd15-inpainting | 2026-10-09T01:24:45 | pass / success | 3 | 4 | 2 | 3 | 3 | 2 | FAIL | Same flat terracotta block as img-3000 (Laplacian var 0.43), scale 0.25, visible pale halo box. 11.6 s. Worse than 00:51. |
| img-alpha-transparent | sd15-inpainting | 2026-10-09T01:25:53 | pass / success | 3 | 3 | 4 | 3 | 3 | 4 | PASS-WITH-NOTES | Over the transparent hole the fill is a flat grey-green rounded block, not black (acceptable per the harness note). Over the dark box there is brick, with a flat grey-green strip on top. Fixed since 00:51. |
| img-aspect-tall | sd15-inpainting | 2026-10-09T01:39:23 | fail / success | 4 | 4 | 3 | 3 | 4 | 1 | FAIL | 256x4096: the selected part of the pole is reproduced, no brick (mean diff 4.7); faint striped ghosts beside it. |
| img-aspect-wide | sd15-inpainting | 2026-10-09T01:25:01 | pass / success | 3 | 3 | 4 | 2 | 3 | 1 | FAIL | 4096x256: the selection became a dark stepped slab that rises into the sky, with green fill in its middle; no brick. The report passes on mean diff 52.7. Worse than 00:51. |
| img-grayscale | sd15-inpainting | 2026-10-09T01:25:19 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Grey brick wall with clear courses; stays grayscale; faint halo box in the sky. |
| img-indexed | sd15-inpainting | 2026-10-09T01:25:28 | pass / execution-error | - | - | - | - | - | - | PASS | Error case, now really indexed (base_type 2). Plain message with the next step ("Convert it with Image > Mode > RGB (or Grayscale) and run the command again"); no layer added, composite unchanged. Fixed since 00:51. |
| img-linear | sd15-inpainting | 2026-10-09T01:25:46 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Matches mode-fill (max diff 3/255); no gamma shift. |
| img-multilayer-hidden | sd15-inpainting | 2026-10-09T01:26:16 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill; the hidden layer does not leak into the context. |
| img-rotated-layer | sd15-inpainting | 2026-10-09T01:26:08 | pass / success | 3 | 3 | 2 | 3 | 3 | 1 | FAIL | Inside the selection the crisp coloured mosaic becomes a softer, washed-out mosaic; a visible soft rectangle; no brick. Slightly less muddy than at 00:51. |
| img-text-layer | sd15-inpainting | 2026-10-09T01:26:01 | pass / success | 3 | 4 | 4 | 3 | 3 | 4 | PASS-WITH-NOTES | Dark red brick block where "SAL" was; the "E" outside the selection stays. Small black stubs on the block's left edge continue the cut glyph strokes. Fixed since 00:51 (text garbage gone). |
| img-unsaved-new | sd15-inpainting | 2026-10-09T01:26:29 | pass / success | 3 | 4 | 4 | 3 | 3 | 1 | FAIL | Four-box scene: the white box is shortened and sky continues; a faint red smudge at the brown box corner; no brick. |
| img-unsaved-new-quality | juggernaut-xl-v9 | 2026-10-09T01:31:40 | pass / success | 2 | 4 | 5 | 3 | 3 | 4 | PASS-WITH-NOTES | New case. Crisp red brick with mortar in the selection, but the white box is rebuilt as an L-shaped white slab beside it, and thin dark straight lines run along the selection's top edge and at the step: hard seams. |
| img-with-path | sd15-inpainting | 2026-10-09T01:26:36 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill; the vector path does not interfere. |
| mode-expand-all | sd15-inpainting | 2026-10-09T01:28:32 | pass / success | 3 | 4 | 4 | 2 | 3 | 4 | PASS-WITH-NOTES | Sky and grass continue on all sides, but the same spurious dark hut appears on the right horizon with a smeared left edge (as at 00:51). |
| mode-expand-bottom | sd15-inpainting | 2026-10-09T01:28:21 | pass / success | 4 | 4 | 4 | 4 | 4 | 5 | PASS | Grass continues into the new strip; slightly blotchy near the bottom edge, no seam at normal view. |
| mode-expand-left | sd15-inpainting | 2026-10-09T01:27:49 | pass / success | 3 | 4 | 4 | 4 | 3 | 5 | PASS-WITH-NOTES | Faint blotchy vertical band in the left sky at the old canvas edge. |
| mode-expand-right | sd15-inpainting | 2026-10-09T01:28:13 | pass / success | 3 | 3 | 4 | 3 | 3 | 5 | PASS-WITH-NOTES | New right strip of sky slightly lighter (faint vertical band) and a small dark wedge on the horizon at the right edge. |
| mode-expand-top | sd15-inpainting | 2026-10-09T01:28:02 | pass / success | 4 | 4 | 5 | 4 | 4 | 5 | PASS | Sky gradient continues cleanly; the report's flatness check no longer fails. |
| mode-fill | sd15-inpainting | 2026-10-09T01:39:31 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Baseline: brick wall in the sky half of the box, grass below; faint pale rectangle in the sky around the grown/feathered band and a faint dark ghost in the grass. Same as 00:51. |
| mode-remove | mat-places512 (Remove) | 2026-10-09T01:27:44 | pass / success | 3 | 4 | 3 | 3 | 3 | 4 | PASS-WITH-NOTES | Box gone, sky clean apart from a faint pale box and a thin dark smear on the horizon; under the old box the grass has blotchy strokes that break the checker. Same as 00:51. |
| mode-seed-fixed-repeat | sd15-inpainting | 2026-10-09T01:30:30 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Runs identical; image equals mode-fill. |
| mode-seed-random | sd15-inpainting | 2026-10-09T01:30:09 | pass / success | 3 | 3 | 4 | 4 | 3 | 3 | PASS-WITH-NOTES | Seeds differ: run 1 is a brick shed with a roof (good), run 2 is plain sky and grass. 1 of 2 runs has the content. Better than 00:51 (two black blobs). |
| mode-tier-juggernaut | juggernaut-xl-v9 | 2026-10-09T01:39:38 | pass / success | 4 | 4 | 5 | 4 | 4 | 5 | PASS | Crisp brick wall with a stone base course; the pale halo seen at 00:51 is gone (not visible even equalized). |
| mode-tier-mat | mat-places512 | 2026-10-09T01:30:05 | pass / success | 3 | 4 | 3 | 3 | 3 | 4 | PASS-WITH-NOTES | Same as mode-remove (MAT, 3.9 s), same blotchy grass. |
| mode-tier-sd15 | fast (sd15-inpainting) | 2026-10-09T01:29:09 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill. |
| mode-tier-sdxl-fooocus | quality (sdxl-base + Fooocus) | 2026-10-09T01:29:16 | pass / success | 4 | 4 | 5 | 4 | 4 | 5 | PASS | Brick wall with a pale coping and base; no halo, no shadow slab (both present at 00:51). |
| mode-txt2img-image | sd15-inpainting | 2026-10-09T01:28:51 | pass / success | - | - | 5 | 4 | - | 5 | PASS | New 680x512 image of a log cabin in a meadow; thin bright line on the right border. Source untouched. |
| mode-txt2img-layer | sd15-inpainting | 2026-10-09T01:28:44 | pass / success | - | - | 5 | 5 | - | 5 | PASS | Cabin photo exactly inside the selection, hard edge by design; nothing outside changed. |
| mode-variations-4 | sd15-inpainting | 2026-10-09T01:28:52 | pass / success | 3 | 3 | 4 | 3 | 3 | 3 | PASS-WITH-NOTES | Four masked variations, first visible. v1 and v3 are brick, v2 and v4 are plain sky/grass with a tiny blue speck on the right horizon. 2 of 4 have content (1 of 4 at 00:51). |
| prompt-empty | sd15-inpainting | 2026-10-09T01:26:44 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Box removed (continuation prompt); pale box visible in the sky. |
| prompt-negative-only | sd15-inpainting | 2026-10-09T01:27:22 | pass / success | 3 | 4 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Same as prompt-empty; nothing red or brick; pale box in the sky. |
| prompt-quotes-backslashes | sd15-inpainting | 2026-10-09T01:27:14 | pass / success | 3 | 4 | 5 | 3 | 3 | 4 | PASS-WITH-NOTES | A black road sign with arrows and a "6" on a post: the prompt is honoured and the string survives. A stray orange stick at the sign's lower right. |
| prompt-unicode-emoji | sd15-inpainting | 2026-10-09T01:27:06 | pass / success | 3 | 4 | 5 | 4 | 3 | 4 | PASS-WITH-NOTES | A bowl with a blossom branch (matches the cafe and flower prompt), crisp; no crash. Faint halo. |
| prompt-very-long | sd15-inpainting | 2026-10-09T01:26:55 | pass / success | 3 | 4 | 4 | 4 | 3 | 5 | PASS-WITH-NOTES | Weathered brick building with a slate roof; faint pale halo. |
| sel-channel-active | sd15-inpainting | 2026-10-09T01:24:12 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Generated region is the same brick wall as mode-fill; the pink/orange in the composite is the channel overlay, not baked in. Fixed since 00:51. |
| sel-corner-bottomright | sd15-inpainting | 2026-10-09T01:23:17 | pass / success | 4 | 4 | 5 | 4 | 4 | 5 | PASS | Brick pillar with a stone coping in the corner, crisp; only a faint bluish fringe on its left edge when equalized. |
| sel-corner-topleft | sd15-inpainting | 2026-10-09T01:39:01 | fail / success | 3 | 4 | 4 | 4 | 3 | 1 | FAIL | Sky continued, no brick; a slightly darker blue rectangle is visible in the corner at normal view. |
| sel-corner-topleft-quality | juggernaut-xl-v9 | 2026-10-09T01:31:23 | pass / success | 4 | 4 | 5 | 4 | 3 | 5 | PASS-WITH-NOTES | New case. Crisp red brick; soft dark fringe along the bottom edge. |
| sel-edge-bottom | sd15-inpainting | 2026-10-09T01:38:54 | pass / success | 3 | 3 | 2 | 2 | 2 | 2 | FAIL | A flat maroon house-shaped block with no brick pattern; smeared left edge and green smears in the mask band. Worse than 00:51. |
| sel-edge-left | sd15-inpainting | 2026-10-09T01:38:32 | pass / success | 3 | 4 | 4 | 4 | 3 | 5 | PASS-WITH-NOTES | Brick wall against the left edge; faint pale band above it and a faint ghost in the grass. Fixed since 00:51. |
| sel-edge-left-seed7 | sd15-inpainting | 2026-10-09T01:40:02 | fail / success | 3 | 4 | 4 | 3 | 3 | 1 | FAIL | New case. Sky continued, no brick; pale rectangle and a small blue fleck at the left edge. |
| sel-edge-left-seed99 | sd15-inpainting | 2026-10-09T01:40:12 | fail / success | 3 | 4 | 4 | 3 | 3 | 1 | FAIL | New case. Same as seed 7: sky continued, pale rectangle, small blue fleck at the lower left. |
| sel-edge-right | sd15-inpainting | 2026-10-09T01:38:47 | fail / success | 3 | 4 | 4 | 4 | 3 | 1 | FAIL | Sky and grass continued, no brick; faint pale box. |
| sel-edge-top | sd15-inpainting | 2026-10-09T01:38:40 | fail / success | 2 | 3 | 4 | 4 | 3 | 1 | FAIL | Sky continued, no brick; a darker blue rectangle is clearly visible at the top edge (more visible than at 00:51). |
| sel-edge-top-quality | juggernaut-xl-v9 | 2026-10-09T01:31:05 | pass / success | 4 | 4 | 5 | 4 | 3 | 5 | PASS-WITH-NOTES | New case. Crisp brick panel; soft dark fringe along the bottom edge. |
| sel-feathered | sd15-inpainting | 2026-10-09T01:23:33 | pass / success | 3 | 4 | 4 | 4 | 3 | 1 | FAIL | 20 px feather: box removed, sky and grass continued, no brick; pale box in the sky. The report passes on mean diff 74 (box removal). Worse than 00:51 (weak red wall then). |
| sel-huge-85pct | sd15-inpainting | 2026-10-09T01:38:24 | pass / success | 3 | 3 | 4 | 3 | 3 | 5 | PASS-WITH-NOTES | Large brick wall with grass tufts at its foot; the sun was inside the selection and is gone (correct). The regenerated grass below is greyer than the border grass and the 4% border ring is faintly visible. Fixed since 00:51. |
| sel-layer-in-group | sd15-inpainting | 2026-10-09T01:23:57 | pass / success | 2 | 2 | 3 | 3 | 3 | 1 | FAIL | Layer offsets correct, but the selected part of the vivid mosaic becomes a washed-out grey-beige mosaic, an obvious rectangle; no brick. |
| sel-layer-mask-active | sd15-inpainting | 2026-10-09T01:24:05 | pass / success | 3 | 3 | 4 | 4 | 3 | 4 | PASS-WITH-NOTES | Pixel-identical to mode-fill; an active layer mask does not redirect the fill. |
| sel-layer-offset | sd15-inpainting | 2026-10-09T01:23:49 | pass / success | 2 | 2 | 3 | 3 | 3 | 1 | FAIL | Same as sel-layer-in-group: aligned correctly, washed-out mosaic rectangle, no brick. |
| sel-multi-disjoint | sd15-inpainting | 2026-10-09T01:39:07 | fail / success | 3 | 4 | 4 | 4 | 3 | 1 | FAIL | Both rectangles continued as sky/grass, faint ghost boxes, no brick (mean diff 1.8). |
| sel-none | sd15-inpainting | 2026-10-09T01:21:36 | pass / execution-error | - | - | - | - | - | - | PASS | Error case. Plain message with next steps (Rectangle or Free Select, or Select > All); no layer added, composite and selection unchanged. The log carries a traceback for this user error (noise only). |
| sel-quickmask-painted | sd15-inpainting | 2026-10-09T01:23:41 | pass / success | 3 | 4 | 4 | 3 | 3 | 4 | PASS-WITH-NOTES | Brick in the painted part of the box (stepped outline, the unpainted strip stays dark); faint grey haze in the sky following the soft painted falloff. Fixed since 00:51. |
| sel-tiny-20px | sd15-inpainting | 2026-10-09T01:37:43 | fail / success | 4 | 5 | 4 | 4 | 4 | 1 | FAIL | 20 px selection inside the flat dark box: practically unchanged (mean diff 1.5); only a faint tonal square in the equalized view. |
| sel-tiny-20px-quality | juggernaut-xl-v9 | 2026-10-09T01:30:44 | pass / success | 4 | 4 | 3 | 3 | 4 | 2 | FAIL | New case. A few grey/white speckles inside the dark box, visible as a small dot at normal view; texture but no brick. The quality tier does not rescue a 20 px selection. |
| sel-tiny-20px-seed7 | sd15-inpainting | 2026-10-09T01:32:12 | fail / success | 4 | 5 | 4 | 4 | 4 | 1 | FAIL | New case. Unchanged (mean diff 2.4). |
| sel-tiny-20px-seed99 | sd15-inpainting | 2026-10-09T01:32:26 | fail / success | 4 | 5 | 4 | 4 | 4 | 1 | FAIL | New case. Unchanged (mean diff 1.9); faint darker shape only in the equalized view. |
| sel-whole-image | sd15-inpainting | 2026-10-09T01:21:37 | pass / success | 5 | 5 | 5 | 4 | 5 | 5 | PASS | Full-frame red brick wall over a pavement, sharp, natural colour. Fixed since 00:51 (was mint/teal). |

## Failures and concerns

Every FAIL and every score of 2 or lower, with what was seen and the likely
cause on the plug-in side. "Hypothesis" means it was not verified in code.

### A. Flat, untextured objects in place of brick (sel-edge-bottom, img-3000, img-6000)

Seen: the model paints a solid-coloured shape in roughly brick colour
(terracotta block, maroon house shape) with no brick, mortar or any texture.
Laplacian variance inside is 0.4 to 27, against 1160 for the mode-fill brick.
In sel-edge-bottom the left edge is smeared and green smears sit in the mask
band. All three were better at 00:51.

Hypothesis: the new neutral grey pre-fill gives SD 1.5 a flat, mid-tone
region. The model keeps it flat and only shifts its hue toward "red", and
colour match (color_match=1.0) then pulls the region toward the context
statistics, which flattens it further. For img-3000 and img-6000 the working
size is 768x648, above SD 1.5's native 512, at scale 0.50 and 0.25, so the mask
grow and feather become 8 and 4 px. Suggested direction: keep the working size
at about 512 on the long side for SD 1.5, and test the neutral pre-fill with
colour match reduced or skipped for prompted fills (the ablation shows that
colour match removes about half of the change).

### B. SD 1.5 ignores the prompt at flat-sky positions (14 FAILs)

Cases: img-1024, img-256, img-aspect-tall, img-unsaved-new, sel-corner-topleft,
sel-edge-right, sel-edge-top, sel-edge-left-seed7, sel-edge-left-seed99,
sel-feathered, sel-multi-disjoint, sel-tiny-20px, sel-tiny-20px-seed7,
sel-tiny-20px-seed99 (content 1).

Seen: the masked area becomes a continuation of the sky, grass or the box, with
no brick. The same position gives brick with one seed and sky with others
(sel-edge-left: seed 1234 brick, seeds 7 and 99 sky). In img-1024, img-256 and
sel-feathered the dark box is removed, so report.json passes on the mean
difference, but no requested content appears. The ablation README calls
img-256 and img-1024 passes; visually they are not.

Plug-in side: the mask band leaves a visible rectangle in several of these
(sel-edge-top seams 2, sel-corner-topleft 3): the sky inside the band is
regenerated a little darker or lighter than the original. See the systemic
note. The content failure itself is the model's behaviour (see Model
limitations): sel-edge-top, sel-corner-topleft and img-unsaved-new give brick
with the quality tier. sel-feathered is the exception: it had content at
00:51 and is listed again under plug-in defects.

### C. Fine texture is washed out (sel-layer-offset, sel-layer-in-group, img-rotated-layer)

Seen: the selection sits on a crisp, saturated 8 px mosaic layer. The generated
area is a desaturated, softer version of the mosaic, an obvious rectangle
(seams 2, color 2 in two cases). Layer offsets and group handling are correct.
Slightly better than at 00:51, but still damaging: the result is worse than
the input and contains no brick.

Hypothesis: the context is almost entirely mosaic, so colour match and the
pre-fill average the tiles toward grey. SD 1.5 at scale 1.0 cannot rebuild
8 px tiles and does not override them with the prompt. Try colour match only
on a ring just outside the selection, and skip it when the ring has high
variance.

### D. img-aspect-wide (FAIL; artifacts 2, content 1)

Seen: on the 4096x256 strip the dark bar inside the selection becomes a dark
stepped slab that grows up into the sky, with a green block in its middle. No
brick.

Hypothesis: the 0.5x context margin on a 410x154 selection gives a 768x240
working image. That is too short for SD 1.5 to place a wall, so it extends the
strongest context feature (the dark bar). A minimum working height (pad the
context vertically to at least 384 to 512 px) would help.

### E. img-unsaved-new-quality (PASS-WITH-NOTES, seams 2)

Seen: thin dark straight lines along the top of the selection and at the step
where the white box meets the brick. Juggernaut keeps the hard edge of the
rectangle and draws a roof-line there.

Hypothesis: the mask edge for this tier is too hard. In sel-edge-top-quality
and sel-corner-topleft-quality there is a similar soft dark fringe on the
bottom edge. A few more pixels of feather for the SDXL template, or blending
the outer 8 px back to the original, should remove it.

### F. sel-tiny-20px-quality (FAIL; content 2)

Seen: a few grey/white speckles in the dark box; no brick. A 20 px selection
is upscaled 2.67x into a 192 px context, so even SDXL has only a 53 px working
square to draw in, too small for recognisable brick. For selections under about 64 px the plug-in
could warn that the area is too small for new content, or enlarge the working
crop further.

### Scores of 2 or lower in passing cases

- mode-expand-all, artifacts 2: the same dark hut on the right horizon as at
  00:51, with a smeared left edge. The model copies the dark box from the
  context into the new border. A negative prompt for expand, or a border-only
  prompt, could suppress it.
- img-unsaved-new-quality, seams 2: see E.

### Systemic note (not a FAIL by itself)

Most SD 1.5 fills still show a faint pale or dark rectangle that matches the
grown plus feathered mask band (grow 16 px, feather 16 to 24 px). It is visible
at normal view in mode-fill, prompt-empty, img-256, img-6000, sel-edge-top and
sel-corner-topleft. The SDXL tiers (mode-tier-juggernaut,
mode-tier-sdxl-fooocus) no longer show it. Hypothesis: the SD 1.5 VAE round
trip plus colour matching lifts or darkens flat gradients. Blending the band
back toward the original, or colour matching on the ring outside the selection
only, should remove it.

## Model limitations

What the SD 1.5 inpainting model does by itself, independent of the plug-in:

- On flat synthetic regions (plain sky, a flat dark box) it continues the
  context and ignores the prompt. The ablation (sd15-prompt-ablation/README.md)
  re-ran the exact crop and mask the plug-in sent for sel-edge-top against
  ComfyUI with each graph step removed: with or without pre-fill, colour match,
  DifferentialDiffusion or noise_mask, the mean change inside the mask stays
  between 0.8 and 2.8, and "a red hot air balloon" gives the same sky as
  "red brick wall". No graph step causes it.
- The result flips with the seed and with small changes in crop size or
  position. That is why mode-fill (seed 1234) gives brick, while the same
  position at other seeds, or nearby positions, give sky.
- The Quality tier (Juggernaut XL) produces brick at the same positions where
  SD 1.5 fails: sel-edge-top-quality, sel-corner-topleft-quality,
  img-unsaved-new-quality, plus mode-tier-juggernaut and
  mode-tier-sdxl-fooocus. The exception is a 20 px selection
  (sel-tiny-20px-quality), which is too small for any model.

So these FAILs are counted as model behaviour, not plug-in defects:
img-1024, img-256, img-aspect-tall, img-unsaved-new, sel-corner-topleft,
sel-edge-right, sel-edge-top, sel-edge-left-seed7, sel-edge-left-seed99,
sel-multi-disjoint, sel-tiny-20px, sel-tiny-20px-seed7, sel-tiny-20px-seed99,
sel-tiny-20px-quality. The plug-in could still pick SDXL for Fill by default,
or warn when SD 1.5 is used on a flat region.

Plug-in defects or plug-in-influenced results (fixable on the plug-in side):

- Flat, untextured blocks (A: sel-edge-bottom, img-3000, img-6000): the
  neutral pre-fill, colour match and an over-large working size for SD 1.5.
  These cases got worse with the fixes.
- sel-feathered lost its content after the pre-fill and margin change. The
  feathered mask probably gives the model too little hard-masked area to place
  an object, but it is a regression and should be checked.
- Washed-out texture (C: sel-layer-offset, sel-layer-in-group,
  img-rotated-layer): colour match and pre-fill averaging fine detail.
- img-aspect-wide: working crop too short for SD 1.5 (D).
- Mask-band halo on SD 1.5 fills, and the hard edge or dark fringe on the
  SDXL tier (systemic note, E).
- The report's content_changed_in_selection check passes when the dark box is
  merely removed. It cannot tell "requested content added" from "background
  continued", so report.json overstates passes (img-1024, img-256,
  img-aspect-wide, sel-feathered). This is a harness issue, not a plug-in
  issue.

## Re-score needed

none (every report.json was written at or before 2026-10-09T01:40:12, before this pass)

## Not yet scored

none

## Real photos

Twenty-eight photo-* cases on six Wikimedia Commons photographs (sources,
selections and prompts in photos-README.md, spec in photo-spec.json), scored
from after.jpg and region-1to1.jpg at 1:1, on the same 1-5 scale and verdicts
as above. Seed 1234, 1 variation, 20 steps. Remove = MAT Places512 (the
Remove checkbox always uses the installed LaMa/MAT model); remove-quality =
Juggernaut XL v9 with an empty prompt; replace = Juggernaut XL v9 (Quality);
replace-fast = SD 1.5 inpainting (Fast); extend = Juggernaut XL v9.

Code state: the remove, remove-quality, replace and extend rows were run
after the fixes below (03:19 to 03:32); the replace-fast rows are from the
first run (03:00), whose SD 1.5 fill path is identical to the final code. A/B
evidence for every parameter change is in photo-ab/README.md.

Selection respect: every fill case reports outside_max_abs_diff = 0 outside
the grown mask; no layer, offset or selection-restore problem was seen. The
report.json "pass" flags (26 of 28) only check mechanics; the verdicts below
are visual.

| Case | Seams | Color | Blur | Artifacts | Mask edge | Content | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|
| photo-face-remove | 4 | 4 | 3 | 3 | 4 | 4 | PASS-WITH-NOTES | Patch gone, weave and the flap fold continue. Two small dark stains (left edge, lower middle). Inside detail ratio 0.08 of the surroundings (0.02 before the MAT fix). |
| photo-fabric-remove | 4 | 4 | 3 | 3 | 4 | 4 | PASS-WITH-NOTES | Red fibre cluster removed; one radial cluster of white fibres converges in the middle; slightly glassy. |
| photo-landscape-remove | 4 | 4 | 3 | 4 | 4 | 4 | PASS-WITH-NOTES | Barn gone, horizon and hedge continue. A pale patch remains behind the tree crowns at the right edge of the selection. |
| photo-architecture-remove | 3 | 4 | 3 | 2 | 3 | 2 | FAIL | Air conditioner replaced by a pile of window-frame and box fragments. MAT cannot reconstruct the window structure behind it. |
| photo-text-remove | 5 | 5 | 4 | 5 | 5 | 5 | PASS | "AUX" removed, clean yellow sign surface (two dark blobs before the MAT fix). |
| photo-product-remove | 3 | 5 | 4 | 2 | 4 | 3 | FAIL | Foot ring and its shadow removed, but the selection crossed the cup and its bottom contour now has a step. |
| photo-landscape-remove-quality | 4 | 4 | 4 | 2 | 4 | 1 | FAIL | Empty-prompt removal with Juggernaut invents a green hill and a smaller shed where the barn was. Model behaviour; MAT does this case well. |
| photo-architecture-remove-quality | 4 | 4 | 4 | 3 | 4 | 4 | PASS-WITH-NOTES | Window, railings and frames continue where the unit was; a stray yellow strap. Better than MAT here. |
| photo-face-replace | 5 | 4 | 5 | 5 | 5 | 5 | PASS | Gold aviators fitted to the face; skin under the bridge slightly smoother than the rest. |
| photo-fabric-replace | 3 | 4 | 3 | 4 | 4 | 5 | PASS-WITH-NOTES | Red scarf lying on the tweed; the fibres left of it are softer than the surrounding weave (generated at 0.57x). Before the pre-fill fix: a framed photograph of a woman with a scarf (FAIL). |
| photo-landscape-replace | 5 | 5 | 4 | 5 | 5 | 5 | PASS | Balloon in the evening sky, no rectangle. Before the pre-fill fix: balloon on its own blue-sky rectangle (FAIL). |
| photo-architecture-replace | 2 | 2 | 2 | 4 | 2 | 1 | FAIL | No window: a flat yellow-beige rectangle with visible top and bottom edges on the pink wall. With the old neutral pre-fill a flat green pane in a frame filled the box (content 3). Open issue, see below. |
| photo-text-replace | 4 | 4 | 4 | 5 | 4 | 1 | FAIL | Word removed cleanly, no arrow drawn. The old neutral pre-fill gave a blue block with an arrow-like end filling the box. |
| photo-product-replace | 5 | 5 | 5 | 5 | 5 | 5 | PASS | Lemon slice on the saucer with a soft contact shadow. |
| photo-face-replace-fast | 5 | 4 | 4 | 4 | 5 | 5 | PASS | Sunglasses; the eyes show through the lenses as a reflection, slightly odd but plausible. No mask-band rectangle. |
| photo-fabric-replace-fast | 2 | 3 | 2 | 3 | 3 | 1 | FAIL | No scarf. A softer, lighter rectangle of fibres (concern 3): generated at 0.57x and upscaled; colour match off gives the same result (photo-ab section 3). |
| photo-landscape-replace-fast | 5 | 5 | 4 | 4 | 5 | 5 | PASS | Balloon plus a small second balloon; basket lettering garbled. |
| photo-architecture-replace-fast | 4 | 4 | 4 | 2 | 4 | 1 | FAIL | No window; cables removed and a dark open shutter shape drawn at the edge. Model ignores the prompt. |
| photo-text-replace-fast | 5 | 5 | 4 | 2 | 5 | 1 | FAIL | Word replaced by garbage letters "AEESREN", no arrow. Model behaviour. |
| photo-product-replace-fast | 5 | 5 | 4 | 4 | 5 | 5 | PASS | Whole lemon plus a slice on the saucer. |
| photo-face-extend | 4 | 4 | 4 | 5 | 4 | 4 | PASS-WITH-NOTES | Grey backdrop continues; faint vertical tone step where the new strip starts. (Strip context before the minimum aspect: a black panel; whole-canvas context: a dark band at the far edge.) |
| photo-fabric-extend | 2 | 4 | 2 | 3 | 3 | 3 | FAIL | Weave continues but coarser and blurred, with a visible seam at the old edge (seam metric 33.7). |
| photo-landscape-extend | 4 | 4 | 3 | 3 | 4 | 4 | PASS-WITH-NOTES | Trees and meadow continue; one bright fern-like branch hangs into the frame. Before the expand fix: a flat lime bar (FAIL). |
| photo-architecture-extend | 4 | 4 | 3 | 4 | 4 | 5 | PASS-WITH-NOTES | Facade continues with windows and curtains, softer than the original. Before: a blurred yellow block (FAIL). |
| photo-text-extend | 4 | 4 | 3 | 4 | 4 | 4 | PASS-WITH-NOTES | Sign frame continues, a blurred path and grass beyond it. Before: a flat pale field. |
| photo-product-extend | 5 | 5 | 5 | 5 | 5 | 5 | PASS | White background continues. |
| photo-landscape-extend-all | 1 | 2 | 1 | 1 | 2 | 1 | FAIL | Quality tier, all four sides: the border is a smeared radial blur of green and sky, like a vignette frame; nothing generated. Unchanged by the fixes (all-sides still uses the whole canvas). |
| photo-landscape-extend-all-fast | 4 | 4 | 3 | 4 | 4 | 5 | PASS-WITH-NOTES | Same expansion with SD 1.5: birch, meadow and sky extended on all sides; soft (0.42x working scale), bottom-left corner darker. |

Totals: 8 PASS, 10 PASS-WITH-NOTES, 10 FAIL.

### Known concerns from the synthetic matrix, checked on photos

1. Pale or dark rectangle at the mask edge in SD 1.5 fills: not seen on the
   photos as a tonal band (face, landscape, product fills blend). The fabric
   fill shows a softer rectangle, which is resolution (0.57x working scale on
   a 672x587 selection), not the mask band.
2. Hard dark seam lines on the Quality tier: not seen. The Quality tier had a
   different and worse defect instead: with the neutral grey pre-fill,
   Juggernaut painted a separate framed picture into the selection (fabric,
   landscape). Fixed: SDXL prompted fills use the border pre-fill
   (geometry.prefill_for); a soft-edged neutral pre-fill did not help.
3. Flat tinted blocks: seen in photo-fabric-replace-fast (soft block, SD 1.5)
   and photo-architecture-replace (flat yellow rectangle, Quality tier with
   the border pre-fill). Colour match is not the cause (A/B with colour match
   off: identical at normal view), so the default stays at 1.0.
4. err-model-missing showing "FLUX.1 Fill [dev] (first-party safetensors, fp8
   at load time)": fixed in app.py (workflow.model_display_name, used for every
   ModelMissing message and the progress title); the message now reads
   "'FLUX.1 Fill [dev]' is not downloaded yet ...". Unit-tested; the GIMP
   error case was not re-run in this pass.

### Plug-in defects found and fixed in this pass

- MAT removal was soft and left ghosts: the removal node always resamples to
  512 px, so a 1024 px working size was thrown away with nearest-neighbour
  sampling. geometry.INPAINT_MODEL max_side 512, geometry.fill_padding 0.5x
  margin for prompt-free models (photo-ab section 1).
- Quality-tier framed-picture fills: geometry.prefill_for (section 2).
- Generative Expand painted flat bars: a one-sided strip used the whole canvas
  as context. geometry.plan_expand and _strip_context (section 4).
- Every expansion failed with "LoadImage: End of file" once the context was a
  strip: ComfyUI decodes uploads with PyAV, whose format probe took the strip
  mask for MPEG-TS. workflow.probe_safe_png, applied to both uploads in
  backends/comfy.py (section 4). Any upload whose compressed bytes look
  periodic could hit this, so it also protects fills.

### Open issues (not fixed)

- Quality tier ignores some prompts with the border pre-fill
  (photo-architecture-replace, photo-text-replace): nothing is added, and on
  the wall the barely changed pre-fill shows as a tinted flat rectangle. The
  old neutral pre-fill drew something in these two but framed pictures in
  others. Next step: a per-selection choice (for example neutral only for
  small selections or low-variance surroundings), not tried.
- All-sides expansion on the Quality tier produces a blurred vignette instead
  of content; SD 1.5 does it well. Likely the same "picture in a frame"
  reading of a rectangle surrounded by a border; expanding one side at a time
  would avoid it.
- Large fills and expansions on fine texture (fabric) come back softer than
  the 1:1 surroundings because they are generated at 0.5 to 0.8x.
- Empty-prompt removal with a generation model invents objects
  (photo-landscape-remove-quality); MAT is the better default, which is what
  the Remove checkbox already uses.
- MAT cannot rebuild structured backgrounds (photo-architecture-remove).

## SD 1.5 and expand A/B

Details, grids and the variant definitions: `sd15-ab/README.md`. Scores are
content / seams / blur (1 to 5), seed 1234.

| Case | A (committed) | B (blur pre-fill, CM 0.5) | C (CM off) | D (640 px cap) |
|---|---|---|---|---|
| sel-edge-bottom | 2/3/2 | 1/4/3 | 2/3/2 | 2/3/2 (unchanged) |
| img-3000 | 2/3/2 | 2/3/2 | 2/3/2 | 4/3/4 |
| sel-feathered | 1/3/3 | 4/2/4 | 1/3/3 | 1/3/3 (unchanged) |
| sel-layer-offset | 1/4/2 | 1/4/2 | 1/4/2 | 1/4/2 (unchanged) |
| sel-huge-85pct (guard) | 5/4/4 | 1/3/3 | 5/4/4 | 4/3/4 |

Kept D (`geometry.fill_profile`). Final run with the change:

| Case | Content | Seams | Blur | Verdict | Notes |
|---|---|---|---|---|---|
| img-3000 | 4 | 3 | 4 | PASS-WITH-NOTES | Brick courses and mortar (was a flat block); faint lighter rectangle in the mask band. |
| img-6000 | 4 | 4 | 4 | PASS-WITH-NOTES | Brick wall with coping at 640x536 (was a flat block). |
| sel-huge-85pct | 4 | 3 | 4 | PASS-WITH-NOTES | Brick wall; the top of the selection is a darker sky panel with a visible edge (was brick over the whole selection). |
| sel-edge-bottom, sel-feathered, sel-layer-offset | - | - | - | unchanged | Contexts below 640 px; same parameters as before, same failures (A column). |
| photo-landscape-extend-all | 4 | 2 | 4 | FAIL (seams) | Now four one-sided passes: meadow, trees, birch foliage and sky generated on all sides (was a blurred vignette, content 1). The left strip is a separate picture with a different horizon and a hard vertical seam at the old edge; right, top and bottom blend. Harness checks new_layer_or_group and old_pixels_outside_mask_unchanged fail by construction (four layers; they test one layer's mask); measured instead: old pixels farther than 64 px from the old edge are unchanged (0 changed). |

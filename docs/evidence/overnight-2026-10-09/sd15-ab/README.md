# SD 1.5 large-selection A/B and all-sides expand (2026-10-09)

Prompt "red brick wall", negative "blurry", seed 1234, sd15-inpainting, one run
per case and variant, cases from `C:\AI\overnight-scratch\runs\matrix-spec.json`.
Variants were switched with a temporary environment hook in `App.generative_fill`
(removed afterwards); each applied only to prompted SD 1.5 fills at strength 1.0.

| Variant | Change against the committed state (39f3dcc) |
|---|---|
| A | none: neutral grey pre-fill, colour match 1.0, SD 1.5 max side 768 |
| B | blurred (navier-stokes) pre-fill and colour match 0.5 (hypotheses a + b) |
| C | neutral pre-fill, colour match off (hypothesis b alone) |
| D | SD 1.5 working size capped at 640 px on the long side (hypothesis c) |

Each `grid-<case>.png` shows A, B, C, D left to right (after-crop). Scores are
content / seams / blur, 1 to 5, from looking at the images.

| Case | A | B | C | D |
|---|---|---|---|---|
| sel-edge-bottom | 2/3/2 flat maroon house shape | 1/4/3 grass only, no object | 2/3/2 same as A | 2/3/2 same as A (working size 528x512 unchanged) |
| img-3000 | 2/3/2 flat terracotta block | 2/3/2 darker flat block | 2/3/2 same as A | 4/3/4 brick courses and mortar, faint lighter rectangle around |
| sel-feathered | 1/3/3 nothing, faint rectangle | 4/2/4 brick block, visible halo rectangle | 1/3/3 same as A | 1/3/3 same as A (600x544 unchanged) |
| sel-layer-offset | 1/4/2 checker pattern continued | 1/4/2 same | 1/4/2 same | 1/4/2 same (616x536 unchanged) |
| sel-huge-85pct (guard) | 5/4/4 brick wall | 1/3/3 no brick, green silhouettes | 5/4/4 same as A | 4/3/4 brick wall, darker sky panel inside the top of the selection |

Kept: D, as the rule `geometry.fill_profile` (prompted SD 1.5 fill whose
context needs no upscaling, shorter side >= 512: long side capped at 640).
B fixes sel-feathered but breaks the guard (and sel-edge-bottom), and a size
rule cannot separate them: with the 0.5x padding every unclamped prompted
selection is 20 to 24 % of its context (sel-feathered 22 %, mode-fill 22 %,
sel-edge-bottom 24 %), so "under 25 % of the working area" selects all of
them. C changes nothing visible. D improves img-3000 and keeps the guard.

Verification after the change (final run, evidence folders rewritten):
`final-img3000-huge-img6000-vs-old-img6000.png` shows img-3000 (brick),
sel-huge-85pct (brick wall), img-6000 (brick with coping, working 640x536 at
0.21) and the previous img-6000 result (flat block) for comparison. img-6000
was not part of the A/B and confirms the rule on an unseen case. Not fixed:
sel-edge-bottom, sel-feathered and sel-layer-offset (their contexts are below
640 px, the rule does not touch them; the model, not a plug-in step, decides
these with seed 1234).

## All-sides expand on the Quality tier (photo-landscape-extend-all)

`expand-all-before-fix-raw-layer.png` is the generated layer of the earlier
run (whole 2432x1952 canvas as context, 1024x824 working): the ring around
the old image is the navier-stokes plus blur pre-fill, returned nearly
unchanged by juggernaut-xl-v9 with the Fooocus patch. The plan itself is
consistent (context = canvas, mask = canvas minus the keep rectangle, working
size within 1024), so the plug-in now expands SDXL-tier images one side at a
time (`geometry.expand_steps`, `App.generative_expand`): left, right, top,
bottom, each a one-sided strip; the top and bottom passes span the widened
canvas and also fill the corners. SD 1.5 keeps the single pass. The re-run is
in `../photo-landscape-extend-all/`.

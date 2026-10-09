# Remove object: visual judgement of lama-big and mat-places512

Scope: every entry in `../../benchmark/index.json` whose model is `lama-big` or `mat-places512` and whose op is `remove-small` or `remove-large`: 33 cases per model, 66 results, all `status: success`. The index was re-read at 12:52 (99 entries); the only new entries were `sd15-inpainting`, which is outside this scope. Case intent comes from `../../benchmark/benchmark-spec.json` (case id and selection rectangle) and `../../benchmark/photos-SOURCES.md`.

Files:

- `scores.csv`: one row per model and case: group, size class, the six scores, verdict, pixel metrics, seconds, VRAM peak, working size, note.
- `pairwise.md`: the better model per case, one line each.
- `strips/<case>.jpg`: comparison strips built for this judgement (downscaled to 1024 px). Top row: before (selection outlined in yellow) | lama-big | mat-places512, at 1:1 around the selection when it fits in 620 px, otherwise scaled (the label shows the factor). Bottom row: 64 px windows centred on the midpoint of each selection edge that lies inside the image, shown at 2x with nearest-neighbour scaling, for before, LaMa and MAT. Full-resolution strips and the scripts are in `C:\AI\overnight-scratch\day\judge-remove`.

Every strip was inspected; the scores are visual. Metrics were computed on the full-resolution `after-full.png` of each run against the source photo.

## Rubric (1 to 5; anchors applied to every entry)

| Criterion | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|
| Object removed | no trace | trace only at 2x, or a small remnant where the object crosses the selection edge | faint ghost visible at 1:1 (outline, shadow, tint) | clear ghost or most of the shape | object still there or replaced by a similar object |
| Background continuity | lines, textures and lighting continue exactly | continue with minor bends | continue roughly; some lines stop or bend | most structure lost | nothing continues |
| Seam | invisible at 2x | visible only at 2x | visible at 1:1 when looked for | the rectangle is obvious | hard edge at a glance |
| Texture fidelity | matches the grain, noise and sharpness around it | slightly calmer or softer | clearly softer or wrong pattern scale | smeared or blurred block | flat smudge |
| Artifacts | none | a speck | one small blob, streak or colour patch | an invented shape or obvious blob | invented object, glyphs or text |
| Plausibility | nobody would notice | an expert would notice at 1:1 | a casual viewer notices at 1:1 | noticed at viewing size | the edit is the first thing seen |

Verdict: PASS when all six are 4 or 5; PASS-WITH-NOTES with exactly one 3 and nothing lower; FAIL with any 1 or 2, or two or more 3s.

## Summary

| Model | Removed | Continuity | Seam | Texture | Artifacts | Plausibility | Mean of six | PASS | PASS-WITH-NOTES | FAIL | Median s | Median VRAM peak MiB (max) | Pairwise wins |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lama-big | 3.91 | 3.24 | 3.21 | 2.73 | 3.18 | 2.85 | 3.19 | 5 | 3 | 25 | 2.84 | 1164 (1292) | 19 |
| mat-places512 | 3.79 | 3.27 | 3.45 | 3.58 | 2.33 | 2.45 | 3.15 | 3 | 3 | 27 | 3.07 | 2318 (2638) | 13 |

One tie (text-remove-small-logo). Seconds and VRAM are from each run's `report.json` (warm process, except one cold start: face-remove-small-patch at 40 s for LaMa and 31 s for MAT). VRAM peak is the whole-GPU reading sampled during the run, so it includes what was already loaded.

The two models fail in opposite ways:

- lama-big smears. Texture is 2 or lower in 19 of 33 cases; it invents an object (artifacts 2 or lower) in only 4.
- mat-places512 hallucinates. Artifacts are 2 or lower in 19 of 33 cases: glyphs in clouds, fake text on a sign, fake handwriting, a church on a white product background, a lamp in place of a traffic light, a figure on a TV stand. Its texture is never below 3.

Only 8 LaMa results and 6 MAT results pass the strict bar. Neither model handles medium to large holes well at the working size the plug-in uses (see the plug-in causes below).

### By size class (mean of the six scores)

| Size class | Cases | lama-big | mat-places512 |
|---|---|---|---|
| tiny | 1 | 3.00 | 4.17 |
| small | 13 | 3.23 | 3.26 |
| medium | 9 | 3.30 | 3.11 |
| large | 9 | 3.07 | 2.98 |
| huge | 1 | 2.83 | 2.50 |

## Per-group winners

| Group | Cases | lama-big mean / passing | mat-places512 mean / passing | Pairwise (LaMa-MAT-tie) | Winner |
|---|---|---|---|---|---|
| person: skin and clothing (face patch, badge, bracelet) | 3 | 4.06 / 3 | 3.56 / 0 | 3-0-0 | lama-big |
| large object beside a person (two shuttles) | 2 | 2.67 / 1 | 3.00 / 0 | 1-1-0 | split: LaMa passes with notes on the plain backdrop, MAT is less bad on the flag |
| text and signage (sign pictograms, banner, NPS logo, diary lines, stain) | 5 | 3.90 / 2 | 3.23 / 1 | 4-0-1 | lama-big (MAT writes fake glyphs) |
| product on plain background (cup, handle, knob) | 3 | 3.44 / 1 | 2.83 / 0 | 3-0-0 | lama-big |
| structured background (facade, interior, street, skyline) | 7 | 2.88 / 1 | 2.74 / 1 | 4-3-0 | lama-big by a hair; both mostly fail |
| textured or natural background (fabric, fur, weave, grass, crowd, branches, clouds, water, gravel) | 11 | 2.88 / 0 | 3.42 / 4 | 2-9-0 | mat-places512 |
| illustration, halftone print (baby, stamp) | 2 | 3.00 / 0 | 2.83 / 0 | 2-0-0 | lama-big (both fail: LaMa loses the dot screen, MAT invents objects) |

## Five worst results and likely causes

1. **lama-big, face-remove-large-shuttle (9/30).** A 732x2064 hole on the image's left edge leaves a dark smeared mass with shuttle-shaped residue; the flag does not continue. Plug-in first: the context is clamped at the image border and scaled to a 408x512 working size (about 5x down), so the model fills a hole of roughly 140x400 px and the result is upscaled 5x. Model second: LaMa averages over very large holes.
2. **lama-big, night-street-remove-large-car (11/30).** The car becomes a pale smear with a ghost column; the crosswalk is lost. The cause is the same as case 1: an 806x355 hole worked at 512x368 and upscaled. Laplacian ratio 0.004: almost no detail survives.
3. **mat-places512, handwriting-remove-large-lines (13/30).** Three lines of script are replaced by invented scribbles. This is the model: MAT synthesises the dominant texture of the context, and here that texture is handwriting. The plug-in cannot fix it except by not using MAT on text.
4. **mat-places512, interior-remove-large-tv (13/30).** A dark TV-shaped panel remains and an orange figure is invented on the stand. This is the model (object completion from the stand that is still there). The selection shares part of the blame: the stand is outside it, so the cue stays.
5. **mat-places512, night-street-remove-small-light (13/30).** The traffic light is replaced by a bright yellow lamp. The model completes a lamp from the glow left outside the tight selection. The selection is partly at fault: the halo is outside it.

Close behind: MAT clouds-remove-large-palm and illustration-remove-large-baby (14/30, invented glyphs and flags), and LaMa architecture-remove-large-laundry (15/30, smeared facade).

### Plug-in, selection and harness causes (not the model)

- **Working size caps LaMa at 512.** `stable_boy/geometry.py` `INPAINT_MODEL = ModelProfile("inpaint_model", min_side=256, max_side=512, min_context=512)` applies to both models. `context_rect` grows the context to about three times the selection, so every medium or large hole is downscaled 2x to 5x before inference and upscaled after it. MAT is a 512 model, but LaMa is fully convolutional and is normally run at the native resolution of the crop. LaMa's median Laplacian ratio of 0.033 (detail inside the hole is 3% of the detail around it) and its texture mean of 2.73 come mostly from this. Suggested change (not made; this lane owns no code): give LaMa its own profile with `max_side` around 1024 to 2048, or keep the crop at native resolution when it fits, and re-run the benchmark's large cases to confirm. Whether comfyui-inpaint-nodes resizes LaMa input internally needs checking first.
- **Default order prefers MAT.** `stable_boy/app.py` `removal_model_available` tries `("mat-places512", "lama-big")`, so MAT is used whenever both are installed. See the recommendation.
- **Remnants where the object crosses the selection.** The plug-in already grows the removal mask (6 to 16 px in these runs, plus a 2 to 24 px feather; see the `mask(grow=... feather=...)` line in each `plugin-log.txt`). In several cases the object reaches further than that past the spec rectangle (knob, water plants, pet scar below the box, traffic-light glow, stain), and both models keep or regrow the rest. That is the selection (spec rectangles are tight), not the plug-in or the model; a user would see the same thing with a tight marquee.
- **No leaks.** The plug-in blends the fill into a band up to about 24 to 30 px outside the selection (its grow plus feather, as intended). Beyond 40 px from the selection the result equals the source in every case: mean absolute difference 0.00 to 0.23 levels, and no pixel differs by more than 12 levels (`mad_beyond_40px`, `leak_px_frac_beyond_40px`). `mad_outside_band` (outside the selection grown by the spec feather plus 2 px, 0.03 to 0.77 levels) includes the plug-in's blend band and is not a leak measure.
- **Colour management (for the benchmark lane).** For sources with an embedded non-sRGB profile (Adobe RGB: food, hands, crowd, text; ProPhoto: signage), `after-full.png` differs from the decoded source by 5 to 15 levels everywhere. It matches the source converted to sRGB within 0.1 to 0.8 levels and carries no ICC profile. The whole image is converted to sRGB somewhere between import and export. This is colour management in GIMP or the harness, not the model. The metrics here compare against the sRGB-converted source.

## Pixel metrics and how far to trust them

Per entry, in `scores.csv`:

- `mad_beyond_40px` and `leak_px_frac_beyond_40px`: mean absolute difference from the source more than 40 px outside the selection, and the fraction of those pixels that differ by more than 12 levels. Both are about 0 everywhere, so no leaks. `mad_outside_band` is the same difference measured closer in (see above).
- `lap_ratio`: Laplacian variance inside the hole (eroded 4 px) divided by that in a ring 8 to 40 px outside it. About 1 is matching detail; below 0.2 is smeared; above 1.5 means new high-frequency content was invented. LaMa median 0.033, MAT median 0.588.
- `seam_ratio`: mean Sobel gradient within 1 px of the selection edge, divided by that 6 to 24 px either side. Above 1 suggests a step at the seam.

Where they disagree with the eye:

- **lap_ratio is the useful tie-breaker.** It ranks LaMa's smearing (large holes at 0.001 to 0.01) and MAT's inventions correctly: 9.9 on the cup with the church, 4.2 on the invented lamp, 2.2 on fake text on the sign, 3.0 on the knob blob. It misreads flat targets. LaMa on text-remove-large-signs scores 0.115, which looks like smearing, but the correct fill is a flat yellow panel and the ring contains letters and the frame. The eye is trusted there.
- **seam_ratio is weak.** It is measured at the selection edge, but the plug-in blends the fill 6 to 30 px further out, so the real transition is spread across the "away" band. Most values are below 1 because the fill is smoother than the busy ring, not because the seam is invisible. LaMa's birch seam is obvious at a glance yet has a ratio of 0.77. It only flagged real problems where MAT drew strong strokes at the edge (night light 1.93, stain 1.59, signage logo 1.29). The 2x zooms are trusted over it.

## Recommendation

Make **lama-big** the default removal model and reverse the order in `removal_model_available`. On the cases users bring to Remove object, it is the safer choice. It won 19 of 33 pairwise comparisons, and every comparison on people, products and text (10 to 0, one tie). It almost never invents an object (4 cases against 19 for MAT). It uses about half the VRAM (median 1.2 GB against 2.3 GB) at the same speed (about 3 s). Its failure is blur, which a user reads as "needs another pass". MAT's failure is invented glyphs, figures and buildings, which reads as "broken". MAT is clearly better on fine natural textures (fur, weave, grass, branches, crowd: 9 of 11). It is worth keeping as an optional "texture" alternative, not as the default. Neither model is good enough on medium and large holes as the plug-in drives them today: LaMa passed only 8 of 33. The first thing to fix is the 512 px working cap for LaMa in `geometry.INPAINT_MODEL`. Re-judge both models after those changes before closing the question.

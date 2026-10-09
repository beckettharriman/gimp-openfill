# SD 1.5 inpainting checkpoints: visual judgement of sd15-inpainting, realistic-vision-v6-inpainting and dreamshaper-8-inpainting

Scope: every entry in `../../benchmark/index.json` for `sd15-inpainting` (sd15), `realistic-vision-v6-inpainting` (rv6) and `dreamshaper-8-inpainting` (ds8): 33 core cases per model, 99 results, all `status: success`. The index was re-read at the end (13:45, 198 entries). There were no new entries for these three models; the only additions were `juggernaut-xl-v9`, which is outside this scope. Case intent comes from `../../benchmark/benchmark-spec.json`. The plug-in settings per run come from each run's `plugin-log.txt`.

Method and rubric follow `../remove/README.md`, so the two reports can be compared. The one change: the first criterion is "prompt adherence" (for removal cases it is scored exactly like "object removed" there).

Files:

- `scores.csv`: one row per model and case, with the group, operation, size class, the six scores, verdict, total (6 to 30), pixel metrics, seconds, cold flag, VRAM peak, working size and a note.
- `pairwise.md`: the best of the three per case, one line each, with every model's total and verdict.
- `strips/<case>.jpg`: comparison strips (downscaled to 1024 px). Fill cases: a 2x2 grid of before (selection in yellow) | sd15 / rv6 | ds8, cropped around the selection at 1:1 when the crop fits in 500 px, otherwise scaled (the label shows the factor). Below that, 64 px windows at the midpoints of two selection edges, shown at 2x with nearest-neighbour scaling. Expand cases: the full canvases (the original outlined, with new area grey in "before"), then 400 px 1:1 crops at the main seam, then 2x seam windows. Full-resolution strips and the scripts (`judge.py`, `crop.py`, `scores_in.py`, `make_outputs.py`) are in `C:\AI\overnight-scratch\day\judge-sd15`.

Every strip was inspected. The scores are visual. Wide selections (roof tiles) were also checked on extra 1:1 crops. Metrics were computed on the full-resolution `after-full.png` of each run. They were compared against the source photo, converted to sRGB where it had an embedded profile, and placed at the margin offset for expand cases.

## Rubric (1 to 5; anchors applied to every entry)

| Criterion | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|
| Prompt adherence (prompted) | requested content present and convincing | present, with a minor deviation (size, style) | present but wrong in kind or partial (disc instead of hoop, extra object) | only a hint or garbled | absent, or a different thing |
| Prompt adherence (remove) | no trace | trace only at 2x | faint ghost at 1:1 | clear ghost, or most of the shape | object still there or replaced by a similar object |
| Background continuity | lines, textures and lighting continue exactly | continue with minor bends | continue roughly; some lines stop or bend | most structure lost | nothing continues |
| Seam | invisible at 2x | visible only at 2x | visible at 1:1 when looked for | the rectangle is obvious | hard edge at a glance |
| Texture fidelity | matches grain, noise and sharpness around it | slightly calmer or softer | clearly softer or wrong pattern scale | smeared or blurred block | flat smudge |
| Artifacts | none | a speck | one small blob, streak or colour patch | an invented shape or obvious blob | invented object, glyphs or text |
| Plausibility | nobody would notice | an expert would notice at 1:1 | a casual viewer notices at 1:1 | noticed at viewing size | the edit is the first thing seen |

Verdict: PASS when all six are 4 or 5; PASS-WITH-NOTES with exactly one 3 and nothing lower; FAIL with any 1 or 2, or two or more 3s.

## Summary

| Model | Adherence | Continuity | Seam | Texture | Artifacts | Plausibility | Mean of six | PASS | PASS-WITH-NOTES | FAIL | Pairwise wins | Median s (warm) | Cold s | Median VRAM peak MiB (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sd15-inpainting | 3.70 | 3.70 | 3.79 | 3.36 | 3.12 | 2.97 | 3.44 | 7 | 7 | 19 | 9 | 9.9 | 56.1 | 3616 (4538) |
| realistic-vision-v6-inpainting | 3.76 | 3.64 | 3.45 | 3.52 | 3.03 | 2.82 | 3.37 | 5 | 3 | 25 | 10 | 9.4 | 48.8 | 3552 (4828) |
| dreamshaper-8-inpainting | 4.06 | 3.48 | 3.36 | 3.39 | 3.30 | 3.09 | 3.45 | 7 | 10 | 16 | 12 | 8.8 | 38.8 | 3520 (4444) |

There were two ties (face-expand-right and text-remove-small-logo). Seconds and VRAM are from each run's report. Median seconds exclude the one cold start per model. The VRAM peak is a whole-GPU reading, including about 0.8 to 1.0 GB held by the desktop. All three fit 8 GB without offloading and cost the same: about 9 s per fill and 3.5 GB. Speed and memory do not separate them, so only quality does.

Means are within 0.1 of each other. The verdict counts differ more: ds8 has 17 of 33 acceptable (PASS or PASS-WITH-NOTES), sd15 has 14 and rv6 has 8. rv6 loses mostly on removal, where it repaints a similar object (a new fork, a new car, a modern house in place of the barn, a cushion).

### Per-group winners

Cell: mean of six / results not FAIL / pairwise wins.

| Group | Cases | sd15 | rv6 | ds8 | Winner |
|---|---|---|---|---|---|
| remove (empty prompt, plug-in removal prompt) | 13 | 3.47 / 6 / 4 | 3.28 / 2 / 2 | 3.77 / 9 / 6 | ds8, clearly. rv6 should never do removal. |
| replace with a prompt (object into a scene, object swap) | 12 | 3.38 / 4 / 3 | 3.39 / 3 / 4 | 3.26 / 5 / 5 | ds8 on count, but it also has the worst failures (pasted panels). No safe winner. |
| fill (material change, damaged area) | 4 | 2.96 / 1 / 2 | 2.79 / 0 / 2 | 2.58 / 0 / 0 | sd15. All three are bad here: 1 acceptable result out of 12. |
| expand one side | 2 | 3.67 / 1 / 0 | 4.00 / 2 / 1 | 3.58 / 1 / 0 | rv6 (the only one that carries the damask into the new strip) |
| expand all sides | 2 | 4.33 / 2 / 0 | 4.33 / 1 / 1 | 4.08 / 2 / 1 | sd15 and ds8 (both acceptable twice); rv6 shifts the sky colour |

Sub-group that matters for defaults: **text in the prompt** (signage-replace-text, text-replace-text-20h). 0 of 6 results are acceptable. No SD 1.5 checkpoint writes the requested words. sd15 at least produced "20" in the sign's font.

Removal against the dedicated removal models, on the same 13 cases, with the same rubric, from `../remove/scores.csv`: lama-big 3.15 mean / 3 acceptable, mat-places512 3.13 / 3, sd15 3.47 / 6, rv6 3.28 / 2, ds8 3.77 / 9. On these cases ds8 with the removal prompt beats both LaMa and MAT. Part of the difference is the plug-in: SD 1.5 removal runs at up to 768 px with a 1.0x margin, while LaMa and MAT are capped at 512 px. ds8 still invents objects on plain or iconic backgrounds (cup, monument).

## Five worst results and likely causes

1. **sd15, architecture-material-roof-tiles (10/30).** The 1620x89 strip of corrugated awning becomes a soft dark band with no tiles, and a yellow box is invented on it. Plug-in first: a very wide, thin selection gets a 2000x1273 context, worked at 640x408 (scale 0.32), so the model sees a band about 28 px tall. No SD 1.5 model can draw tiles at that size. rv6 and ds8 fail the same way (13/30 and 13/30), minus the box. Model second: sd15 adds the box.
2. **ds8, texture-damaged-huge (11/30).** The fill is a 1792x1360 selection on a 1920x1440 brick wall. ds8 builds a deep recessed niche with a flat orange back wall. Model: ds8 composes a scene instead of continuing a texture. Plug-in: colour match is switched off for this case (`color_match=0.0`, the selection covers most of the context), and the work is done at 640x480 (scale 0.33). sd15 also invents a recess. rv6 keeps a brick wall but darker, as an obvious rectangle.
3. **ds8, landscape-replace-balloon (12/30).** The balloon is painted on a pasted rectangle of blue sky inside the white overcast sky.
4. **ds8, product-replace-spoon (12/30).** The spoon sits on a pasted black square on the white table.
   Cases 3 and 4 share a cause. Plug-in first: SD 1.5 prompted fills pre-fill the hole with neutral grey (`prefill=border/neutral`). On a near-white, low-texture context, ds8 reads the grey block as a separate picture and fills it edge to edge, the same failure the code comment in `geometry.prefill_for` describes for SDXL. Model second: sd15 and rv6 get the same grey hole and mostly do not do this. ds8 is the checkpoint that cannot tolerate it.
5. **sd15, signage-replace-text (12/30).** "White text that says Desert Museum" comes out as a ragged blue bar with gibberish letters. Model: SD 1.5 cannot spell. All three fail (14/30 each for rv6 and ds8). The blue panel instead of the brown sign is probably the grey pre-fill again: the model paints a sign over the grey instead of continuing the brown.

Close behind (14/30): sd15 handwriting-remove-large-lines (writes fake script; all three do), rv6 landscape-remove-small-barn (builds a modern house), rv6 text-replace-text-20h ("R7L").

## Model behaviour against plug-in behaviour

Plug-in settings seen in these runs (from `plugin-log.txt`):

- Removal (empty prompt): 1.0x margin (a 3x context), working size up to 768, removal prompt "seamless continuation of the surrounding background..." with a negative that includes object, text and person, navier-stokes pre-fill, colour match 1.0, mask grow 16 px plus feather up to 24 px.
- Prompted fill: 0.5x margin, working size capped at 640 when the context is large (`SD15_PROMPT_MAX_SIDE`), neutral grey pre-fill, colour match 1.0 (0 when the selection covers most of the context), the same grow and feather.
- Expand: one pass for all sides, with the context capped at 768 on the long side (face-expand-right worked at 384x768 for a 1500x3000 context).

What is the plug-in (it would affect any SD 1.5 checkpoint):

- **Pale frame around prompted fills.** The selection outline shows as a lighter rectangle in hands-replace-strawberry (all three; ds8 at a glance), product-replace-spoon (sd15, rv6), product2-material-suede (rv6, ds8). It appears with the grey pre-fill. Among the 13 removal cases (navier-stokes pre-fill) only the rv6 handwriting band and faint columns on the portrait backdrop resemble it, and they are smoothing rather than a pale outline. Likely cause: the grey pre-fill covers the grown and feathered mask, but the band where the model mask is below 1.0 is only partly regenerated, so grey survives there and the GIMP layer mask blends it back in. This needs checking in `workflow.py` (the `INPAINT_MaskedFill` extent against the sampler mask). The fix would be to pre-fill only where the mask is 1.0, or to use a blurred pre-fill instead of flat grey on the band.
- **Pasted panels with ds8.** The neutral grey pre-fill on bright, flat contexts causes the balloon and spoon failures. Suggestion: use the border (navier-stokes) pre-fill for SD 1.5 when the context has little texture, or tint the neutral fill to the ring's mean colour.
- **Soft results on large contexts.** Working scales of 0.3 to 0.5 (roof tiles, texture-huge, fabric-large, night car, expand strips) produce smooth patches. The fills show as snow, grass and brick that are calmer than the photo (median Laplacian ratio inside against the ring: sd15 0.39, rv6 0.17, ds8 0.28). Thin selections suffer most, because the context grows from the larger side.
- **No leaks.** More than 40 px outside the selection (or inside the original area for expand), every result equals the source: mean absolute difference at most 0.23 levels, and at most 0.006% of pixels differ by more than 12 levels.

What is the model:

- **rv6 repaints the object it was asked to remove** (fork, car, barn as a house, AC as a cushion) despite the removal prompt and negative. It is a portrait and realism checkpoint with a strong object prior.
- **ds8 composes scenes**: niches, framed panels, a rock spire on a product shot. On removal it is the most willing to leave the background empty.
- **sd15 is the most conservative on texture.** It wins fabric, cuff, shuttle backdrop, suede and moon scale. It is also the least prompt-faithful: no canoe at all, and goggles instead of aviators.
- **All three cannot write text** and continue handwriting as pseudo-script.

## Pixel metrics and how far to trust them

Same definitions as `../remove/README.md`: `mad_beyond_40px` and `leak_px_frac_beyond_40px` (leak), `lap_ratio` (Laplacian variance inside the hole eroded 4 px, divided by the variance in a ring 8 to 40 px outside), and `seam_ratio` (mean Sobel gradient within 1 px of the edge divided by the gradient 6 to 24 px either side). For expand cases the hole is the new margin and the ring is the old image.

- **lap_ratio works for removal and texture fills.** Low values match the smooth patches seen (fabric-damaged-large at 0.008 to 0.022, crowd monument at 0.013 to 0.068). For prompted object fills it measures the new object, not quality: the ladybug is 26.3 for sd15, the earring 35.2 for ds8 and the 20H text 57.8 for sd15. It is not a tie-breaker there.
- **seam_ratio is weak, as in the remove report.** It flagged only strong strokes at the edge (sd15 20H 3.28, rv6 earring 2.65 where the hoop touches the edge, handwriting about 1.4 to 1.6). It missed the strawberry frame (0.81 to 1.04) and the ds8 balloon panel (0.37, the panel edge lies outside the measured band). The 2x zooms were trusted over it.
- Pairwise ties were broken by eye. No case needed the metrics to decide.

## Recommendation

**Bundled verified "Fast" default: dreamshaper-8-inpainting.** It has the most acceptable results (17 of 33 against 14 for sd15 and 8 for rv6), the most pairwise wins (12), the best prompt adherence (4.06) and the best removal (9 of 13 acceptable, better than LaMa and MAT on the same cases). It is also slightly the fastest and smallest. Its failures are the loudest, though: pasted panels on flat backgrounds and invented niches on huge fills. The grey pre-fill change above should land before it is called verified, and those two cases should be re-run. **Do not ship realistic-vision-v6-inpainting as a default.** Its removal behaviour (repainting the object) rules it out. Keep sd15-inpainting as the licence-clean baseline and the texture-continuation fallback.

**Are any of them good enough as the default for prompted fills? No.** On prompted work (replace plus fill, 16 cases) the best checkpoint is acceptable 5 times out of 16. Across all three models and both fill groups, 1 of 12 material or damaged-area fills is acceptable, and 0 of 6 text prompts. SD 1.5 at the plug-in's 512 to 640 px working size is usable for small, simple objects on textured backgrounds (moon, ladybug, aviators, canoe, strawberry apart from the frame) and for removal. It is not usable for material changes, large areas, flat product backgrounds or text. Ship it as the "Fast" tier with variations on and that limitation stated. Make the default for prompted fills the SDXL tier once its own judgement confirms it (juggernaut-xl-v9 was benchmarked but is not judged here). Re-judge after the pre-fill fix, because it alone accounts for at least 7 of the 99 results being FAIL.

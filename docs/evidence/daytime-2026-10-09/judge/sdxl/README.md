# SDXL checkpoints: visual judgement of juggernaut-xl-v9, realvisxl-v5 and sdxl-base

Scope: every entry in `../../benchmark/index.json` for `juggernaut-xl-v9` (jxl) and `realvisxl-v5` (rvxl): 33 core cases per model, all `status: success`; and the 33 core runs of `sdxl-base` (base; the "quality" tier, SDXL 1.0 base with the Fooocus inpaint patch), of which 32 succeeded. The sdxl-base runs finished at 15:35 but were not yet posted to the index when this report was written; they were scored from the run's raw output (see "sdxl-base: source and gaps" at the end). 98 results in total. Case intent comes from `../../benchmark/benchmark-spec.json`. The plug-in settings per run come from each run's `plugin-log.txt`.

Method, rubric, verdict rule, metrics and file layout follow `../sd15/README.md` (which follows `../remove/README.md`), so the three reports can be compared row by row. The first criterion is "prompt adherence"; for removal cases it is scored exactly like "object removed" in the remove report, including the convention that an object replaced by a similar object scores 1 on adherence, artifacts and plausibility.

Files:

- `scores.csv`: one row per model and case, same columns as `../sd15/scores.csv`: group, operation, size class, the six scores, verdict, total (6 to 30), pixel metrics, seconds, cold flag, VRAM peak, working size and a note.
- `pairwise.md`: the best SDXL checkpoint per case, one line each, plus the cross-family verdict (best SDXL against best SD 1.5, and against the best of LaMa and MAT on removal cases).
- `strips/<case>.jpg`: comparison strips (downscaled to 1024 px), same layout as the SD 1.5 strips: before (selection in yellow) and each model, cropped around the selection at 1:1 when the crop fits in 500 px, otherwise scaled (the label shows the factor); below, 64 px windows at the midpoints of two selection edges at 2x nearest-neighbour. Expand cases: full canvases, then 400 px 1:1 crops at the main seam, then 2x seam windows.
- `cross/<case>.jpg`: cross-family strips used for the cross-family verdict: before | best SDXL | best SD 1.5 (the winner in `../sd15/pairwise.md`) | best of LaMa and MAT (highest total in `../remove/scores.csv`, removal cases only). Labels carry the model and its total.
- Full-resolution strips and the scripts (`judge.py`, `crop.py`, `cross.py`, `base_post.py`, `scores_in.py`, `base_scores_1.py`, `cross_in.py`, `make_outputs.py`) are in `C:\AI\overnight-scratch\day\judge-sdxl`.

Every strip was inspected. The scores are visual. Wide or scaled selections (roof tiles, monument base, landscape expand margins, logo band) were also checked on extra 1:1 crops. Metrics were computed on the full-resolution `after-full.png` of each run against the source photo converted to sRGB where it has an embedded profile, and placed at the margin offset for expand cases.

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
| juggernaut-xl-v9 | 3.88 | 3.70 | 3.45 | 3.48 | 3.12 | 2.73 | 3.39 | 5 | 4 | 24 | 11 | 24.7 | 104.7 | 7296 (7852) |
| realvisxl-v5 | 3.76 | 3.64 | 3.48 | 3.52 | 3.33 | 2.94 | 3.44 | 9 | 1 | 23 | 12 | 29.2 | 89.8, 120.8 | 7182 (7802) |
| sdxl-base (32 of 33) | 3.59 | 3.53 | 3.44 | 3.50 | 3.03 | 2.56 | 3.28 | 7 | 0 | 25 | 2 | 27.6 | 33.8 | 7205 (7767) |

Eight ties. Seconds and VRAM for jxl and rvxl are from each run's report; for sdxl-base the seconds are from the run's `gimp-report.json` and the VRAM peak was taken from the benchmark's `logs/gpu-samples.jsonl` over each run's start and end time, the same samples the benchmark uses. Median seconds exclude cold starts (rvxl ran in two GIMP processes, so it has two; sdxl-base's cold start is short because the base checkpoint was still cached from the expand lane). The VRAM peak is a whole-GPU reading including about 0.8 to 1.0 GB held by the desktop. All three fit the 8 GB card without offloading or OOM (`comfy_offload_lines` and `oom` empty for jxl and rvxl; no offload or OOM lines in the sdxl-base plug-in logs), with 300 to 500 MiB to spare at the peak. Against the SD 1.5 tier (dreamshaper-8: 8.8 s, 3.5 GB) an SDXL fill costs about 3x the time and 2x the memory.

The two fine-tuned checkpoints are close (means within 0.05, 9 against 10 acceptable results). sdxl-base is clearly behind: lowest mean (3.28), lowest plausibility (2.56), 7 acceptable out of 32 and only 2 pairwise wins. For comparison, dreamshaper-8-inpainting had 17 of 33 acceptable and sd15-inpainting 14 on the same cases (`../sd15`). On the whole set **SDXL as benchmarked is worse than SD 1.5**, and the reason is removal and expand, not prompted fills.

### Per-group winners

Cell: mean of six / results not FAIL / pairwise wins. Cross-family: best SDXL against best SD 1.5, as SDXL better / SD 1.5 better / tie.

| Group | Cases | jxl | rvxl | base | Ties | Winner | Cross-family vs SD 1.5 |
|---|---|---|---|---|---|---|---|
| remove (empty prompt, plug-in removal prompt) | 13 | 3.17 / 3 / 5 | 3.27 / 3 / 4 | 2.87 / 1 / 1 | 3 | none: all three repaint objects; base worst (skyscraper, buckle, car pair) | 4 / 8 / 1 |
| replace with a prompt (object into a scene, object swap) | 12 | 3.90 / 4 / 4 | 3.90 / 6 / 4 | 3.94 / 6 / 1 | 3 | rvxl and base tie on count (6 of 12); rvxl wins more cases | 8 / 3 / 1 |
| fill (material change, damaged area) | 4 | 2.88 / 1 / 1 | 2.88 / 0 / 2 | 2.54 / 0 / 0 | 1 | none; jxl's tweed is the only acceptable fill | 1 / 2 / 1 |
| expand one side | 2 | 3.83 / 1 / 1 | 3.75 / 1 / 0 | 3.42 / 0 / 0 | 1 | jxl (carries the damask, at the wrong scale) | 0 / 1 / 1 |
| expand all sides | 2 (base: 1) | 2.42 / 0 / 0 | 2.67 / 0 / 2 | 3.17 / 0 / 0 | 0 | none: 0 of 5 acceptable | 0 / 2 / 0 |

- **Prompted object insertion is where SDXL earns its cost.** Strawberry (jxl and rvxl 30/30, base 29), balloon (29 for all three), spoon, canoe, ladybug, fox and sunglasses are photographic, and none shows the pasted panel or pale frame the SD 1.5 tier had on balloon, spoon and strawberry. sdxl-base is as good as the fine-tunes here and draws the only correct earring (one small hoop on an ear). The best SD 1.5 checkpoint passed 5 of 12; rvxl and base pass 6.
- **Text: still no.** "Desert Museum" becomes "Deserttant Msseu Vesi" (jxl), "Sauvent Musum 45" (rvxl) and "2D74" (base); for "20H" all three erase the 18H and write nothing. jxl at least gets "Desert" and the sign's lettering style.
- **Removal is bad, and worst on the base model.** 3, 3 and 1 of 13 acceptable. SDXL repaints what it was told to remove (palm trunk, a new car or cars, a new painting in place of the portrait, a hill or barn roof in place of the barn) or invents (torches or a gold buckle on a sleeve, a skyscraper in place of the obelisk, a green haze on a white product shot). Only the monument (jxl, rvxl), the high chair, the handwriting (jxl) and the logo are as good as or better than the other families.
- **Expand all sides fails for all three:** blurred dark-green margins with hard horizontal steps on the landscape (jxl also writes a fake watermark; base timed out), and cream or grey margins with a visible step at the old frame on the white product shot (all three).
- **jxl against rvxl against base:** jxl is fastest (24.7 s) and best at structured removals (monument, handwriting, AC) and expand-one-side. rvxl has the fewest artifacts (3.33) and the most clean passes on people and products. base matches them on object insertion but invents the most on removal and material changes (two floating shoes) and shifts the backdrop colour on the one-side expand.

### Cross-family comparison

Decided by eye on `cross/<case>.jpg` (best SDXL result against the best SD 1.5 result from `../sd15/pairwise.md` and, on removal cases, the better of LaMa and MAT from `../remove/scores.csv`). Totals from different reports were used only as a guide; they agree with the visual call except on text-replace-text-20h, where SDXL scores higher (clean, but writes nothing) and SD 1.5 is called better because it wrote "20".

| Comparison | Cases | SDXL better | Other better | Tie |
|---|---|---|---|---|
| Best SDXL vs best SD 1.5, all cases | 33 | 13 | 16 | 4 |
| Best SDXL vs best SD 1.5, prompted cases (replace, fill, expand) | 20 | 9 | 8 | 3 |
| Best SDXL vs best SD 1.5, replace with a prompt only | 12 | 8 | 3 | 1 |
| Best SDXL vs best SD 1.5, removal cases | 13 | 4 | 8 | 1 |
| Best SDXL vs best of LaMa and MAT, removal cases | 13 | 5 | 7 | 1 |

sdxl-base changed the best-SDXL result in two cases (earring, cup); the earring flips from SD 1.5 better to SDXL better. SDXL wins against LaMa/MAT on monument, handwriting, high chair, AC unit and the shirt patch; it loses on palm, fork, portrait, barn, car, shuttle and logo, nearly all by putting an object back. The product-cup case is a tie (LaMa's smear ring against SDXL's haze).

## Five worst results and likely causes

1. **All three, texture-damaged-huge (10/30 each).** A 1728x1296 selection on a 1920x1440 brick wall becomes a recessed niche of giant flat bricks, about ten times the wall's brick size, with a shadowed frame. Plug-in first: the selection covers about 80% of the context, so there is almost no ring to anchor scale or colour; colour match is switched off (`color_match=0.0`) and the work is done at 1024x768 (scale 0.53). Model second: SDXL, like ds8, composes a scene ("a red brick wall" seen as a subject) instead of continuing a texture. All six generative checkpoints judged so far fail this case; it should not be offered as a single-pass fill.
2. **jxl, landscape-expand-all (11/30).** 256 px margins on all sides: the sky is fine, but the right and bottom margins are blurred dark green with a hard horizontal step, and garbled watermark-like text is written in the bottom-left corner. Plug-in first: the 2432x1952 canvas is worked at 1024x824 (scale 0.42), so each margin is about 107 px at working size, and this run used the general guidance (no `cfg=4.0` in its log line). The banding matches what the uncommitted `workflow.EXPAND_SDXL_CFG` change describes (hard bands at cfg 7). Model second: the watermark text is the checkpoint's prior near image edges; the uncommitted `EXPAND_FRAME_NEGATIVE` adds "watermark" to the negative for user prompts. rvxl fails the same case (13/30) without the text; sdxl-base, which ran with `cfg=4.0`, timed out on it.
3. **jxl and base, night-street-remove-large-car (12/30 each).** The car is replaced by three toy-like cartoon cars (jxl) or a smeared red and white car pair (base). Model: the object prior; the plug-in's removal prompt ("seamless continuation ... nothing added") and negative ("object, ... person") do not stop it. Plug-in: an empty-prompt removal is sent to the generation model at scale 0.53. rvxl puts back one realistic car (17/30).
4. **base, landscape-remove-small-barn (12/30).** The barn becomes a neon-green slope with a dark jagged ridge and a grey dome remnant. Model: base has the weakest grip on photographic colour of the three; jxl (green hill) and rvxl (mound with a barn roof) fail the same case less loudly. Selection: the tree overlapping the barn's right end keeps a cue.
5. **All three, clouds-remove-large-palm (13 to 14/30).** The trunk is repainted (three trunks for rvxl, one for jxl and base), and a lighter vertical sky band follows the left selection edge. Model: the crown outside the selection is a strong cue and every SDXL checkpoint completes the palm. Selection: the spec rectangle stops below the crown. SD 1.5 (ds8) and LaMa removed it.

Close behind: base crowd-remove-large-monument (14, a skyscraper in place of the obelisk), jxl, rvxl and base interior-remove-small-portrait (15, a new framed painting), base product2-material-suede (14, two shoes, one floating), base handwriting-remove-large-lines (14, a pale tear-like band with pseudo-script).

## Model behaviour against plug-in behaviour

Plug-in settings seen in these runs (from `plugin-log.txt`; identical for all three checkpoints except where noted):

- Every SDXL fill uses `template=sdxl_fooocus` (Fooocus inpaint head and patch), the border pre-fill with navier-stokes (also for prompted fills, unlike SD 1.5's neutral grey), colour match 1.0 (0.0 for texture-damaged-huge), mask grow 16 px in the image (6 to 32 px at working size) and feather up to 24 px, and a working size of 768 to 1024 on the long side. Small contexts are upscaled: earring 3.0x, ladybug 2.0x, moon 1.67x, spoon 1.5x.
- Removal (empty prompt) uses the plug-in's removal prompt and negative on the same checkpoint.
- Expand: one pass, canvas worked at up to 1024 px (face-expand-right 512x1024, landscape 1024x824). The jxl expand runs and rvxl landscape-expand-all and face-expand-right show no `cfg=` in the log; rvxl interior-expand-left and product-expand-all and all four sdxl-base expands show `cfg=4.0`, so the expand guidance change was in place for those six only.

What is the plug-in (would affect any SDXL checkpoint):

- **No pasted panels.** The border pre-fill removes the SD 1.5 tier's worst prompted failures: balloon and spoon pass on all three checkpoints, and no strawberry frame. This is evidence for the SD 1.5 report's suggestion to stop using the neutral grey pre-fill there.
- **Objects clipped at the selection edge.** At 1.3x to 3x upscale the model fills the selection edge to edge, and the layer mask (grow 6 to 16 px) cuts what crosses it: the second watermelon slice (all three), the earring (jxl, rvxl), the ladybug (jxl, base), the suede shoe's toe (jxl, rvxl). A small-object hint (a mask smaller than the selection for "replace into empty" fills, or a larger layer-mask grow when the generated object reaches the mask edge) would help. This is the plug-in plus a tight selection, not the model.
- **Calm patches.** Fill areas come back cleaner than the photo: smooth bright snow around the fox, a noise-free darker square around the moon, a uniform paper band on the diary, a lighter band on the logo panel. The plug-in does not re-inject grain after colour match. Median Laplacian ratio inside against the ring: jxl 0.23, rvxl 0.27, base 0.32 (SD 1.5: 0.17 to 0.39), so SDXL is not softer than SD 1.5 overall; the issue is noise, not sharpness.
- **Flat stripes on the napkin (fork).** All three checkpoints keep the navier-stokes streaks of the pre-fill as flat colour bands without weave (`lap_ratio` 0.009 to 0.010). Likely cause: with the Fooocus patch the sampler stays close to the pre-filled pixels on a low-contrast, regular texture. Needs a check with a blurred or noisy pre-fill on that case.
- **Expand banding.** See worst case 2. The rvxl and sdxl-base runs with `cfg=4.0` still fail product-expand-all (visible step at the old top and bottom edge, cream tint), so the guidance change alone does not fix the white-background case. The expand lane should re-run both expand-all cases with the current working tree before SDXL expand is enabled by default.
- **Removal routed to a generation model.** All 13 removal cases went through the SDXL checkpoint with the removal prompt. The plug-in already prefers LaMa/MAT when "Remove object" is ticked (`app.removal_model_available`); an empty prompt on the SDXL tier should do the same, or fall back to the SD 1.5 removal path.
- **No leaks.** More than 40 px outside the selection (or inside the original area for expand), every result equals the source: mean absolute difference at most 0.23 levels, and at most 0.013% of pixels differ by more than 12 levels.

What is the model:

- **All three SDXL checkpoints have a strong object prior** and repaint what was removed (palm, portrait, car, barn) or something of the same kind. The removal prompt and negative are not enough. This is the same failure that ruled rv6 out in the SD 1.5 report, and it applies to every SDXL checkpoint, most of all to sdxl-base (skyscraper, gold buckle, car pair).
- **jxl invents more than rvxl** (torches on a sleeve, toy cars, watermark text, a floating shoe); rvxl invents less but repaints more literally (three trunks, barn roof). **sdxl-base invents the most** and drifts in colour (neon-green slope, greener backdrop strip on the portrait expand).
- **All three compose product shots** when asked for a material ("a brown suede leather shoe" becomes a new shoe on white pedestal blocks), and a niche when asked for a texture.
- **All three draw excellent objects** at the right lighting and perspective, which no SD 1.5 checkpoint did consistently.
- **Neither writes the requested text.**

## Pixel metrics and how far to trust them

Same definitions as `../remove/README.md` and `../sd15/README.md`: `mad_beyond_40px` and `leak_px_frac_beyond_40px` (leak), `lap_ratio` (Laplacian variance inside the hole eroded 4 px over a ring 8 to 40 px outside) and `seam_ratio` (mean Sobel gradient within 1 px of the edge over the gradient 6 to 24 px either side). For expand cases the hole is the new margin and the ring is the old image.

- Leak metrics confirm the visual: no change outside the blend band in any run.
- `lap_ratio` again measures the new object on prompted fills (ladybug 50 to 58, earring 26 to 46, spoon 17 to 30) and is not a quality signal there. On removal and texture it matches what was seen: 0.009 for the striped napkin, 0.014 for the shuttle backdrop, 0.032 to 0.038 for the giant bricks.
- `seam_ratio` flagged the product-cup case (2.1 to 3.8: the curved shadow line under the haze) and the jxl and rvxl roof tiles (1.8 and 2.2: the light line at the bottom edge; base 1.0). It missed the expand-all steps (0.72 to 1.03) because the step lies 0 to 30 px off the old edge and is smoothed by the feather. The 2x windows and 1:1 crops were trusted over it.
- No pairwise call needed the metrics; ties were left as ties.

## Recommendation

**Default SDXL checkpoint for prompted fills: realvisxl-v5.** It has the most acceptable results (10 of 33), the most pairwise wins (12), the fewest invented objects (artifacts 3.33) and 6 of 12 "replace with a prompt" cases acceptable, all clean of panels and frames. It is about 4.5 s slower per fill than jxl. juggernaut-xl-v9 is a close second and the better pick only if speed matters more than inventions. **Do not make sdxl-base the default:** it matches the fine-tunes on object insertion (6 of 12, and the best earring) but is the worst SDXL checkpoint on removal (1 of 13), on material changes and on expand, and wins only 2 cases. Keep it in the catalog as the licence-clean first-party fallback (CreativeML OpenRAIL++-M from Stability), not as the "Quality" default.

**Default for expand: none of the three, as benchmarked.** 0 of 5 expand-all results are acceptable, against 5 of 6 for the three SD 1.5 checkpoints. The one-side expands are no better than SD 1.5. Keep SD 1.5 (sd15-inpainting or ds8) for expand until the expand lane's guidance and negative changes are re-benchmarked on both expand-all cases (the two rvxl runs and the sdxl-base product run already had `cfg=4.0` and still show the step at the old frame), then re-judge.

**Is SDXL good enough to ship as the default at all? Only for one thing.** As the default for "type what you want into a selection" (object insertion and object swaps) it is clearly better than SD 1.5: 8 of 12 cross-family wins against 3, no pasted panels, photographic objects, at about 25 to 30 s and 7.2 GB per fill on an 8 GB card. It is not good enough as the default for removal (at best 3 of 13 acceptable; loses to LaMa/MAT 7 to 5 and to SD 1.5 8 to 4), for expand (0 of 5 on all sides), for material changes or huge damaged areas (1 of 12 acceptable across the three), or for text (0 of 6). Ship realvisxl-v5 as the "Quality" tier for prompted fills only, with routing: empty prompt to LaMa/MAT (or ds8), expand to SD 1.5 until fixed, and no single-pass fill for selections that cover most of the image. Making SDXL the blanket default would make the plug-in worse than the SD 1.5 tier on 16 of 33 cases.

## sdxl-base: source and gaps

- The index (`../../benchmark/index.json`) was re-read at 14:25, 14:50, 15:05, 15:20, 15:36 and 15:56 and never listed `sdxl-base`. Its batch waited for the GPU lock until 15:19, ran all 33 core cases from 15:20 to 15:35 (`logs/launcher.log`: "33 case(s) done, 0 left") and was still waiting for the lock to post its results at 15:56.
- To score it within the time box, the run's raw output (`runs/sdxl-base/<case>/after.raw` with the size and channels from `gimp-report.json`) was converted the way `run_benchmark.py` `load_raw`/`rgb` does (alpha over white) into `C:\AI\overnight-scratch\day\judge-sdxl\base-runs`. Nothing under the benchmark folders was modified. Seconds, cold flag, working size and plug-in settings are from `gimp-report.json`; the VRAM peak is from `logs/gpu-samples.jsonl` over each run's time window. When the benchmark lane posts the runs, its `report.json` values replace these; the images are the same.
- **Missing: sdxl-base landscape-expand-all.** The run ended with `execution-error`: "The AI backend is not available: GET /history/... failed: WinError 10060" after 32 s. This is a backend timeout during the batch (the harness or ComfyUI), not a model result, so it is not scored. sdxl-base's expand-all mean covers product-expand-all only.

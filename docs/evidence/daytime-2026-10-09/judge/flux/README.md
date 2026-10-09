# FLUX.1 Fill dev (GGUF Q4): visual judgement

Scope: the `flux1-fill-dev-gguf-q4` entries in `../../benchmark/index.json`. The index has 33. Three timed out (`execution-error`: face-remove-small-patch, landscape-replace-balloon, signage-replace-text). Two ran on the merged pipeline (60636cc), which sends an empty prompt to `lama-big` (`model_used_differs`: clouds-remove-large-palm, illustration-remove-large-baby), so they are not FLUX results. That leaves **28 FLUX results**, all scored. The runs used plug-in commits 095af15 (roof tiles), 8176966 (most cases) and 60636cc.

Method, rubric, anchors and verdict rule are the same as `../sdxl/README.md` (which follows `../sd15` and `../remove`), so rows can be compared directly. That includes the convention that a removed object replaced by a similar object scores 1 on adherence, artifacts and plausibility. Following the daytime efficiency rules, judging was done on contact sheets rather than per-case strips.

Files:

- `scores.csv`: same columns as `../sdxl/scores.csv`, plus `offload_lines`, `best_sdxl`, `best_sdxl_total`, `best_sdxl_verdict`, `pairwise_vs_best_sdxl`, `pairwise_reason`, `best_sd15` and `best_sd15_total`. The best SDXL result is the highest total in `../sdxl/scores.csv`, with realvisxl-v5 winning ties. The best SD 1.5 result comes from `../sd15/scores.csv` the same way, with ds8 winning ties.
- `sheets/sheet1..6.jpg`: five cases per sheet in case-name order. Each row shows before (selection in yellow) | FLUX | best SDXL (label gives the model and its total) | two 75 px windows of the FLUX result at 2x nearest-neighbour, taken at the midpoints of the selection edges (the old frame edge for expand). The crop is 1:1 when it fits in 420x300 px, otherwise scaled, and the label gives the factor. Expand cases show the full canvas.
- Scripts (`judge.py`, `zoom.py`, `scores_in.py`, `make_outputs.py`), full-resolution sheets and the 1:1 zooms used for borderline cases (roof tiles, the three expands) are in `C:\AI\overnight-scratch\day\judge-flux`. Metrics were computed on each run's `after-full.png` with the SDXL judge's own functions.

## Summary

| Model | Adherence | Continuity | Seam | Texture | Artifacts | Plausibility | Mean of six | PASS | PASS-WITH-NOTES | FAIL | vs best SDXL (better / same / worse) | Median s | Cold s | Median VRAM peak MiB (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| flux1-fill-dev-gguf-q4 (28) | 2.79 | 3.86 | 3.68 | 3.64 | 2.86 | 2.39 | 3.20 | 5 | 5 | 18 | 9 / 5 / 14 | 112.4 | 122.0, 129.5, 151.3 | 7633 (7858) |
| for reference: realvisxl-v5 (33) | 3.76 | 3.64 | 3.48 | 3.52 | 3.33 | 2.94 | 3.44 | 9 | 1 | 23 | - | 29.2 | 89.8, 120.8 | 7182 (7802) |

On the same 28 cases the best SDXL result is acceptable (PASS or PASS-WITH-NOTES) 11 times. FLUX is acceptable 10 times.

**Timing and memory.** Warm runs took 87 to 151 s, with a median of 112 s. That is about 3.9x realvisxl-v5 and about 13x dreamshaper-8. 11 of 28 runs logged ComfyUI partial loading ("5660.98 MB loaded, 959.41 MB offloaded"). The whole-GPU peak (desktop included) was 7.6 GB median and 7.86 GB max. There was no OOM, but the card has nothing left over.

**Timeouts.** 3 of the 31 runs routed to FLUX hit the plug-in's generation time limit, which it estimated at 134 to 166 s, so about 1 fill in 10 fails outright at the current setting. One of them was signage-replace-text ("Desert Museum"), so the main text test has no FLUX result.

## Per use case

Cell: mean of six / FLUX acceptable / best SDXL acceptable / pairwise (better-same-worse).

| Group | Cases | FLUX | Notes |
|---|---|---|---|
| replace with a prompt (object insertion and swap) | 10 | 4.10 / 6 / 6 / 4-3-3 | Sunglasses (29), strawberry (28, no calyx), fox (27), earring (27, hoop too large for "small") and canoe (24, glyphs on the hull) are photographic, with good light and no pasted panels. FLUX tends to scale the object to fill the selection: huge moon, huge ladybug without the grass blade. Spoon is a dull spatula on a faintly greyer square. Watermelon is one smooth, seedless wedge with an orange remnant. |
| text (inside replace) | 1 (+1 timed out) | 20H: 3.83, FAIL | **The first generative model in the benchmark to write all the requested characters** (the best SD 1.5 result wrote only "20"). "20H" comes out in bold black in the sign's own typeface, but upright rather than italic and with a stray vertical bar ("20 I H"). SDXL wrote nothing on this case. "Desert Museum" timed out (138 s limit), so multi-word text is untested. The text prior also works against FLUX: it writes garbled text where none was asked for (logo removal: "MUTGAL ES60K EUIT"; product expand: a fake headline and caption; canoe hull). |
| fill (material, damaged area) | 4 | 2.54 / 1 / 1 / 2-0-2 | **Suede is the best material change in the benchmark.** It keeps the same shoe and turns it to dark brown suede, with a slightly greyer backdrop rectangle (FAIL on seam and plausibility). Roof tiles have the right shape but are grey-brown, not red (PASS-WITH-NOTES). Tweed and the huge brick wall come back as a **flat pink disc** and a **flat grey slab** (8/30 each, the worst results). |
| remove (empty prompt sent to FLUX with the removal prompt) | 10 | 2.52 / 1 / 3 / 1-2-7 | Only the shuttle is removed cleanly (26, better than rvxl). Everything else is repainted or invented: a new fork, a new barn, a new white car, rewritten handwriting, a lattice tower for the obelisk, a red board for the portrait, a pink box for the AC unit, a flat blob for the cup, and garbled text for the logo. |
| expand (one side, all sides) | 4 | 3.33 / 2 / 1 / 2-0-2 | **landscape-expand-all is the first acceptable expand-all above the SD 1.5 tier** (25; SDXL had 0 of 5): meadow, sky and trees on all sides with no hard step, only slightly soft. interior-expand-left continues the molding but leaves a plain panel without damask (24). face-expand-right invents a second astronaut in the margin, and product-expand-all writes fake text into the white margins (FAIL). |

## Worst three

1. **fabric-damaged-large (8/30)** and **texture-damaged-huge (8/30).** A flat, featureless field fills the selection: a salmon-pink disc on tweed and a grey slab with rounded corners on brick. The prompt ("tweed wool fabric weave", "red brick wall") is ignored. The flat colour and rounded shape point to the sampling setup rather than to the model's prior (see plug-in notes).
2. **product-remove-large-cup (9/30).** A flat grey-brown blob with a hard edge replaces the cup and saucer on a white background. It is the same failure as 1, on a removal.
3. **architecture-remove-small-ac (12/30).** The AC unit becomes a flat pink box with the cable still plugged in. It is part flat field, part object prior.

Close behind: interior-remove-small-portrait (13, red board), and five removals at 15 that were repainted as the same kind of object (fork, barn, car, obelisk to tower, logo to glyphs), plus face-expand-right (15, second astronaut).

## Plug-in versus model

Plug-in (would change with code or settings):

- **The time limit is too tight for FLUX on 8 GB.** The estimate (134 to 166 s) is close to the median run time (112 s) and below the cold runs (up to 151 s, or 201 s wall time for the balloon), which gives 3 timeouts out of 31. FLUX on a partially offloaded card needs about 2x headroom (240 s or more), or a progress-based deadline instead of a fixed one.
- **The negative prompt does nothing.** `build_flux_fill` samples at `cfg=1.0` with FluxGuidance 30, so "watermark, text artifacts" and the removal negative are ignored. The removal prompt alone does not stop FLUX from repainting. The merged pipeline already sends empty prompts to LaMa (palm and baby in this index). It should do so for FLUX in every case, and FLUX should never receive a removal.
- **Flat fields (fabric, brick, cup, AC).** All four are large or high-contrast selections, filled with navier-stokes, colour match 1.0 (0.0 for the brick) and DifferentialDiffusion on a feathered mask at 25 euler steps. The results are flat and follow the rounded shape of the soft mask. This looks like a sampling or conditioning problem in the plug-in's FLUX graph, not the model's prior. A model prior draws something; these draw nothing. It needs one check with a hard mask, with no DifferentialDiffusion, and at the reference 50 steps, on fabric-damaged-large, before FLUX is offered for fills or materials.
- **No leaks.** The largest `mad_beyond_40px` is 0.23 levels and `leak_px_frac` is at most 0.00006.

Model:

- Strong object prior. It repaints removed objects literally and with high quality, which makes the failures worse (new fork, new barn, new car, new handwriting).
- Text prior. It writes legible glyphs on request, which no SD 1.5 or SDXL checkpoint did in full, but it also writes garbled text into empty white margins and onto signs it was meant to clear.
- Objects are scaled to fill the selection (moon, ladybug, earring). Lighting, depth of field and perspective integrate better than SDXL's (fox, sunglasses, suede).

Metrics were used only as tie-breakers. `seam_ratio` above 1.3 flags the cases where the object touches the selection edge (20H, earring, spoon, moon, canoe), not seams. `lap_ratio` of about 30 on cup and logo matches the hard blob edge and the glyphs.

## Recommendation

**Do not make FLUX Fill Q4 the "Quality (slow)" default for prompted fills on 8 GB cards.** On object insertion it ties realvisxl-v5 (6 of 10 acceptable each; pairwise 4 better, 3 same, 3 worse) while taking about 112 s per fill instead of 29 s. It also times out 1 time in 10 at the current limit and runs with about 1 GB offloaded. On fills and materials it can return a flat field (2 of 4). On removal it is as bad as sdxl-base (1 of 10 acceptable).

**Offer it as an opt-in "Quality (slow)" choice for prompted object fills and short text, with routing.** Short text is the one job it does that nothing else in the catalog does: "20H" is legible where SDXL wrote nothing. Before shipping it:

1. Send empty prompts and "Remove object" to LaMa/MAT, never to FLUX.
2. Raise the FLUX time limit to at least 240 s on 8 GB, or make the deadline depend on progress.
3. Fix or rule out the flat-field failure (hard mask, no DifferentialDiffusion, 50 steps) on fabric-damaged-large and product-remove-large-cup.
4. Re-run signage-replace-text and landscape-replace-balloon so that multi-word text is actually tested.

Keep realvisxl-v5 as the "Quality" default for prompted fills. For expand, FLUX beats SDXL on the landscape but writes text into plain margins, so SD 1.5 should stay the expand default (5 of 6 expand-all acceptable in `../sd15`).

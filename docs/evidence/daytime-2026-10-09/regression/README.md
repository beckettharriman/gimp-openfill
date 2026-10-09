# Regression check on the judges' failed cases, 2026-10-09 (daytime)

The 184 model/case pairs that failed in `judge/remove`, `judge/sd15` and `judge/sdxl` were re-run on the current plug-in with the benchmark's seeds and settings (`benchmark/benchmark-spec.json`, seed 1234, 25 steps, CFG 7), then compared pairwise with the old benchmark result: better / same / worse plus one line, not the full rubric.

- Plug-in: branch `gimp3-port` at `60636cc` (merge of the pipeline fixes; HEAD moved to `d88f014` during the run, which adds benchmark evidence only, no plug-in code). Module hashes for every GIMP process: `app.py c973a0a2822f`, `geometry.py c0d7ccbcc686`, `workflow.py ea1d8f192f8a`. `models/catalog.json` had an uncommitted edit (the SDXL base entry).
- Driver: `tests/gimp_batch_benchmark.py` (unchanged), one `gimp-console-3.2.exe` per model with the isolated test profile; 8 processes, all 184 runs returned `success`. ComfyUI was the already-running server on 8188.
- Empty prompts now go to LaMa whatever model is chosen, so the 54 SD 1.5 and SDXL "remove" pairs ran LaMa (column `used_lama`). Their outputs are pixel-identical to the `lama-big` benchmark result for the same case (max difference 1/255), so "now passes" for those rows is the `lama-big` verdict from `judge/remove`.
- Judging: one look at each contact sheet (`sheets/<family>-NN.jpg`, 5 rows each: before | old | new | new seam band at 2x, all crops 1:1 around the selection, 360 px window). Rows were pre-sorted by a metric score (seam gradient ratio and Laplacian ratio distance from 1, plus leak beyond 40 px; the same formulas as the judge scripts). Pixel-identical re-runs were scored `same` from the pixel comparison.
- "now_pass" with "(visual, crop)" is judged from the 1:1 crop only, not from the full image; "likely" means only the seam crop was seen. Treat both as candidates for the full-rubric pass.

## Summary

| Family | Pairs | Better | Same | Worse | Now pass (old rubric) | Ran LaMa (empty prompt) |
|---|---|---|---|---|---|---|
| remove (lama-big, mat-places512) | 52 | 0 | 52 | 0 | 0 | 25 (lama-big itself) |
| sd15 (3 checkpoints) | 60 | 19 | 34 | 7 | 8 | 22 (8 better / 11 same / 3 worse) |
| sdxl (3 checkpoints) | 72 | 31 | 36 | 5 | 7 (2 of them "likely") | 32 (23 better / 7 same / 2 worse) |
| total | 184 | 50 | 122 | 12 | 15 | |

- remove: `lama-big` is deterministic and its pipeline did not change: all 25 re-runs are pixel-identical. `mat-places512` differs by at most 0.14/255 on average (run-to-run noise); no visible change.
- Expand: SD 1.5 expands are pixel-identical to the old runs; SDXL expands changed and improved (interior-expand-left x3, landscape-expand-all x2), product-expand-all and face-expand-right are unchanged in look.
- Pixel-identical prompted SDXL fills (watermelon, moon, ladybug, earring, fox, 20H text; 15 pairs) did not touch the changed code paths.

## Five biggest improvements

1. `realvisxl-v5` / `juggernaut-xl-v9` `landscape-expand-all`: the blurred dark-green block with a hard horizontal step is gone; grass and tree line continue (likely PASS-WITH-NOTES; check the bottom-left watermark in a full view).
2. `realistic-vision-v6-inpainting` `architecture-material-roof-tiles`: red clay tiles now drawn across the whole strip with clean edges (old kept the dark metal). Four tiled passes at scale 1.0.
3. SDXL `interior-expand-left` (all three checkpoints): wall and moulding continue instead of an invented lampshade, rod or stacked frames.
4. `dreamshaper-8` / `realistic-vision-v6` `landscape-replace-balloon` and `product-replace-spoon`: the object now sits in the scene (no pasted blue-sky or black panel, no bowl) at a believable scale.
5. Removes routed to LaMa for SD/SDXL checkpoints: invented objects disappear (glowing pens and buckle on `face-remove-small-patch`, skyscraper on `crowd-remove-large-monument`, second trunks on `clouds-remove-large-palm`, swapped painting on `interior-remove-small-portrait`); `face-remove-small-patch` and `portrait-remove-large-shuttle` now reach the `lama-big` PASS-WITH-NOTES for 6 pairs.

## Regressions (12) and likely causes

| Model / case | What changed | Likely cause |
|---|---|---|
| sd15-inpainting / product2-material-suede, dreamshaper-8 / same, realistic-vision-v6 / same | the shoe is replaced by a white backdrop and a heel; the material change is lost | new minimum working scale with tiled passes: the 1722x898 selection is split into 4 tiles of 1066 px at scale 0.60, each tile sees only part of the shoe and paints its own scene. Runtime also rose from about 8.6 s to 34 s. |
| juggernaut-xl-v9, realvisxl-v5, sdxl-base / architecture-material-roof-tiles | a flat yellow or yellow-green slab instead of the old red tile ridge | same tiling: the 1620x89 strip runs as 2 SDXL tiles of 1024x576 that are mostly wall; grain matching then adds noise to a flat slab. The SD 1.5 runs of this case (4 tiles at 1.0) improved, so it is SDXL tile geometry, not the strip itself. |
| sd15-inpainting / text-replace-text-20h | selection painted plain yellow, no text at all | border pre-fill switched from `neutral` to `navier-stokes` for SD 1.5: the hole is pre-filled with smooth plate colour, and the inpainting model keeps it. The ranking change for "prompted fills that draw little" cannot help with one variation. |
| juggernaut-xl-v9, realvisxl-v5 / handwriting-remove-large-lines | ghost scribbles where the old run gave nearly clean paper | empty prompt now routes to LaMa, which smears the surrounding handwriting into the hole. |
| sd15-inpainting / night-street-remove-large-car | pale glare smear instead of a plausible road | LaMa routing; the hole is large and LaMa works at 512 px. |
| realistic-vision-v6 / illustration-remove-large-baby, interior-remove-small-portrait | ghost streaks / blotchy blurred damask where the old SD fill was clean | LaMa routing (structured patterns are a known LaMa weakness; `lama-big` failed these cases too). |

## Timing per family (seconds, plug-in procedure wall time)

| Family | Group | Pairs | Median warm, new | Median, old | Cold first case, new |
|---|---|---|---|---|---|
| remove | lama-big | 25 | 2.7 | 2.7 | 8.3 |
| remove | mat-places512 | 27 | 3.0 | 3.1 | 5.0 |
| sd15 | empty prompt (now LaMa) | 22 | 4.9 | 10.8 | 4.5 |
| sd15 | prompted | 38 | 10.7 | 8.6 | 11.6, 13.9 |
| sdxl | empty prompt (now LaMa) | 32 | 5.0 | 27.7 | 4.7 to 5.3 |
| sdxl | prompted | 40 | 24.2 | 27.8 | 51.0 |

Tiled cases are the slow ones: SD 1.5 `product2-material-suede` and `texture-damaged-huge` take 33 to 36 s (old 8 to 11 s); SDXL `architecture-material-roof-tiles` 47.5 s (old 23.8 s). Wall time for the whole re-run: 17:49 to 18:35 (46 min, including one 70 s lock pause).

## Files

- `scores.csv`: one row per pair: family, model, case, old_verdict, pairwise, reason, metrics (old->new seam ratio, Laplacian ratio, leak beyond 40 px, combined score, mean old/new difference), now_pass, used_lama, seconds old/new, cold, sheet.
- `sheets/`: 38 contact sheets (remove-01..11, sd15-01..12, sdxl-01..15), downscaled to 1400 px; full-size PNGs and full results in `C:\AI\overnight-scratch\day\regression\`.
- `<model>/<case>/report.json`, `plugin-log.txt`: per-run report (timing, VRAM, working size, code hashes) and the plug-in log lines; `index.json` lists them.

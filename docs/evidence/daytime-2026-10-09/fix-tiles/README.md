# Tiled fills and tiled LaMa removal (2026-10-09, daytime)

Branch `fix-pipeline`. Two follow-ups to the regression check (`../regression/README.md`). Benchmark
cases and seeds (`../benchmark/benchmark-spec.json`, seed 1234, 25 steps, CFG 7), run headless in
`gimp-console-3.2.exe` with the lane profile through `tests/gimp_batch_benchmark.py`
(`batch-command-example.txt`). "Current" is the regression lane's re-run
(`C:\AI\overnight-scratch\day\regression\runs`); "old" is the benchmark result. Pairwise verdicts on the
contact sheets in this folder; one row per pair in `scores.csv`. Full-size results:
`C:\AI\overnight-scratch\day\fix2\gimp\<variant>\<model>\<case>\after-full.png`.

## 1. Tiled prompted fills: layout pass

When the fill is tiled, the whole context is first generated in one pass (`geometry.layout_work`: the
single-pass scale raised to at least 0.45, long side at most 1.5 x the model's max side), pasted
through the mask, and the tiles then run over it at `tile_denoise` (setting, default 0.65) without
pre-fill and with the whole tile in the conditioning (the refine path of `_tile_pass`).
`geometry.wants_layout` decides per fill:

- the selection's shorter side at the tile scale is under 0.2 of the tiles' shorter working side
  (a strip whose tiles are mostly context): layout pass, any architecture (SDXL roof);
- SD 1.5 and at least 0.5 of a tile across (a large area split into a grid): layout pass (suede);
- otherwise tiles only. SDXL areas with the layout pass got worse (Juggernaut brick twice its size,
  red leather sleeve back to grey); SD 1.5 strips too (realistic-vision-v6 roof: clay tiles turned
  grey-white). Those three run exactly as before (pixel-identical).

| Pairs | better | same | worse |
|---|---|---|---|
| 6 regressions (suede x3 SD 1.5, roof x3 SDXL) | 6 | 0 | 0 |
| 3 guards (texture sd15 and Juggernaut, red leather Juggernaut) | 0 | 3 | 0 |

Tile denoise 0.5 vs 0.65: identical to the eye on SD 1.5; on SDXL 0.65 draws clearer tiles on all
three roof runs, so 0.65 is the default. On SD 1.5 the detail tiles change little: the suede result
with tiles at 0.02 differs from 0.65 by 0.31/255 on average (max 28), so for SD 1.5 the layout pass
does the work. The suede is still not the old result (a brown oxford): sd15-inpainting draws a heel.

Tile placement: windows are already centred on the selection across a strip and moved inside the
image only at the edge (unit test `test_strip_tiles_centred_on_the_selection_across`); the roof
strip sits on the top edge (51 px above it), so its SDXL windows (576 working px across, the model's
minimum) are mostly wall by necessity. The layout pass is what fixes that case.

## 2. LaMa on large holes: tiled removal

`INPAINT_InpaintWithModel` pads its input to a square and resizes it to 256 px (LaMa; MAT 512) with
nearest-neighbour sampling, so the plug-in's 512 px context reached LaMa at 0.1 to 0.2 of the image
scale on large holes. A 2x upscaled crop cannot help (it is resized to 256 px the same way), so that
variant was not run. Tiled removal (`geometry.plan_removal`, `workflow._removal_tiles`): windows of
512 image px centred on the selection, chained (later windows see earlier results as known pixels),
hard hole mask for the node, blended back over a 24 px ramp inside the repainted half-overlap band.

Variants: 512/128, 512/256 and 384/128 (tile/overlap) on the 9 cases (`p2-lama-*.jpg`). All three
fixed the night-street car and smoothed the shuttle, but windows deep inside a hole are nearly all
hole and come back grey: a dark blob in place of the tea cup (guard) and on the baby. So only bands are
tiled (shorter side at most 0.75 x 512); deeper holes keep the single pass. Kept: 512/128 (same look
as 512/256, fewer windows); settings `removal_tile` (0 = off) and `removal_tile_overlap`.

| Pairs (kept variant) | better | same | worse |
|---|---|---|---|
| 5 regressions (handwriting x2 routes, night car, baby, portrait) | 1 | 4 | 0 |
| old worst: face-remove-large-shuttle | 0 | 1 | 0 |
| 4 guards (text logo, text signs, product handle, product cup) | 0 | 4 | 0 |

Small holes are untouched (pixel-identical: portrait, handle; cup, shuttle and baby by the band
rule). Handwriting: sharper pseudo-script instead of a smear, still leftover writing. The structured
damask (portrait) and the baby need a better removal model, not tiling.

# Pipeline quality: the plug-in defects isolated by the judges (2026-10-09, daytime)

Branch `fix-pipeline`. Cases and photos from `../benchmark/benchmark-spec.json`, seed 1234, plug-in
defaults (25 steps, CFG 7, dpmpp_2m karras). Exploration ran outside GIMP through the plug-in's own
`geometry` and `workflow` modules against the ComfyUI on 8188 (`C:\AI\overnight-scratch\day\pipeline\sim.py`,
GIMP-like composite); every kept change was then verified headless in `gimp-console-3.2.exe` with the
lane profile (`gimp_run.py`, a wrapper of `tests/gimp_batch_benchmark.py`; `batch-command-example.txt`,
`plugin-log.txt`). "Before" is the benchmark's own result for the case (`day\benchmark\runs`) unless
marked "sim". Verdicts are pairwise (better / same / worse) by eye on the sheets in each folder; the
labels on the sheets carry the judges' `lap_ratio` (L) and `seam_ratio` (S).

## Results

| Step | Change | Cases (model) | Verdict | Kept |
|---|---|---|---|---|
| 1a pale frame | border pre-fill for SD 1.5 and a hard (grown, unblurred) model mask for SD 1.5 inpainting fills | strawberry, spoon, balloon, suede (sd15, ds8 in sim; sd15 in GIMP) | better 7 of 8 (frame and pasted panels gone; balloon less colourful, same) | yes |
| 1b soft large fills | minimum working scale 0.6 / 0.75: smaller margin, then overlapping tiles chained in one graph | texture-damaged-huge (sd15, Juggernaut), red leather (Juggernaut) | better 3 of 3 (no niche, brick scale right; leather drawn); Juggernaut brick shifts to orange | yes |
| 1c thin strip | tiles at least 256 working px across | roof tiles (sd15 GIMP; Juggernaut sim) | sd15 better (no yellow box, textured band, still not clay tiles); Juggernaut worse in sim (planks) | yes |
| 1d removal | LaMa before MAT; working size 768 / 1024; LaMa + SD 1.5 refine 0.4 / 0.55 / 0.8 | face-remove-large-shuttle, night-street-remove-large-car | larger working sizes: same (the node resizes LaMa to 256 px internally); refine: same (adds grain, no structure) | order only |
| 2 refine | second pass at full resolution, denoise 0.35 to 0.5 | fabric-damaged-large, horse, fox, strawberry (sd15); fabric, leather (Juggernaut) | worse or same (SD 1.5 softer with a visible rectangle; Juggernaut changes yarn scale) | code kept, off |
| 3 caption | no-model scene description appended to prompts | balloon, horse, sunglasses, red leather, window, watermelon (sd15, Juggernaut) | better 1, worse 4, same 7 (sunglasses lost on SD 1.5, orange window on Juggernaut) | code kept, off |
| 4 ranking | quality.rank orders variations | strawberry, balloon, seeds 1234, 7, 42 (sd15, 4 variations, GIMP) | first layer = my pick in 5 of 6 (see below) | yes |
| 5 routing | empty prompt or Remove goes to LaMa/MAT; SDXL expand goes to an installed SD 1.5 inpainting model | night car, shuttle (GIMP log: "empty prompt -> using lama-big") | as designed | yes |
| 6 clipping | layer mask shows the whole growth on upscaled fills | watermelon, ladybug (Juggernaut), earring (sd15) | same | no (reverted) |
| 7 grain | noise measured in flat areas of the ring and of the layer; the missing part added | brick, leather, roof (GIMP), spoon (clean) | invisible at 3x on brick; nothing added on clean photos (spoon, strawberry) | yes |
| 8 coverage | blur pre-fill + denoise 0.75 when the selection covers > 60 % of the context | texture-damaged-huge (sd15, Juggernaut) | worse (flat smudge); the tiled pass is the fix | no |

## Findings

- 1a: the pale frame was not the pre-fill extent. The SD 1.5 inpainting UNet sees the hole as grey in
  its conditioning image wherever the mask is at least 0.5, while the blurred band of the noise mask
  is sampled only in the last steps; there it reproduced that grey (profile across the strawberry's
  right edge: 73 inside, 134 in the grown band, 92 outside). A hard model mask removes it; the GIMP
  layer feather does the blending. The neutral grey pre-fill caused the pasted panels (dreamshaper-8
  spoon and balloon, sd15 spoon blob).
- 1d: `INPAINT_InpaintWithModel` pads LaMa input to a square and resizes it to 256 px (MAT: 512) with
  nearest-neighbour sampling, so the plug-in's working size cannot raise LaMa's resolution. Large holes
  stay smeared; fixing that needs a different LaMa runner (native resolution), not a plug-in setting.
- Timeout (coordinator item): the automatic estimate adds the model files' load time from disk and a
  10-minute floor when the server's last prompt used other model files; the deadline moves while
  progress events arrive. Observed live: "timeout estimate 600 s (model files 8.4 GB, cold)".

## 4. Ranking detail

Headless runs with 4 variations (`4-ranking/`, each variation from the plug-in's debug dump). With the
first metric set the first layer matched my pick in 2 of 4 (seeds 1234 and 7): it preferred a tiny
strawberry and a small balloon because only seam, softness and frame counted for prompted fills. A
content term was added (prompted fills whose inside hardly differs from the ring rank lower,
`quality.PROMPT_CONTENT`), calibrated on those same 4 runs: 3 of 4 there (the miss is strawberry seed
1234, where it picks v2 over my v1, both good strawberries). Out of sample (seed 42, run after the
change): 2 of 2. Variations without the object (bare stem) now rank last in every run.

## Expand routing

`product-expand-all` with `juggernaut-xl-v9` chosen: log "model juggernaut-xl-v9 -> using SD 1.5
sd15-inpainting", success in 12 s.

## Open issues

- Roof tiles: no SD 1.5 or Juggernaut result draws clay tiles; Juggernaut's tiled pass invents planks.
- Tiled SDXL fills are slow (texture-damaged-huge: 121 s for 4 tiles).
- LaMa on large holes (see 1d).
- Objects clipped at the selection edge on upscaled fills come from the model mask itself.

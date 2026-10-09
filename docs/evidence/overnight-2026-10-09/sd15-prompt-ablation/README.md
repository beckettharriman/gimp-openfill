# SD 1.5 inpainting ignores the prompt on flat synthetic regions (ablation)

Cases sel-edge-top, sel-edge-*, sel-corner-*, sel-multi-disjoint, img-aspect-*,
img-unsaved-new and sel-tiny-20px returned success with a correct layer and
mask, but SD 1.5 inpainting painted the surrounding background (sky, flat box)
instead of "red brick wall" (mean abs diff in the selection 0 to 3).

The exact crop and mask the plug-in sent for sel-edge-top (`sent-image.png`,
`sent-mask.png`, 616x600 working size) were re-run directly against ComfyUI
with parts of the graph removed (`exp_fill.py`, `exp2.py`, seed 1234). Mean
abs diff inside the mask:

| Graph variant | "red brick wall" | "a red hot air balloon" |
|---|---|---|
| as the plug-in builds it (blur pre-fill, color match) | 0.85 | 0.85 |
| no color match | 2.15 | 2.26 |
| no pre-fill | 0.77 | |
| no pre-fill, no color match | 2.25 | |
| border pre-fill | 0.84 | |
| no DifferentialDiffusion, no color match | 2.18 | |
| noise_mask off, no color match | 2.81 | |
| both off, no color match | 2.81 | |

No graph step is responsible: the SD 1.5 inpainting checkpoint itself
continues the flat sky. The same positions are re-tested with the Quality
tier (`*-quality` cases in matrix-spec.json).

Follow-up (same crop, seeds 1234 / 7 / 99): a neutral grey pre-fill alone
still gave sky; neutral pre-fill with the context margin reduced from 1x to
0.5x the selection gave a brick wall at 2 of 3 seeds, and at 0.25x at 3 of 3
(one a small brick door). Prompted fills now use the neutral pre-fill and a
0.5x margin (removal keeps 1x and the border pre-fill). In the matrix this
turned sel-edge-left, sel-edge-bottom, sel-corner-bottomright, img-aspect-wide
and img-256/1024 into passes; flat-sky positions (sel-edge-top/right,
sel-corner-topleft, img-aspect-tall, sel-multi-disjoint, sel-tiny-20px and
sel-edge-left at seeds 7/99) still come back as sky with SD 1.5, while the
same positions pass with Juggernaut XL (`*-quality` cases). A 0.25x margin
was tried in the matrix as well: it only added sel-edge-left-seed7, so the
wider 0.5x margin (more context for blending) was kept.
